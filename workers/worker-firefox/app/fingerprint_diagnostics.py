from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


from .profile_config import set_baseline_stale


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)


def _sha256_json(data: Any) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten(value[key], child))
    elif isinstance(value, list):
        # Ordering itself can be fingerprint-relevant, so lists are atomic.
        out[prefix] = value
    else:
        out[prefix] = value
    return out


def diff_snapshots(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    old = flatten(baseline)
    new = flatten(current)
    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}
    changed: dict[str, dict[str, Any]] = {}
    same = 0

    for key in sorted(set(old) | set(new)):
        if key not in old:
            added[key] = new[key]
        elif key not in new:
            removed[key] = old[key]
        elif old[key] != new[key]:
            changed[key] = {"baseline": old[key], "current": new[key]}
        else:
            same += 1

    return {
        "summary": {
            "same": same,
            "changed": len(changed),
            "added": len(added),
            "removed": len(removed),
            "drift_detected": bool(changed or added or removed),
        },
        "changed": changed,
        "added": added,
        "removed": removed,
    }


def observed_signals(page) -> dict[str, Any]:
    """Collect deterministic browser-visible signals, including rendering output.

    The probes deliberately avoid time/performance/random values. Rendering has
    multiple independent hashes so we can tell whether drift comes from pixels,
    serialization, metrics, WebGL parameters, or higher-level page logic.
    """
    return page.evaluate(
        r"""
        async () => {
          const hashString = (str) => {
            let h = 2166136261 >>> 0;
            for (let i = 0; i < str.length; i++) {
              h ^= str.charCodeAt(i);
              h = Math.imul(h, 16777619) >>> 0;
            }
            return h.toString(16).padStart(8, '0');
          };
          const hashBytes = (arr) => {
            let h = 2166136261 >>> 0;
            for (let i = 0; i < arr.length; i++) {
              h ^= arr[i];
              h = Math.imul(h, 16777619) >>> 0;
            }
            return h.toString(16).padStart(8, '0');
          };

          const result = {
            navigator: {
              userAgent: navigator.userAgent,
              platform: navigator.platform,
              language: navigator.language,
              languages: Array.from(navigator.languages || []),
              hardwareConcurrency: navigator.hardwareConcurrency ?? null,
              deviceMemory: navigator.deviceMemory ?? null,
              maxTouchPoints: navigator.maxTouchPoints ?? null,
              webdriver: navigator.webdriver ?? null,
              cookieEnabled: navigator.cookieEnabled ?? null,
              pdfViewerEnabled: navigator.pdfViewerEnabled ?? null
            },
            screen: {
              width: screen.width,
              height: screen.height,
              availWidth: screen.availWidth,
              availHeight: screen.availHeight,
              colorDepth: screen.colorDepth,
              pixelDepth: screen.pixelDepth,
              devicePixelRatio: window.devicePixelRatio,
              innerWidth: window.innerWidth,
              innerHeight: window.innerHeight,
              outerWidth: window.outerWidth,
              outerHeight: window.outerHeight
            },
            intl: {
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
              locale: Intl.DateTimeFormat().resolvedOptions().locale,
              calendar: Intl.DateTimeFormat().resolvedOptions().calendar,
              numberingSystem: Intl.DateTimeFormat().resolvedOptions().numberingSystem
            },
            media: {
              colorSchemeDark: matchMedia('(prefers-color-scheme: dark)').matches,
              reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
              pointerFine: matchMedia('(pointer: fine)').matches,
              pointerCoarse: matchMedia('(pointer: coarse)').matches,
              hover: matchMedia('(hover: hover)').matches
            },
            canvas: {},
            webgl: {},
            audio: {},
            fonts: {}
          };

          try {
            const canvas = document.createElement('canvas');
            canvas.width = 360;
            canvas.height = 160;
            const ctx = canvas.getContext('2d', {willReadFrequently: true});
            ctx.textBaseline = 'alphabetic';
            const gradient = ctx.createLinearGradient(0, 0, 360, 160);
            gradient.addColorStop(0, '#f60');
            gradient.addColorStop(0.5, '#069');
            gradient.addColorStop(1, '#6c0');
            ctx.fillStyle = gradient;
            ctx.fillRect(8, 8, 344, 144);
            ctx.globalCompositeOperation = 'multiply';
            ctx.fillStyle = 'rgba(240, 220, 80, .72)';
            ctx.beginPath();
            ctx.arc(95, 72, 47, 0, Math.PI * 2);
            ctx.fill();
            ctx.globalCompositeOperation = 'source-over';
            ctx.fillStyle = '#102030';
            ctx.font = '18px Arial';
            ctx.fillText('Camoufox FP diagnostics 0.4.9', 18, 116);
            ctx.font = '22px serif';
            ctx.fillText('Aa Ω Ж 😀 🦊', 18, 145);
            ctx.strokeStyle = 'rgba(255,255,255,.83)';
            ctx.lineWidth = 1.25;
            ctx.beginPath();
            ctx.bezierCurveTo(170, 15, 320, 45, 225, 135);
            ctx.stroke();

            const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const metrics = ctx.measureText('Aa Ω Ж 😀 🦊 Camoufox');
            const dataUrl = canvas.toDataURL('image/png');
            result.canvas.dataUrlHash = hashString(dataUrl);
            result.canvas.dataUrlLength = dataUrl.length;
            try {
              const payload = dataUrl.split(',', 2)[1] || '';
              const decoded = atob(payload);
              const pngBytes = new Uint8Array(decoded.length);
              for (let i = 0; i < decoded.length; i++) pngBytes[i] = decoded.charCodeAt(i);
              result.canvas.dataUrlBytesHash = hashBytes(pngBytes);
              result.canvas.dataUrlBytesLength = pngBytes.length;
            } catch (e) {
              result.canvas.dataUrlBytesError = String(e);
            }
            try {
              const blob = await new Promise((resolve, reject) => {
                canvas.toBlob(value => value ? resolve(value) : reject(new Error('canvas.toBlob returned null')), 'image/png');
              });
              const blobBytes = new Uint8Array(await blob.arrayBuffer());
              result.canvas.blobHash = hashBytes(blobBytes);
              result.canvas.blobSize = blob.size;
              result.canvas.blobType = blob.type;
            } catch (e) {
              result.canvas.blobError = String(e);
            }
            result.canvas.pixelHash = hashBytes(image.data);
            result.canvas.textMetrics = {
              width: metrics.width,
              actualBoundingBoxAscent: metrics.actualBoundingBoxAscent,
              actualBoundingBoxDescent: metrics.actualBoundingBoxDescent,
              actualBoundingBoxLeft: metrics.actualBoundingBoxLeft,
              actualBoundingBoxRight: metrics.actualBoundingBoxRight
            };
          } catch (e) {
            result.canvas.error = String(e);
          }

          try {
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 128;
            const gl = canvas.getContext('webgl', {
              antialias: true,
              alpha: true,
              depth: true,
              preserveDrawingBuffer: true
            }) || canvas.getContext('experimental-webgl');
            if (!gl) throw new Error('WebGL unavailable');

            const dbg = gl.getExtension('WEBGL_debug_renderer_info');
            result.webgl.vendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
            result.webgl.renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
            result.webgl.version = gl.getParameter(gl.VERSION);
            result.webgl.shadingLanguageVersion = gl.getParameter(gl.SHADING_LANGUAGE_VERSION);
            result.webgl.maxTextureSize = gl.getParameter(gl.MAX_TEXTURE_SIZE);
            result.webgl.maxRenderbufferSize = gl.getParameter(gl.MAX_RENDERBUFFER_SIZE);
            // Firefox/Camoufox exposes some WebGL typed-array parameters through
            // Xray wrappers. Reading MAX_VIEWPORT_DIMS caused the v0.4.7 probe
            // to abort before rendering. Keep scalar/string parameters here and
            // continue to the deterministic render probe instead.
            result.webgl.extensions = (gl.getSupportedExtensions() || []).slice().sort();
            result.webgl.extensionsHash = hashString(result.webgl.extensions.join('|'));

            const compile = (type, src) => {
              const shader = gl.createShader(type);
              gl.shaderSource(shader, src);
              gl.compileShader(shader);
              if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
                throw new Error(gl.getShaderInfoLog(shader) || 'shader compile failed');
              }
              return shader;
            };
            const vs = compile(gl.VERTEX_SHADER, `
              attribute vec2 p;
              attribute vec3 c;
              varying vec3 v;
              void main(){ gl_Position=vec4(p,0.0,1.0); v=c; }
            `);
            const fs = compile(gl.FRAGMENT_SHADER, `
              precision mediump float;
              varying vec3 v;
              void main(){
                float f = sin(gl_FragCoord.x * 0.071) * cos(gl_FragCoord.y * 0.053);
                gl_FragColor=vec4(v * (0.82 + f * 0.12), 1.0);
              }
            `);
            const program = gl.createProgram();
            gl.attachShader(program, vs);
            gl.attachShader(program, fs);
            gl.linkProgram(program);
            if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
              throw new Error(gl.getProgramInfoLog(program) || 'program link failed');
            }
            gl.useProgram(program);
            const data = new Float32Array([
              -0.92,-0.85, 1,0.15,0.2,
               0.91,-0.71, 0.1,1,0.25,
              -0.13, 0.94, 0.15,0.25,1
            ]);
            const buffer = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
            gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
            const stride = 5 * 4;
            const pLoc = gl.getAttribLocation(program, 'p');
            const cLoc = gl.getAttribLocation(program, 'c');
            gl.enableVertexAttribArray(pLoc);
            gl.vertexAttribPointer(pLoc, 2, gl.FLOAT, false, stride, 0);
            gl.enableVertexAttribArray(cLoc);
            gl.vertexAttribPointer(cLoc, 3, gl.FLOAT, false, stride, 2 * 4);
            gl.viewport(0, 0, canvas.width, canvas.height);
            gl.clearColor(0.031, 0.047, 0.071, 1);
            gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
            gl.drawArrays(gl.TRIANGLES, 0, 3);
            gl.finish();

            const pixels = new Uint8Array(canvas.width * canvas.height * 4);
            gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
            result.webgl.renderPixelHash = hashBytes(pixels);
            result.webgl.renderDataUrlHash = hashString(canvas.toDataURL('image/png'));

            const precisions = {};
            for (const stage of [['vertex', gl.VERTEX_SHADER], ['fragment', gl.FRAGMENT_SHADER]]) {
              for (const precision of [['lowFloat', gl.LOW_FLOAT], ['mediumFloat', gl.MEDIUM_FLOAT], ['highFloat', gl.HIGH_FLOAT]]) {
                const f = gl.getShaderPrecisionFormat(stage[1], precision[1]);
                precisions[`${stage[0]}.${precision[0]}`] = f ? [f.rangeMin, f.rangeMax, f.precision] : null;
              }
            }
            result.webgl.precisions = precisions;
          } catch (e) {
            result.webgl.error = String(e);
          }

          try {
            const Offline = window.OfflineAudioContext || window.webkitOfflineAudioContext;
            if (!Offline) throw new Error('OfflineAudioContext unavailable');
            const context = new Offline(1, 5000, 44100);
            const oscillator = context.createOscillator();
            oscillator.type = 'triangle';
            oscillator.frequency.value = 10000;
            const compressor = context.createDynamicsCompressor();
            compressor.threshold.value = -50;
            compressor.knee.value = 40;
            compressor.ratio.value = 12;
            compressor.attack.value = 0;
            compressor.release.value = 0.25;
            oscillator.connect(compressor);
            compressor.connect(context.destination);
            oscillator.start(0);
            const rendered = await context.startRendering();
            const data = rendered.getChannelData(0);
            let sample = '';
            for (let i = 0; i < data.length; i += 37) sample += data[i].toFixed(8) + ',';
            result.audio.hash = hashString(sample);
            result.audio.sampleRate = rendered.sampleRate;
            result.audio.length = rendered.length;
          } catch (e) {
            result.audio.error = String(e);
          }

          try {
            const candidates = [
              'Arial', 'Arial Black', 'Calibri', 'Cambria', 'Courier New',
              'Georgia', 'Helvetica', 'Segoe UI', 'Tahoma', 'Times New Roman',
              'Trebuchet MS', 'Verdana', 'Menlo', 'Monaco', 'Ubuntu'
            ];
            const available = candidates.filter(font => document.fonts && document.fonts.check(`12px "${font}"`));
            result.fonts.available = available;
            result.fonts.hash = hashString(available.join('|'));
          } catch (e) {
            result.fonts.error = String(e);
          }

          return result;
        }
        """
    )


