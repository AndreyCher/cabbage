"""Minimal, self-owned WebRTC-debug-UI backend for worker-google-android.

Talks to the official emulator's EmulatorController gRPC service directly
(getStatus, setPhysicalModel for GPS, sendKey for hardware buttons,
streamScreenshot for a live view). This intentionally does not use the
image's legacy "android.emulation.control.Rtc" service: that service never
actually returns an SDP answer or ICE candidates for a real browser peer
connection (verified by direct gRPC probing), so a real WebRTC video path is
not available on this pinned emulator image. streamScreenshot gives a real,
if lower-frame-rate, live view instead.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "proto"))

import grpc
from aiohttp import web
from google.protobuf import empty_pb2

import emulator_controller_pb2 as ec
import emulator_controller_pb2_grpc as ec_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d (%(funcName)s): %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

EMULATOR_CHANNEL: "grpc.aio.Channel | None" = None

# Only the documented Android-mapped w3c KeyboardEvent.key values
# (see emulator_controller.proto's KeyboardEvent.key docs) plus volume keys.
ALLOWED_KEYS = {"GoHome", "GoBack", "AppSwitch", "Power", "AudioVolumeUp", "AudioVolumeDown"}


async def handle_status(request: web.Request) -> web.Response:
    stub = ec_grpc.EmulatorControllerStub(EMULATOR_CHANNEL)
    try:
        status = await stub.getStatus(empty_pb2.Empty())
        return web.json_response(
            {
                "version": status.version,
                "uptime": status.uptime,
                "booted": status.booted,
            }
        )
    except grpc.RpcError as exc:
        logging.error("Error fetching status from emulator: %s", exc)
        return web.json_response({"error": str(exc)}, status=502)


async def handle_gps(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        latitude = float(data.get("latitude", 0.0))
        longitude = float(data.get("longitude", 0.0))
        altitude = float(data.get("altitude", 0.0))
    except (ValueError, TypeError):
        return web.json_response({"error": "invalid_gps_payload"}, status=400)

    stub = ec_grpc.EmulatorControllerStub(EMULATOR_CHANNEL)
    try:
        req = ec.PhysicalModelValue(
            target=ec.PhysicalModelValue.PhysicalType.POSITION,
            value=ec.ParameterValue(data=[longitude, latitude, altitude]),
        )
        await stub.setPhysicalModel(req)
        return web.json_response({"status": "success"})
    except grpc.RpcError as exc:
        logging.error("Error setting GPS on emulator: %s", exc)
        return web.json_response({"error": str(exc)}, status=502)


async def handle_key(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        key = str(data.get("key", ""))
    except (ValueError, TypeError):
        return web.json_response({"error": "invalid_key_payload"}, status=400)

    if key not in ALLOWED_KEYS:
        return web.json_response({"error": "unsupported_key", "allowed": sorted(ALLOWED_KEYS)}, status=400)

    stub = ec_grpc.EmulatorControllerStub(EMULATOR_CHANNEL)
    try:
        req = ec.KeyboardEvent(eventType=ec.KeyboardEvent.KeyEventType.keypress, key=key)
        await stub.sendKey(req)
        return web.json_response({"status": "sent", "key": key})
    except grpc.RpcError as exc:
        logging.error("Error sending key %r to emulator: %s", key, exc)
        return web.json_response({"error": str(exc)}, status=502)


async def handle_screen_stream(request: web.Request) -> web.StreamResponse:
    """Live-ish screen view as a multipart/x-mixed-replace PNG stream.

    Uses the emulator's push-based streamScreenshot RPC (a new frame is
    delivered whenever the device produces one), rather than polling.
    """
    resp = web.StreamResponse(
        status=200,
        headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame"},
    )
    await resp.prepare(request)
    stub = ec_grpc.EmulatorControllerStub(EMULATOR_CHANNEL)
    img_format = ec.ImageFormat(format=ec.ImageFormat.ImgFormat.PNG)
    try:
        async for image in stub.streamScreenshot(img_format):
            if not image.image:
                continue
            header = (
                b"--frame\r\n"
                b"Content-Type: image/png\r\n"
                b"Content-Length: " + str(len(image.image)).encode() + b"\r\n\r\n"
            )
            await resp.write(header)
            await resp.write(image.image)
            await resp.write(b"\r\n")
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    except grpc.RpcError as exc:
        logging.info("Screenshot stream ended: %s", exc)
    except Exception:
        logging.exception("Unexpected error in screenshot stream")
    return resp


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def init_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/api/v1/emulator/status", handle_status)
    app.router.add_post("/api/v1/emulator/gps", handle_gps)
    app.router.add_post("/api/v1/emulator/key", handle_key)
    app.router.add_get("/api/v1/emulator/screen.mjpeg", handle_screen_stream)
    return app


async def main() -> None:
    parser = argparse.ArgumentParser(description="worker-google-android debug gateway")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--emulator-host", default=os.environ.get("EMULATOR_GRPC_HOST", "google-emulator"))
    parser.add_argument("--emulator-port", type=int, default=int(os.environ.get("EMULATOR_GRPC_PORT", "8554")))
    args = parser.parse_args()

    global EMULATOR_CHANNEL
    emulator_address = f"{args.emulator_host}:{args.emulator_port}"
    logging.info("Connecting to Emulator gRPC service at: %s", emulator_address)
    EMULATOR_CHANNEL = grpc.aio.insecure_channel(emulator_address)

    app = init_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", args.port)
    await site.start()
    logging.info("Gateway webserver listening on http://0.0.0.0:%d", args.port)

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        pass
    finally:
        logging.info("Shutting down gateway channel.")
        await EMULATOR_CHANNEL.close()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
