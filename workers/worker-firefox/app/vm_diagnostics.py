from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VM_DIAGNOSTICS_SCHEMA = 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None


def _run(cmd: list[str], timeout: int = 5) -> str | None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        out = (proc.stdout or proc.stderr or "").strip()
        return out if out else None
    except Exception:
        return None


def _json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten(value[key], child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            child = f"{prefix}[{idx}]"
            out.update(_flatten(item, child))
    else:
        out[prefix] = value
    return out


def _diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    fa, fb = _flatten(a), _flatten(b)
    keys = sorted(set(fa) | set(fb))
    same: list[str] = []
    changed: dict[str, dict[str, Any]] = {}
    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}
    for key in keys:
        if key not in fa:
            added[key] = fb[key]
        elif key not in fb:
            removed[key] = fa[key]
        elif fa[key] == fb[key]:
            same.append(key)
        else:
            changed[key] = {"baseline": fa[key], "current": fb[key]}
    return {
        "summary": {
            "same": len(same),
            "changed": len(changed),
            "added": len(added),
            "removed": len(removed),
            "drift_detected": bool(changed or added or removed),
        },
        "changed": changed,
        "added": added,
        "removed": removed,
    }


def _parse_kv_lines(value: str | None, separator: str = ':') -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(value, str):
        return out
    for line in value.splitlines():
        if separator not in line:
            continue
        key, raw = line.split(separator, 1)
        key = key.strip()
        raw = raw.strip()
        if key:
            out[key] = raw
    return out


def _summarize_xdpyinfo(value: Any) -> str:
    if not isinstance(value, str):
        return repr(value)
    import re
    dims = re.search(r"dimensions:\s+(\d+)x(\d+) pixels", value)
    resolution = re.search(r"resolution:\s+(\d+)x(\d+) dots per inch", value)
    vendor = re.search(r"vendor string:\s+(.+)", value)
    version = re.search(r"X\.Org version:\s+(.+)", value)
    depth = re.search(r"depth of root window:\s+(\d+) planes", value)
    visuals = re.search(r"number of visuals:\s+(\d+)", value)
    parts: list[str] = []
    if dims:
        parts.append(f"size={dims.group(1)}x{dims.group(2)}")
    if resolution:
        parts.append(f"dpi={resolution.group(1)}x{resolution.group(2)}")
    if depth:
        parts.append(f"depth={depth.group(1)}")
    if visuals:
        parts.append(f"visuals={visuals.group(1)}")
    if vendor:
        parts.append(f"vendor={vendor.group(1).strip()}")
    if version:
        parts.append(f"xorg={version.group(1).strip()}")
    return ', '.join(parts) if parts else f"raw_len={len(value)}"


def _summarize_meminfo(value: Any) -> str:
    if not isinstance(value, str):
        return repr(value)
    kv = _parse_kv_lines(value)
    keys = ('MemTotal', 'MemAvailable', 'MemFree', 'Cached', 'SwapTotal', 'SwapFree')
    parts = [f"{key}={kv[key]}" for key in keys if key in kv]
    return ', '.join(parts) if parts else f"raw_len={len(value)}"


def _summarize_proc_status(value: Any) -> str:
    if not isinstance(value, str):
        return repr(value)
    kv = _parse_kv_lines(value)
    keys = ('Pid', 'PPid', 'Threads', 'VmSize', 'VmRSS', 'VmSwap', 'voluntary_ctxt_switches', 'nonvoluntary_ctxt_switches')
    parts = [f"{key}={kv[key]}" for key in keys if key in kv]
    return ', '.join(parts) if parts else f"raw_len={len(value)}"


def _compact_value(key: str, value: Any) -> str:
    if key == 'host.x11.xdpyinfo':
        return _summarize_xdpyinfo(value)
    if key == 'host.memory.meminfo':
        return _summarize_meminfo(value)
    if key == 'host.proc.status':
        return _summarize_proc_status(value)
    if isinstance(value, str):
        clean = value.replace('\n', ' ').replace('\t', ' ').strip()
        if len(clean) > 180:
            return repr(clean[:177] + '...')
        return repr(clean)
    text = repr(value)
    return text if len(text) <= 180 else text[:177] + '...'