def collect_snapshot(page, identity_state: dict[str, Any]) -> dict[str, Any]:
    camou_config = identity_state.get("camou_config", {})
    observed = observed_signals(page)
    snapshot: dict[str, Any] = {
        "schema_version": 3,
        "identity": identity_state.get("metadata", {}).get("identity"),
        "camoufox_config_hash": _sha256_json(camou_config),
        "camoufox_config": camou_config,
        "observed": observed,
    }
    return snapshot


def run_fingerprint_diagnostics(
    cfg: dict[str, Any],
    page,
    identity_state: dict[str, Any],
    run_dir: Path,
    logger,
) -> dict[str, Any]:
    diagnostics = cfg.get("fingerprint_diagnostics", {})
    enabled = bool(diagnostics.get("enabled", False))
    result: dict[str, Any] = {"enabled": enabled}
    if not enabled:
        logger.info("Fingerprint diagnostics: DISABLED")
        return result

    save_snapshot = bool(diagnostics.get("save_snapshot", True))
    compare_with_baseline = bool(diagnostics.get("compare_with_baseline", True))
    update_baseline = bool(diagnostics.get("update_baseline", False))
    fail_on_change = bool(diagnostics.get("fail_on_change", False))

    logger.info("Fingerprint diagnostics: ENABLED")
    snapshot = collect_snapshot(page, identity_state)
    fp_dir = run_dir / "fingerprint"
    if save_snapshot:
        write_json(fp_dir / "snapshot.json", snapshot)

    baseline_path = Path(identity_state["paths"]["root"]) / "fingerprint-baseline.json"
    baseline_existed = baseline_path.exists()
    profile_cfg = identity_state.get("profile_config", {})
    baseline_stale = bool(profile_cfg.get("baseline_stale", False))

    identity_was_updated = bool(identity_state.get("updated", False))
    if baseline_stale:
        write_json(baseline_path, snapshot)
        config_path = Path(identity_state["paths"]["config"])
        refreshed_profile = set_baseline_stale(config_path, identity_state["metadata"]["identity"], False)
        identity_state["profile_config"] = refreshed_profile
        result.update({
            "baseline_path": str(baseline_path),
            "baseline_created": not baseline_existed,
            "baseline_updated": baseline_existed,
            "baseline_stale_before_run": True,
            "baseline_stale": False,
            "compared": False,
            "drift_detected": False,
            "fail_on_change": fail_on_change,
            "reason": "identity profile configuration changed",
        })
        logger.info("Fingerprint baseline was stale after identity profile configuration change")
        logger.info("Fingerprint baseline refreshed for current identity profile: %s", baseline_path)
        return result

    if update_baseline or identity_was_updated or not baseline_existed:
        write_json(baseline_path, snapshot)
        result.update({
            "baseline_path": str(baseline_path),
            "baseline_created": not baseline_existed,
            "baseline_updated": baseline_existed,
            "compared": False,
            "drift_detected": False,
            "fail_on_change": fail_on_change,
            "baseline_stale": False,
        })
        reason = "identity update" if identity_was_updated else ("configuration" if update_baseline else "first snapshot")
        logger.info("Fingerprint baseline saved (%s): %s", reason, baseline_path)
        return result

    if not compare_with_baseline:
        result.update({
            "baseline_path": str(baseline_path),
            "baseline_created": False,
            "baseline_updated": False,
            "compared": False,
            "drift_detected": False,
            "fail_on_change": fail_on_change,
        })
        logger.info("Fingerprint baseline comparison is disabled")
        return result

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline.get("schema_version") != snapshot.get("schema_version"):
        write_json(baseline_path, snapshot)
        result.update({
            "baseline_path": str(baseline_path),
            "baseline_created": False,
            "baseline_updated": True,
            "compared": False,
            "drift_detected": False,
            "fail_on_change": fail_on_change,
            "reason": "diagnostics schema upgrade",
        })
        logger.info(
            "Fingerprint baseline refreshed for diagnostics schema upgrade: %s -> %s",
            baseline.get("schema_version"), snapshot.get("schema_version"),
        )
        return result

    diff = diff_snapshots(baseline, snapshot)
    write_json(fp_dir / "diff.json", diff)

    drift = bool(diff["summary"]["drift_detected"])
    result.update({
        "baseline_path": str(baseline_path),
        "baseline_created": False,
        "baseline_updated": False,
        "compared": True,
        "drift_detected": drift,
        "summary": diff["summary"],
        "diff_file": str(fp_dir / "diff.json"),
        "snapshot_file": str(fp_dir / "snapshot.json") if save_snapshot else None,
        "fail_on_change": fail_on_change,
    })

    summary = diff["summary"]
    if drift:
        logger.warning(
            "Fingerprint drift detected: changed=%s added=%s removed=%s same=%s",
            summary["changed"], summary["added"], summary["removed"], summary["same"],
        )
        for key, values in list(diff["changed"].items())[:20]:
            logger.warning("FP CHANGED %s: %r -> %r", key, values["baseline"], values["current"])
        if len(diff["changed"]) > 20:
            logger.warning("FP diff contains %s additional changed fields; see %s", len(diff["changed"]) - 20, fp_dir / "diff.json")
    else:
        logger.info("Fingerprint persistence check: no drift detected (%s comparable fields)", summary["same"])

    return result
