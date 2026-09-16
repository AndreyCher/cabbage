from __future__ import annotations
import argparse,json,logging,os,signal,sys,time,uuid,subprocess
from datetime import datetime,timezone
from pathlib import Path
from .config_loader import load_runtime_config
from .runtime import RuntimeContext,FatalActionError,ShutdownRequested
from .control_api import ControlAPIServer
from .android import AndroidDevice
from .actions import ActionEngine
from .phone_provider import PhoneSession
from .telephony import TelephonySession, resolve_identity

APP_VERSION=Path(__file__).resolve().parent.parent.joinpath("VERSION").read_text().strip() if Path(__file__).resolve().parent.parent.joinpath("VERSION").is_file() else "dev"
def dump(path,data): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
def logger_for(run_dir):
    l=logging.getLogger("worker-android");l.setLevel(logging.INFO);l.handlers.clear();f=logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for h in (logging.StreamHandler(sys.stdout),logging.FileHandler(run_dir/"run.log",encoding="utf-8")): h.setFormatter(f);l.addHandler(h)
    return l

def expected_inputs(actions): return {str(a["key"]) for a in actions if isinstance(a,dict) and a.get("type")=="wait_input" and a.get("key")}

def start_video(device,cfg,run_dir,logger):
    if not cfg.get("recording",{}).get("video",False): return None
    p=run_dir/"videos"/"session.mp4";p.parent.mkdir(parents=True,exist_ok=True)
    max_time=int(cfg.get("recording",{}).get("max_time_sec",180)); bitrate=int(cfg.get("recording",{}).get("bitrate",4000000))
    remote="/sdcard/cabbage-session.mp4"; proc=subprocess.Popen(["adb","-s",device.serial,"shell","screenrecord","--bit-rate",str(bitrate),"--time-limit",str(min(max_time,180)),remote],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return proc,remote,p

def stop_video(device,state,logger):
    if not state:return {"video":False,"files":[]}
    proc,remote,p=state
    if proc.poll() is None: proc.terminate();
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
    time.sleep(.5); r=subprocess.run(["adb","-s",device.serial,"pull",remote,str(p)],capture_output=True,text=True); subprocess.run(["adb","-s",device.serial,"shell","rm","-f",remote],capture_output=True)
    if r.returncode==0 and p.is_file() and p.stat().st_size>0:return {"video":True,"backend":"android-screenrecord","files":[str(p.relative_to(p.parents[1]))]}
    return {"video":True,"backend":"android-screenrecord","files":[],"errors":[(r.stderr or "recording unavailable").strip()]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--profile");args=ap.parse_args()
    system=os.getenv("WORKER_SYSTEM_CONFIG","/config/config.json"); profile=args.profile or os.getenv("WORKER_PROFILE","android-test-001")
    cfg,layout=load_runtime_config(profile,system); scenario=cfg["run"]["scenario"]; actions=cfg["scenarios"][scenario]["actions"]
    run_id=str(cfg.get("run",{}).get("run_id") or uuid.uuid4()); run_dir=Path(layout["artifacts_dir"])/cfg["identity"]/scenario/run_id; (run_dir/"screenshots").mkdir(parents=True,exist_ok=True)
    log=logger_for(run_dir); runtime=RuntimeContext(cfg["identity"],run_id,scenario,expected_inputs(actions)); device=AndroidDevice(cfg,log); api=None; video=None; phone=None; telephony=None
    summary={"app_version":APP_VERSION,"project":layout["project_name"],"component":f"worker-{layout['worker_type']}","worker_type":layout["worker_type"],"identity":cfg["identity"],"scenario":scenario,"run_id":run_id,"controller_run_id":cfg.get("run",{}).get("controller_run_id"),"configuration":{"system":layout["system_config"],"global_default":layout["global_default_config"],"local_default":layout["local_default_config"] if layout["local_default_loaded"] else None,"profile":layout["profile_config"],"scenario":layout["scenario_config"]},"started_at":datetime.now(timezone.utc).isoformat(),"shutdown":{"requested":False,"signal":None,"reason":None,"graceful":False}}
    def on_signal(sig,_): runtime.request_shutdown(sig); raise ShutdownRequested(sig)
    oldi,oldt=signal.signal(signal.SIGINT,on_signal),signal.signal(signal.SIGTERM,on_signal)
    try:
        # Install the SMS validator before publishing the API; early callbacks
        # must not occupy an unvalidated SMS input slot during Android boot.
        # Validate fixed telephony values before touching Android. Cloud phone
        # numbers are intentionally optional: a new worker run must never
        # require reuse of a number allocated by an earlier container.
        resolve_identity(cfg.get("telephony", {}), cfg["identity"], "+15555550100")
        phone_cfg = cfg.get("phone_number_provider", {})
        if phone_cfg.get("enabled", False):
            try:
                phone = PhoneSession(phone_cfg, runtime)
            except FatalActionError:
                if phone_cfg.get("required", False):
                    raise
                summary["phone_provider"] = {"provider": phone_cfg.get("provider"), "allocated": False, "warning": "unavailable"}
                log.warning("Phone provider is unavailable; starting without a connected phone")
        acfg=cfg.get("api",{})
        if acfg.get("enabled",True): api=ControlAPIServer(runtime,host=acfg.get("host","0.0.0.0"),port=int(acfg.get("port",8090)),logger=log,profile_config_path=Path(layout["identities_dir"])/cfg["identity"]/"config.json",project_name=layout["project_name"],worker_type=layout["worker_type"]);api.start()
        log.info("Project: %s",layout["project_name"]);log.info("Component: worker-%s",layout["worker_type"]);log.info("Worker version: %s",APP_VERSION);log.info("Identity: %s",cfg["identity"]);log.info("Scenario: %s",scenario);log.info("Run ID: %s",run_id)
        runtime.set_status("starting"); device.wait_ready(int(cfg.get("android",{}).get("boot_timeout_sec",180)))
        cloud_number = None
        if phone:
            try:
                cloud_number = phone.start()["number"]
                summary["phone_provider"] = {"provider": phone_cfg["provider"], "allocated": True}
            except FatalActionError:
                if phone_cfg.get("required", False):
                    raise
                try: phone.close()
                except Exception: log.warning("Phone provider cleanup failed after unavailable allocation")
                phone = None
                summary["phone_provider"] = {"provider": phone_cfg.get("provider"), "allocated": False, "warning": "unavailable"}
                log.warning("Phone provider is unavailable; starting without a connected phone")
        elif (cfg.get("telephony", {}).get("enabled", False)
              and isinstance(cfg.get("telephony", {}).get("phone_number"), dict)
              and cfg["telephony"]["phone_number"].get("source") == "cloud_provider"):
            summary["phone_provider"] = {"configured": False, "allocated": False, "warning": "not_configured"}
            log.warning("No phone provider is configured; starting without a connected phone")
        values = resolve_identity(cfg.get("telephony", {}), cfg["identity"], cloud_number,
                                  allow_missing_cloud_number=True)
        if values and values["phone_number"] is None:
            log.warning("Telephony QA is starting without a connected phone number")
        if values:
            telephony = TelephonySession(device, cfg["telephony"], values)
            telephony.prepare()
        caps=device.connect(); summary["device"]={"serial":device.serial,"capabilities":caps};dump(run_dir/"device.json",summary["device"])
        if telephony:
            telephony.start()
            device.telephony = telephony
            summary["telephony"] = {"backend": "app_api", "packages": cfg["telephony"]["packages"], "enabled": True}
        video=start_video(device,cfg,run_dir,log); runtime.set_status("running"); eng=ActionEngine(device,run_dir,log,runtime=runtime,continue_on_error_default=bool(cfg.get("debug",{}).get("continue_on_error",False))); results=eng.run(actions);summary["actions"]=results;summary["action_failures"]=sum(1 for x in results if x["status"]=="FAIL");summary["status"]="PASS";runtime.set_status("completed")
        if phone:
            phone.close()
        summary["runtime"] = runtime.public_status()
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        dump(run_dir/"runtime-events.json", runtime.events())
        dump(run_dir/"summary.json", summary)
        if cfg.get("debug",{}).get("keep_alive",False):
            log.info("Debug keep_alive enabled; waiting for container stop")
            while not runtime.is_shutdown_requested(): time.sleep(1)
    except ShutdownRequested as exc: summary.update(status="STOPPED",reason="user_interrupt",message="Container stop requested by user or orchestrator.");summary["shutdown"]={"requested":True,"signal":exc.signal_number,"reason":"user_interrupt","graceful":False};runtime.set_status("stopped")
    except FatalActionError as exc: summary.update(status="FAIL",reason=exc.reason,message=str(exc));summary.update(exc.details);runtime.set_failure(exc.reason,str(exc))
    except Exception as exc: summary.update(status="FAIL",reason="unexpected_error",error=repr(exc));runtime.set_failure("unexpected_error",repr(exc));log.exception("Scenario failed")
    finally:
        if phone:
            try: phone.close()
            except Exception:
                summary["phone_provider_cleanup"] = "release_failed"
                log.error("Phone provider release failed; allocation requires reconciliation")
        if telephony:
            try: telephony.close()
            except Exception: log.error("Telephony QA cleanup failed")
        try: summary["recording"]=stop_video(device,video,log)
        except Exception as exc: summary["recording"]={"video":True,"files":[],"errors":[str(exc)]}
        try: device.close()
        except Exception: log.exception("Appium cleanup failed")
        summary["runtime"]=runtime.public_status();dump(run_dir/"runtime-events.json",runtime.events())
        if api:
            try: api.stop()
            except Exception: pass
        if summary.get("shutdown",{}).get("requested"):summary["shutdown"]["graceful"]=True
        summary["finished_at"]=datetime.now(timezone.utc).isoformat();dump(run_dir/"summary.json",summary);signal.signal(signal.SIGINT,oldi);signal.signal(signal.SIGTERM,oldt);log.info("Result: %s",summary.get("status"));log.info("Artifacts: %s",run_dir)
    return 0 if summary.get("status") in {"PASS","STOPPED"} else 1
if __name__=="__main__": raise SystemExit(main())
