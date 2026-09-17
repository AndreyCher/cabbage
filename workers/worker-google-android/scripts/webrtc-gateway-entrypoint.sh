#!/bin/sh
set -eu
cat >/tmp/emulator.ini <<EOF
grpc.port=8554
EOF
# The upstream gateway normally discovers a local emulator.  In our compose
# topology it is a separate service, so route only the gRPC target through DNS.
gateway_source=/opt/aemu/gateway/src/videobridge_gateway/gateway_server.py
sed -i 's|emulator_address = f"localhost:{emulator_port}"|emulator_address = f"{os.environ.get('"'"'EMULATOR_GRPC_HOST'"'"', '"'"'google-emulator'"'"')}:{emulator_port}"|' "$gateway_source"
# Emulator 30.1.2 exposes the legacy android.emulation.control.Rtc service,
# while the current upstream gateway defaults to control.v2.Rtc. Translate
# the small signaling adapter while keeping the browser protocol unchanged.
sed -i \
  -e 's/from \.proto import rtc_service_v2_pb2 as rtc/from .proto import rtc_service_pb2 as rtc/' \
  -e 's/from \.proto import rtc_service_v2_pb2_grpc as rtc_grpc/from .proto import rtc_service_pb2_grpc as rtc_grpc/' \
  -e 's/stream_req = rtc.RtcStreamRequest(ice_server_config=ice_config)/stream_req = ec.google_dot_protobuf_dot_empty__pb2.Empty()/' \
  -e 's/rtc_stub.RequestRtcStream/rtc_stub.requestRtcStream/' \
  -e 's/guid = response.id.guid/guid = response.guid/' \
  -e 's/reader_req = rtc.ReceiveJsepMessageRequest(id=rtc.Id(guid=guid))/reader_req = rtc.RtcId(guid=guid)/' \
  -e 's/rtc_stub.ReceiveJsepMessageStream/rtc_stub.receiveJsepMessages/' \
  -e 's/msg_text = response_msg.jsep_msg.message/msg_text = response_msg.message/' \
  -e 's/send_req = rtc.SendJsepMessageRequest()/send_req = rtc.JsepMsg()/' \
  -e 's/send_req.jsep_msg.id.guid = guid/send_req.id.guid = guid/' \
  -e 's/send_req.jsep_msg.message = json.dumps(client_data)/send_req.message = json.dumps(client_data)/' \
  -e 's/rtc_stub.SendJsepMessage/rtc_stub.sendJsepMessage/' \
  "$gateway_source"
# The legacy emulator emits its own empty {"start": {}} message. The current
# gateway already sends a richer start message containing the STUN config, so
# forwarding both makes the browser initialize the peer connection twice.
sed -i '/parsed_jsep = json.loads(msg_text)/a\                    if "start" in parsed_jsep:\n                        continue' "$gateway_source"
exec videobridge-gateway --port=8080 --discovery_file=/tmp/emulator.ini
