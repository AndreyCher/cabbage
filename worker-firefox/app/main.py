from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import signal
import secrets
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .actions import ActionEngine
from .browser import launch
from .browser_cleanup import BrowserCleanupTimeout, bounded_manager_exit, terminate_browser_children
from .config_loader import load_runtime_config
from .control_api import ControlAPIServer
from .runtime import FatalActionError, RuntimeContext, ShutdownRequested
from .diagnostics import browser_identity, compare_proxy_geo_to_identity, network_preflight, proxy_geo_snapshot
from .identity import APP_VERSION, identity_paths, load_or_create_identity, reset_identity
from .plugins import PluginManager, PluginError
from .proxy import ProxyError, classify_proxy_exception, proxy_geo_policy, validate_proxy_config
from .profile_config import (
    apply_direct_overrides,
    effective_fingerprint,
    generation_fingerprint,
    load_or_create_profile_config,
    resolve_window,
    resolved_profile_snapshot,
)
from .fingerprint_diagnostics import run_fingerprint_diagnostics
from .vm_diagnostics import run_vm_diagnostics


def setup_logger(run_dir: Path) -> logging.Logger:
    logger = logging.getLogger("worker-firefox")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    fh = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


def dump_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def wait_for_interactive_debug(cfg: dict, logger: logging.Logger, runtime: RuntimeContext) -> None:
    debug_cfg = cfg.get("debug", {})
    browser_mode = cfg.get("browser", {}).get("mode", "virtual")
    if browser_mode != "debug" or not debug_cfg.get("keep_alive", False):
        return

    logger.info("=" * 72)
    logger.info("DEBUG INTERACTIVE MODE: browser remains open for manual control")
    logger.info("noVNC: http://<docker-host>:6080/vnc.html")
    message = debug_cfg.get("message")
    if message:
        logger.info("%s", message)
    logger.info("Stop with Ctrl+C or: docker compose --profile debug down")
    logger.info("=" * 72)

    # Signal handlers are global for the whole application lifecycle in v0.4.20.
    # Wait on the same RuntimeContext shutdown event used by running actions.
    while not runtime.is_shutdown_requested():
        runtime.interruptible_wait(1.0)

    logger.info("Leaving interactive debug mode; graceful shutdown started")
    raise ShutdownRequested(runtime.shutdown_signal)

def finalize_recorded_videos(run_dir: Path, logger: logging.Logger) -> dict:
    video_dir = run_dir / "videos"
    raw_dir = video_dir / ".raw"
    video_dir.mkdir(parents=True, exist_ok=True)

    # Playwright/Camoufox writes video locally.  During SIGINT/SIGTERM the
    # browser transport may already be closed, so do not call Video.save_as().
    # Wait briefly for local files to finish flushing after context shutdown.
    raw_files: list[Path] = []
    for _ in range(20):
        if raw_dir.is_dir():
            raw_files = sorted(
                (p for p in raw_dir.iterdir() if p.is_file() and p.suffix.lower() == ".webm"),
                key=lambda p: (p.stat().st_mtime_ns, p.name),
            )
        if raw_files and all(p.stat().st_size > 0 for p in raw_files):
            break
        time.sleep(0.1)

    saved: list[str] = []
    errors: list[str] = []
    for index, source in enumerate(raw_files, start=1):
        target = video_dir / f"page-{index:02d}.webm"
        try:
            shutil.copy2(source, target)
            saved.append(str(target))
            logger.info("Saved video: %s", target)
        except Exception as exc:
            errors.append(repr(exc))
            logger.error("Failed to finalize video %s: %s", source.name, exc)

    if not raw_files:
        errors.append("No finalized raw video files found")
        logger.warning("No finalized raw video files found in %s", raw_dir)

    return {"video": True, "files": saved, "errors": errors}