def _log_vm_diff(logger, diff: dict[str, Any], max_items: int = 20) -> None:
    summary = diff['summary']
    logger.warning(
        'VM diagnostics cross-run drift: changed=%s added=%s removed=%s same=%s (full diff saved to artifacts)',
        summary['changed'], summary['added'], summary['removed'], summary['same']
    )

    # Capture timestamps always change and are useful in snapshots, but not in console drift output.
    ignored_console_keys = {'captured_at', 'host.capturedAt'}
    emitted = 0

    for key, values in diff['changed'].items():
        if key in ignored_console_keys:
            continue
        logger.warning(
            '  VM DIAG CHANGED %s: %s -> %s',
            key,
            _compact_value(key, values['baseline']),
            _compact_value(key, values['current']),
        )
        emitted += 1
        if emitted >= max_items:
            break

    if emitted < max_items:
        for key, value in diff['added'].items():
            if key in ignored_console_keys:
                continue
            logger.warning('  VM DIAG ADDED %s: %s', key, _compact_value(key, value))
            emitted += 1
            if emitted >= max_items:
                break

    if emitted < max_items:
        for key, value in diff['removed'].items():
            if key in ignored_console_keys:
                continue
            logger.warning('  VM DIAG REMOVED %s: %s', key, _compact_value(key, value))
            emitted += 1
            if emitted >= max_items:
                break

    visible_total = sum(1 for k in diff['changed'] if k not in ignored_console_keys) \
        + sum(1 for k in diff['added'] if k not in ignored_console_keys) \
        + sum(1 for k in diff['removed'] if k not in ignored_console_keys)
    if visible_total > emitted:
        logger.warning('  VM DIAG: %s additional changes omitted from console; see vm-diagnostics/diff.json', visible_total - emitted)


