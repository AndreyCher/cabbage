"""Verify the single completed run in a fresh QA container without reinstrumenting."""
import json
import logging
import os
from pathlib import Path

from app.android import AndroidDevice
from app.config_loader import load_runtime_config
from app.telephony import resolve_identity

cfg, layout = load_runtime_config(os.environ["WORKER_PROFILE"], os.environ["WORKER_SYSTEM_CONFIG"])
root = Path(layout["artifacts_dir"]) / cfg["identity"] / cfg["run"]["scenario"]
summaries = list(root.glob("*/summary.json"))
assert len(summaries) == 1, "Expected exactly one disposable-worker run"
summary = json.loads(summaries[0].read_text())
assert summary["status"] == "PASS", summary["status"]
assert len(summary["actions"]) == 4 and summary["action_failures"] == 0
assert summary["app_version"] == "0.1.1"
assert summary["recording"]["files"], "Missing video"
for recording in summary["recording"]["files"]:
    assert (summaries[0].parent / recording).stat().st_size > 0
assert (summaries[0].parent / "screenshots/telephony-qa.png").stat().st_size > 0
expected = resolve_identity(cfg["telephony"], cfg["identity"], cfg["phone_number_provider"]["mock_number"])
device = AndroidDevice(cfg, logging.getLogger("qa"))
observed = json.loads(device.adb("shell", "run-as", "org.example.telephonyqa", "cat", "files/telephony.json").stdout)
for key in ("imei", "imsi", "phone_number", "operator", "country_iso"):
    assert observed[key] == expected[key], key
assert observed["numeric"] == expected["mcc"] + expected["mnc"]
assert observed["sim_numeric"] == observed["numeric"]
assert observed["sim_operator"] == expected["operator"]
assert observed["subscription_number"] == expected["phone_number"]
print("PASS: worker lifecycle, real app telephony APIs, mock SMS, screenshot and video", summary["run_id"])
