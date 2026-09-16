import json
import tempfile
import unittest
from pathlib import Path

from app.config_loader import ConfigError, load_runtime_config


class ConfigTests(unittest.TestCase):
    def test_identity_merge_launch_priority_and_boolean_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            files = {
                "global.json": {"telephony": {"enabled": False, "operator": {"mcc": "262"}}},
                "local.json": {"telephony": {"operator": {"mnc": "01"}}},
                "profiles/qa.json": {"identity": "qa", "run": {"scenario": "test"}, "telephony": {"operator": {"name": "launch"}}},
                "identities/qa/config.json": {"telephony": {"operator": {"name": "identity", "country_iso": "de"}}},
                "scenarios/test.json": {"actions": []},
                "system.json": {"project": {"name": "test"}, "worker": {"type": "android"}, "paths": {
                    "global_default_config": "global.json", "local_default_config": "local.json",
                    "profiles_dir": "profiles", "global_scenarios_dir": "global-scenarios",
                    "local_scenarios_dir": "scenarios", "identities_dir": "identities", "artifacts_dir": "artifacts"}}
            }
            for name, data in files.items():
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
            cfg, _ = load_runtime_config("qa", base / "system.json")
            self.assertEqual(cfg["telephony"]["operator"], {"mcc": "262", "mnc": "01", "name": "launch", "country_iso": "de"})
            files["profiles/qa.json"]["phone_number_provider"] = {"enabled": "false"}
            (base / "profiles/qa.json").write_text(json.dumps(files["profiles/qa.json"]))
            with self.assertRaises(ConfigError):
                load_runtime_config("qa", base / "system.json")