def _browser_snapshot(page) -> dict[str, Any]:
    try:
        return page.evaluate(
        r"""
        async () => {
          const safe = async (fn, fallback = null) => {
            try { return await fn(); } catch (_) { return fallback; }
          };

          const result = {
            navigator: {}, screen: {}, window: {}, media: {}, audio: {}, webgl: {},
            capabilities: {}, css: {}, timing: {}
          };

          result.navigator = {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            languages: Array.from(navigator.languages || []),
            hardwareConcurrency: navigator.hardwareConcurrency,
            deviceMemory: navigator.deviceMemory ?? null,
            maxTouchPoints: navigator.maxTouchPoints,
            webdriver: navigator.webdriver,
            cookieEnabled: navigator.cookieEnabled,
            doNotTrack: navigator.doNotTrack,
            pdfViewerEnabled: navigator.pdfViewerEnabled ?? null,
            pluginsLength: navigator.plugins ? navigator.plugins.length : null,
            mimeTypesLength: navigator.mimeTypes ? navigator.mimeTypes.length : null,
            userAgentData: navigator.userAgentData ? {
              mobile: navigator.userAgentData.mobile,
              platform: navigator.userAgentData.platform,
              brands: navigator.userAgentData.brands
            } : null,
            connection: navigator.connection ? {
              effectiveType: navigator.connection.effectiveType,
              downlink: navigator.connection.downlink,
              rtt: navigator.connection.rtt,
              saveData: navigator.connection.saveData
            } : null
          };

          result.screen = {
            width: screen.width, height: screen.height,
            availWidth: screen.availWidth, availHeight: screen.availHeight,
            colorDepth: screen.colorDepth, pixelDepth: screen.pixelDepth,
            orientationType: screen.orientation ? screen.orientation.type : null,
            orientationAngle: screen.orientation ? screen.orientation.angle : null
          };
          result.window = {
            innerWidth, innerHeight, outerWidth, outerHeight,
            screenX, screenY, devicePixelRatio,
            visualViewport: window.visualViewport ? {
              width: visualViewport.width,
              height: visualViewport.height,
              scale: visualViewport.scale,
              offsetLeft: visualViewport.offsetLeft,
              offsetTop: visualViewport.offsetTop
            } : null
          };

          const mq = q => matchMedia(q).matches;
          result.css = {
            pointerFine: mq('(pointer:fine)'), pointerCoarse: mq('(pointer:coarse)'), pointerNone: mq('(pointer:none)'),
            anyPointerFine: mq('(any-pointer:fine)'), anyPointerCoarse: mq('(any-pointer:coarse)'),
            hover: mq('(hover:hover)'), anyHover: mq('(any-hover:hover)'),
            colorGamutP3: mq('(color-gamut:p3)'), colorGamutRec2020: mq('(color-gamut:rec2020)'),
            prefersReducedMotion: mq('(prefers-reduced-motion: reduce)'),
            forcedColors: mq('(forced-colors: active)'), invertedColors: mq('(inverted-colors: inverted)')
          };

          // Some APIs throw SecurityError on about:blank / opaque origins in Firefox.
          // VM diagnostics are best-effort and must never abort the scenario.
          result.capabilities = {
            webAssembly: typeof WebAssembly !== 'undefined',
            sharedArrayBuffer: typeof SharedArrayBuffer !== 'undefined',
            webGPU: await safe(async () => !!navigator.gpu, null),
            bluetooth: await safe(async () => !!navigator.bluetooth, null),
            usb: await safe(async () => !!navigator.usb, null),
            serial: await safe(async () => !!navigator.serial, null),
            hid: await safe(async () => !!navigator.hid, null),
            mediaDevices: await safe(async () => !!navigator.mediaDevices, null),
            serviceWorker: await safe(async () => !!navigator.serviceWorker, null),
            indexedDB: await safe(async () => !!window.indexedDB, null),
            localStorage: await safe(async () => !!window.localStorage, null)
          };

          result.media.devices = await safe(async () => {
            if (!navigator.mediaDevices?.enumerateDevices) return [];
            const devices = await navigator.mediaDevices.enumerateDevices();
            return devices.map(d => ({kind: d.kind, hasLabel: !!d.label, hasDeviceId: !!d.deviceId, hasGroupId: !!d.groupId}));
          }, []);
          result.media.deviceCounts = result.media.devices.reduce((acc, d) => {
            acc[d.kind] = (acc[d.kind] || 0) + 1; return acc;
          }, {});

          result.audio = await safe(async () => {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return {available:false};
            const ctx = new Ctx();
            const data = {
              available: true,
              sampleRate: ctx.sampleRate,
              baseLatency: ctx.baseLatency ?? null,
              outputLatency: ctx.outputLatency ?? null,
              state: ctx.state,
              destinationMaxChannelCount: ctx.destination?.maxChannelCount ?? null
            };
            try { await ctx.close(); } catch (_) {}
            return data;
          }, {error:'audio-context-failed'});

          result.webgl = await safe(async () => {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return {available:false};
            const dbg = gl.getExtension('WEBGL_debug_renderer_info');
            return {
              available: true,
              vendor: gl.getParameter(gl.VENDOR),
              renderer: gl.getParameter(gl.RENDERER),
              unmaskedVendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : null,
              unmaskedRenderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null,
              version: gl.getParameter(gl.VERSION),
              shadingLanguageVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
              maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
              maxRenderbufferSize: gl.getParameter(gl.MAX_RENDERBUFFER_SIZE),
              maxVertexAttribs: gl.getParameter(gl.MAX_VERTEX_ATTRIBS),
              maxVertexTextureImageUnits: gl.getParameter(gl.MAX_VERTEX_TEXTURE_IMAGE_UNITS),
              maxTextureImageUnits: gl.getParameter(gl.MAX_TEXTURE_IMAGE_UNITS),
              maxCombinedTextureImageUnits: gl.getParameter(gl.MAX_COMBINED_TEXTURE_IMAGE_UNITS),
              aliasedLineWidthRange: Array.from(gl.getParameter(gl.ALIASED_LINE_WIDTH_RANGE)),
              aliasedPointSizeRange: Array.from(gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE)),
              extensions: (gl.getSupportedExtensions() || []).slice().sort()
            };
          }, {error:'webgl-failed'});

          result.timing = {
            performanceNowResolutionSample: await safe(async () => {
              const samples = [];
              let prev = performance.now();
              for (let i = 0; i < 250; i++) {
                let cur = performance.now();
                if (cur !== prev) { samples.push(cur - prev); prev = cur; }
              }
              if (!samples.length) return null;
              return {
                minDelta: Math.min(...samples),
                maxDelta: Math.max(...samples),
                sampleCount: samples.length
              };
            }, null)
          };

          return result;
        }
        """
        )
    except Exception as exc:
        return {
            "error": f"browser-snapshot-failed: {type(exc).__name__}: {exc}",
            "partial": True,
        }


