"""Run inside the QA container after tests/qa-app/build.sh."""
import json
import logging
import time

from app.android import AndroidDevice
from app.telephony import TelephonySession, resolve_identity

cfg = {"enabled": True, "packages": ["org.example.telephonyqa"],
       "operator": {"name": "QA Germany", "mcc": "262", "mnc": "01", "country_iso": "de"},
       "phone_number": "+4915112345678"}
values = resolve_identity(cfg, "telephony-smoke")
device = AndroidDevice({}, logging.getLogger("qa"))
session = TelephonySession(device, cfg, values)
try:
    device.adb("shell", "pm", "clear", "org.example.telephonyqa")
    session.start()
    session.launch("org.example.telephonyqa")
    deadline = time.monotonic() + 30
    observed = None
    while time.monotonic() < deadline:
        result = device.adb("shell", "run-as", "org.example.telephonyqa", "cat", "files/telephony.json", check=False)
        if result.returncode == 0:
            observed = json.loads(result.stdout)
            break
        time.sleep(.2)
    assert observed is not None, "QA application did not produce a result"
    for key in ("imei", "imsi", "phone_number", "operator", "country_iso"):
        assert observed[key] == values[key], key
    assert observed["numeric"] == values["mcc"] + values["mnc"]
    assert observed["sim_numeric"] == observed["numeric"]
    assert observed["sim_operator"] == values["operator"]
    assert observed["subscription_number"] == values["phone_number"]
    print("PASS: real Android application observed all configured telephony fields")
finally:
    session.close()