def expected_input_keys(actions: list[dict]) -> set[str]:
    return {
        str(action["key"])
        for action in actions
        if action.get("type") == "wait_input" and action.get("key")
    }

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Worker runtime v{APP_VERSION}")
    parser.add_argument(
        "profile",
        nargs="?",
        default=os.environ.get("WORKER_PROFILE"),
        help="Profile name from paths.profiles_dir (for example test-user-004) or an explicit profile JSON path.",
    )
    parser.add_argument(
        "--system-config",
        default=os.environ.get("WORKER_SYSTEM_CONFIG"),
        help="Bootstrap system config path. Prefer WORKER_SYSTEM_CONFIG in container deployments.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--reset-identity",
        action="store_true",
        help="Delete the configured identity and browser profile, then create a completely new Identity.",
    )
    group.add_argument(
        "--update-identity",
        action="store_true",
        help="Regenerate the fingerprint/device config from the current JSON while preserving the browser profile.",
    )
    parser.add_argument("--version", action="version", version=APP_VERSION)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.system_config:
        raise SystemExit("WORKER_SYSTEM_CONFIG or --system-config is required")
    if not args.profile:
        raise SystemExit("WORKER_PROFILE or profile argument is required")

    cfg, layout = load_runtime_config(args.profile, args.system_config)
    identities_root = layout["identities_dir"]

    if args.reset_identity:
        reset_identity(cfg["identity"], identities_root)

    paths = identity_paths(cfg["identity"], identities_root)
    profile_cfg = load_or_create_profile_config(paths["config"], cfg["identity"])
    effective_fp = effective_fingerprint(cfg, profile_cfg)
    identity_cfg = copy.deepcopy(cfg)
    identity_cfg.setdefault("fingerprint", {}).update(generation_fingerprint(cfg, profile_cfg))

    run_id = f'{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{secrets.token_hex(2)}'
    scenario_name = cfg["run"]["scenario"]
    run_dir = Path(layout["artifacts_dir"]) / cfg["identity"] / scenario_name / run_id
    (run_dir / "screenshots").mkdir(parents=True, exist_ok=True)
    logger = setup_logger(run_dir)
    plugins = PluginManager(cfg, logger=logger)

    scenario_actions = cfg["scenarios"][scenario_name]["actions"]
    runtime = RuntimeContext(
        cfg["identity"],
        run_id,
        scenario_name,
        expected_inputs=expected_input_keys(scenario_actions),
    )

    old_sigint = signal.getsignal(signal.SIGINT)
    old_sigterm = signal.getsignal(signal.SIGTERM)

    def _request_shutdown(signum, _frame):
        first = runtime.request_shutdown(int(signum))
        if first:
            logger.info("Container stop requested by signal %s", signum)
            # v0.4.20: do not only set a flag.  Raising the controlled
            # shutdown exception from the main-thread signal handler unwinds
            # a currently blocking synchronous Playwright call (mouse.move,
            # click, goto, screenshot, etc.) so Docker does not have to wait
            # until stop_grace_period and SIGKILL the container.
            raise ShutdownRequested(int(signum))
        # A second signal during finalization must not interrupt cleanup.
        logger.warning("Shutdown already requested; signal %s received again", signum)

    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)
    api_cfg = cfg.get("api", {})
    api_server = None
    if api_cfg.get("enabled", True):
        api_server = ControlAPIServer(
            runtime,
            host=api_cfg.get("host", "0.0.0.0"),
            port=int(api_cfg.get("port", 8090)),
            logger=logger,
            profile_config_path=paths["config"],
            project_name=layout["project_name"],
            worker_type=layout["worker_type"],
        )
        api_server.start()

    logger.info("Project: %s", layout["project_name"])
    logger.info("Component: worker-%s", layout["worker_type"])
    logger.info("Worker version: %s", APP_VERSION)
    logger.info("Identity: %s", cfg["identity"])
    logger.info("Scenario: %s", scenario_name)
    logger.info("Run ID: %s", run_id)
    logger.info("System config: %s", layout["system_config"])
    logger.info("Default config: %s", layout["default_config"])
    logger.info("Profile config: %s", layout["profile_config"])
    logger.info("Scenario config: %s", layout["scenario_config"])
    source_commit_path = Path(layout["browser_source_commit"])
    browser_source_commit = source_commit_path.read_text(encoding="utf-8").strip() if source_commit_path.is_file() else None
    logger.info("Custom Camoufox source: %s", browser_source_commit or "unknown")
    if args.reset_identity:
        logger.warning("Identity was reset before this run")
    if args.update_identity:
        logger.warning("Identity fingerprint/device config update requested; browser profile will be preserved")

    summary = {
        "app_version": APP_VERSION,
        "project": layout["project_name"],
        "component": f'worker-{layout["worker_type"]}',
        "worker_type": layout["worker_type"],
        "identity": cfg["identity"],
        "scenario": scenario_name,
        "run_id": run_id,
        "browser_source_commit": browser_source_commit,
        "configuration": {
            "system": layout["system_config"],
            "default": layout["default_config"],
            "profile": layout["profile_config"],
            "scenario": layout["scenario_config"],
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
        "network_preflight": None,
        "shutdown": {
            "requested": False,
            "signal": None,
            "reason": None,
            "graceful": False,
        },
    }
    try:
        validate_proxy_config(cfg)
        summary["network_preflight"] = network_preflight(cfg)
        dump_json(run_dir / "network.json", summary["network_preflight"])
        logger.info("Network preflight: %s", summary["network_preflight"])
        if cfg.get("proxy", {}).get("enabled") and summary["network_preflight"].get("proxy_public_ip") is None:
            logger.warning(
                "Proxy public IP preflight unavailable; proxy GEO validation may be skipped or unavailable"
            )

        identity_state = load_or_create_identity(identity_cfg, logger=logger, update=args.update_identity, identities_root=identities_root)

        # v0.4.32: proxy GEO is validation-only during normal runs.  The
        # persistent Identity remains the source of truth for locale/languages/
        # timezone/geolocation; changing the proxy must not rewrite them.
        geo_policy = proxy_geo_policy(cfg) if cfg.get("proxy", {}).get("enabled") else {
            "enabled": False, "validate_identity": False, "fail_on_mismatch": False
        }
        proxy_geo = proxy_geo_snapshot(cfg) if geo_policy["validate_identity"] else None
        geo_validation = compare_proxy_geo_to_identity(
            proxy_geo, identity_state["metadata"].get("location_identity")
        )
        summary["proxy_geo_validation"] = geo_validation
        dump_json(run_dir / "proxy-geo-validation.json", geo_validation)
        if proxy_geo and proxy_geo.get("error"):
            logger.warning("Proxy GEO validation unavailable: %s", proxy_geo.get("error"))
        elif geo_validation.get("mismatch"):
            loc = identity_state["metadata"].get("location_identity", {})
            logger.warning(
                "PROXY GEO mismatch: proxy_country=%s proxy_timezone=%s identity_locale=%s identity_timezone=%s",
                proxy_geo.get("country_code") if proxy_geo else None,
                proxy_geo.get("timezone") if proxy_geo else None,
                loc.get("locale"),
                loc.get("timezone"),
            )
            for mismatch in geo_validation.get("mismatches", []):
                logger.warning(
                    "PROXY GEO MISMATCH %s: identity=%r proxy=%r",
                    mismatch.get("field"), mismatch.get("identity"), mismatch.get("proxy"),
                )
            logger.info("Identity location fingerprint preserved; proxy GEO did not modify browser settings")
            if geo_policy["fail_on_mismatch"]:
                raise ProxyError(
                    "proxy_identity_geo_mismatch",
                    "Proxy GEO does not match persistent Identity location settings.",
                    geo_validation,
                )
        elif geo_validation.get("checked"):
            logger.info(
                "Proxy GEO matches Identity: country=%s timezone=%s",
                proxy_geo.get("country_code") if proxy_geo else None,
                proxy_geo.get("timezone") if proxy_geo else None,
            )

        identity_state["profile_config"] = profile_cfg
        identity_state["effective_fingerprint"] = effective_fp
        identity_state["launch_camou_config"] = apply_direct_overrides(identity_state["camou_config"], effective_fp)
        identity_state["resolved_window"] = resolve_window(effective_fp, identity_state["launch_camou_config"])
        profile_snapshot = resolved_profile_snapshot(
            profile_cfg, effective_fp, identity_state["launch_camou_config"]
        )
        dump_json(run_dir / "resolved-profile.json", profile_snapshot)
        summary["resolved_profile"] = profile_snapshot
        logger.info("Resolved identity profile saved: %s", run_dir / "resolved-profile.json")
        if identity_state["resolved_window"]:
            logger.info(
                "Identity window: %sx%s",
                identity_state["resolved_window"]["width"],
                identity_state["resolved_window"]["height"],
            )
        summary["identity_state"] = {
            "created": identity_state["created"],
            "updated": identity_state.get("updated", False),
            "created_at": identity_state["metadata"].get("created_at"),
            "proxy_id": identity_state["metadata"].get("proxy_identity", {}).get("proxy_id"),
            "identity_file": str(identity_state["paths"]["metadata"]),
            "profile_config_file": str(identity_state["paths"]["config"]),
            "profile_dir": str(identity_state["paths"]["profile"]),
            "fingerprint_request": identity_state["metadata"].get("fingerprint_request"),
        }

        browser_manager = launch(cfg, identity_state, run_dir=str(run_dir))
        context = browser_manager.__enter__()
        engine = None
        try:
            page = context.pages[0] if context.pages else context.new_page()

            observed_identity = browser_identity(page)
            summary["browser_identity"] = observed_identity
            dump_json(run_dir / "browser-identity.json", observed_identity)
            logger.info("Browser identity: %s", observed_identity)

            fp_diag = run_fingerprint_diagnostics(cfg, page, identity_state, run_dir, logger)
            summary["fingerprint_diagnostics"] = fp_diag
            if fp_diag.get("drift_detected") and fp_diag.get("fail_on_change"):
                raise RuntimeError("Fingerprint drift detected and fingerprint_diagnostics.fail_on_change=true")

            vm_diag = run_vm_diagnostics(cfg, page, identity_state, run_dir, logger)
            summary["vm_diagnostics"] = vm_diag

            debug_mode = cfg.get("browser", {}).get("mode", "virtual") == "debug"
            engine = ActionEngine(
                context,
                run_dir,
                logger,
                continue_on_error_default=debug_mode,
                runtime=runtime,
                plugins=plugins,
                show_cursor=bool(cfg.get("recording", {}).get("show_cursor", False)),
            )
            engine.page = page
            engine.pages = [page]
            runtime.set_status("running")
            results = engine.run(scenario_actions)
            summary["actions"] = results

            failed_actions = [item for item in results if item.get("status") == "FAIL"]
            summary["action_failures"] = len(failed_actions)
            summary["debug_continue_on_error"] = debug_mode
            summary["status"] = "PASS"
            runtime.set_status("completed")

            if debug_mode and failed_actions:
                logger.warning(
                    "Debug mode completed with %d failed action(s); failures were recorded but did not abort the scenario",
                    len(failed_actions),
                )

            wait_for_interactive_debug(cfg, logger, runtime)
        finally:
            if engine is not None:
                plugins.teardown_all(engine.ctx)
            # A stuck Playwright transport can also hang Camoufox.__exit__ after
            # the action watchdog has already raised. Bound cleanup so PID 1 can
            # always reach summary finalization and exit without external Ctrl+C.
            browser_exc_info = sys.exc_info()
            try:
                logger.info("Closing Camoufox browser context")
                bounded_manager_exit(browser_manager, browser_exc_info, logger, timeout_sec=4.0)
                summary["browser_cleanup"] = {"status": "graceful"}
                logger.info("Camoufox browser context closed")
            except BrowserCleanupTimeout as cleanup_exc:
                logger.error("Browser cleanup timeout: %s", cleanup_exc)
                fallback = terminate_browser_children(logger)
                summary["browser_cleanup"] = {
                    "status": "forced",
                    "reason": "cleanup_timeout",
                    "message": str(cleanup_exc),
                    **fallback,
                }
                if browser_exc_info[0] is None:
                    raise RuntimeError(str(cleanup_exc)) from cleanup_exc
            except Exception as cleanup_exc:
                logger.error("Browser cleanup failed: %s", cleanup_exc)
                fallback = terminate_browser_children(logger)
                summary["browser_cleanup"] = {
                    "status": "forced",
                    "reason": "cleanup_error",
                    "message": repr(cleanup_exc),
                    **fallback,
                }
                if browser_exc_info[0] is None:
                    raise

    except ShutdownRequested as exc:
        summary["status"] = "STOPPED"
        summary["reason"] = "user_interrupt"
        summary["message"] = "Container stop requested by user or orchestrator."
        summary["shutdown"] = {
            "requested": True,
            "signal": exc.signal_number if exc.signal_number is not None else runtime.shutdown_signal,
            "reason": "user_interrupt",
            "graceful": False,
        }
        runtime.set_status("stopped")
        logger.info("Scenario stopped by shutdown request; finalizing artifacts")
    except ProxyError as exc:
        summary["status"] = "FAIL"
        summary["reason"] = exc.reason
        summary["message"] = str(exc)
        if exc.details:
            summary["proxy_error"] = exc.details
        runtime.set_status("failed")
        logger.error("Proxy error: %s", str(exc))
        logger.error("Reason: %s", exc.reason)
    except FatalActionError as exc:
        summary["status"] = "FAIL"
        summary["reason"] = exc.reason
        summary["message"] = str(exc)
        summary.update(exc.details)
        runtime.set_status("failed")
        logger.error(
            "Scenario stopped: %s (reason=%s)",
            str(exc), exc.reason,
        )
    except Exception as exc:
        proxy_error = classify_proxy_exception(exc) if cfg.get("proxy", {}).get("enabled", False) else None
        if proxy_error is not None:
            summary["status"] = "FAIL"
            summary["reason"] = proxy_error.reason
            summary["message"] = str(proxy_error)
            summary["error"] = repr(exc)
            runtime.set_status("failed")
            logger.error("Proxy error: %s", str(proxy_error))
            logger.error("Reason: %s", proxy_error.reason)
        else:
            summary["status"] = "FAIL"
            summary["reason"] = "unexpected_error"
            summary["error"] = repr(exc)
            runtime.set_status("failed")
            logger.exception("Scenario failed due to unexpected error")
    finally:
        if not cfg.get("recording", {}).get("video", False):
            summary["recording"] = {"video": False, "files": []}
        else:
            logger.info("Finalizing video artifacts")
            summary["recording"] = finalize_recorded_videos(run_dir, logger)

        summary["runtime"] = runtime.public_status()
        dump_json(run_dir / "runtime-events.json", runtime.events())
        if api_server is not None:
            logger.info("Stopping Control API")
            api_server.stop()
        if runtime.is_shutdown_requested() and not summary.get("shutdown", {}).get("requested"):
            summary["shutdown"] = {
                "requested": True,
                "signal": runtime.shutdown_signal,
                "reason": "user_interrupt",
                "graceful": False,
            }
            if summary.get("status") not in {"FAIL", "STOPPED"}:
                summary["status"] = "STOPPED"
                summary["reason"] = "user_interrupt"
                runtime.set_status("stopped")
        if summary.get("shutdown", {}).get("requested"):
            summary["shutdown"]["graceful"] = True
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        dump_json(run_dir / "summary.json", summary)
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)
        logger.info("Result: %s", summary["status"])
        logger.info("Artifacts: %s", run_dir)
        if summary.get("shutdown", {}).get("requested"):
            logger.info("Container stoping bye")

    return 0 if summary["status"] in {"PASS", "STOPPED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