def _host_snapshot() -> dict[str, Any]:
    cpuinfo = _read_text('/proc/cpuinfo') or ''
    cpu_model = None
    cpu_flags = None
    for line in cpuinfo.splitlines():
        if cpu_model is None and line.lower().startswith('model name'):
            cpu_model = line.split(':', 1)[1].strip() if ':' in line else line
        if cpu_flags is None and (line.lower().startswith('flags') or line.lower().startswith('features')):
            cpu_flags = sorted((line.split(':', 1)[1] if ':' in line else '').split())
        if cpu_model is not None and cpu_flags is not None:
            break

    dmi_paths = {
        'sysVendor': '/sys/class/dmi/id/sys_vendor',
        'productName': '/sys/class/dmi/id/product_name',
        'productVersion': '/sys/class/dmi/id/product_version',
        'boardVendor': '/sys/class/dmi/id/board_vendor',
        'boardName': '/sys/class/dmi/id/board_name',
        'biosVendor': '/sys/class/dmi/id/bios_vendor',
        'biosVersion': '/sys/class/dmi/id/bios_version',
    }
    dmi = {k: v for k, p in dmi_paths.items() if (v := _read_text(p)) is not None}

    cgroup_files = {
        'cpuMax': '/sys/fs/cgroup/cpu.max',
        'cpusetEffective': '/sys/fs/cgroup/cpuset.cpus.effective',
        'memoryMax': '/sys/fs/cgroup/memory.max',
        'memoryHigh': '/sys/fs/cgroup/memory.high',
        'pidsMax': '/sys/fs/cgroup/pids.max',
    }
    cgroup = {k: v for k, p in cgroup_files.items() if (v := _read_text(p)) is not None}

    return {
        'capturedAt': _utc_now(),
        'platform': {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'python': platform.python_version(),
        },
        'environment': {
            'DISPLAY': os.getenv('DISPLAY'),
            'CAMOUFOX_EXECUTABLE_PATH': os.getenv('CAMOUFOX_EXECUTABLE_PATH'),
        },
        'cpu': {
            'count': os.cpu_count(),
            'model': cpu_model,
            'flags': cpu_flags,
        },
        'memory': {
            'meminfo': _read_text('/proc/meminfo'),
        },
        'cgroup': cgroup,
        'proc': {
            'cgroup': _read_text('/proc/self/cgroup'),
            'status': _read_text('/proc/self/status'),
        },
        'dmi': dmi,
        'x11': {
            'xdpyinfo': _run(['xdpyinfo', '-display', os.getenv('DISPLAY', ':99')]),
        },
    }


def collect_vm_snapshot(page, identity_state: dict[str, Any], label: str = 'unknown') -> dict[str, Any]:
    return {
        'schema_version': VM_DIAGNOSTICS_SCHEMA,
        'captured_at': _utc_now(),
        'identity': identity_state.get('metadata', {}).get('identity'),
        'label': label,
        'browser': _browser_snapshot(page),
        'host': _host_snapshot(),
    }


def run_vm_diagnostics(cfg: dict[str, Any], page, identity_state: dict[str, Any], run_dir: Path, logger) -> dict[str, Any]:
    diag_cfg = cfg.get('vm_diagnostics', {})
    if not diag_cfg.get('enabled', False):
        return {'enabled': False}

    logger.info('VM diagnostics: ENABLED')
    label = str(diag_cfg.get('label', 'unknown'))
    snapshot = collect_vm_snapshot(page, identity_state, label=label)
    diag_dir = run_dir / 'vm-diagnostics'
    snapshot_path = diag_dir / 'snapshot.json'
    if diag_cfg.get('save_snapshot', True):
        _json_write(snapshot_path, snapshot)

    identity_root = Path(identity_state['paths']['root'])
    baseline_path = identity_root / 'vm-diagnostics-baseline.json'
    history_dir = identity_root / 'vm-diagnostics-history'
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    if diag_cfg.get('keep_history', True):
        _json_write(history_path, snapshot)

    result: dict[str, Any] = {
        'enabled': True,
        'label': label,
        'snapshot': str(snapshot_path) if diag_cfg.get('save_snapshot', True) else None,
        'history': str(history_path) if diag_cfg.get('keep_history', True) else None,
        'baseline': str(baseline_path),
        'drift_detected': False,
    }

    compare = diag_cfg.get('compare_with_baseline', True)
    update = diag_cfg.get('update_baseline', False)
    if baseline_path.exists() and compare:
        try:
            baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
            if baseline.get('schema_version') == VM_DIAGNOSTICS_SCHEMA:
                diff = _diff(baseline, snapshot)
                _json_write(diag_dir / 'diff.json', diff)
                result['diff'] = diff['summary']
                result['drift_detected'] = bool(diff['summary']['drift_detected'])
                if result['drift_detected']:
                    _log_vm_diff(logger, diff)
                else:
                    logger.info('VM diagnostics cross-run: no drift (%s comparable fields)', diff['summary']['same'])
            else:
                logger.info('VM diagnostics baseline schema changed; refreshing baseline')
                update = True
        except Exception:
            logger.exception('Failed to compare VM diagnostics baseline')

    if not baseline_path.exists() or update:
        _json_write(baseline_path, snapshot)
        logger.info('VM diagnostics baseline saved: %s', baseline_path)

    return result
