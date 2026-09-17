from __future__ import annotations
import json, os, shlex, subprocess, time
from pathlib import Path
from typing import Any
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy

KEYCODES = {"BACK":4,"HOME":3,"MENU":82,"ENTER":66,"TAB":61,"ESCAPE":111,"SPACE":62,"DPAD_UP":19,"DPAD_DOWN":20,"DPAD_LEFT":21,"DPAD_RIGHT":22,"DELETE":67}

class AndroidDevice:
    def __init__(self, cfg: dict, logger):
        self.cfg, self.logger, self.driver = cfg, logger, None
        self.telephony = None
        acfg = cfg.get("android", {})
        self.serial = str(acfg.get("serial", "emulator-5554"))
        self.appium_url = str(acfg.get("appium_url", "http://127.0.0.1:4723"))

    def adb(self, *args: str, timeout: float=30, check=True) -> subprocess.CompletedProcess:
        cmd = ["adb", "-s", self.serial, *map(str,args)]
        self.logger.debug("ADB %s", " ".join(shlex.quote(x) for x in cmd))
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=check)

    def wait_ready(self, timeout_sec=180):
        deadline=time.monotonic()+timeout_sec; last=""
        while time.monotonic()<deadline:
            try:
                p=self.adb("shell","getprop","sys.boot_completed",timeout=5,check=False); last=(p.stdout or p.stderr).strip()
                if p.returncode==0 and p.stdout.strip()=="1": return
            except Exception as exc: last=str(exc)
            time.sleep(2)
        raise RuntimeError(f"android_boot_timeout: {last}")

    def connect(self):
        acfg=self.cfg.get("android", {})
        caps = {
            "platformName":"Android", "appium:automationName":"UiAutomator2",
            "appium:deviceName":str(acfg.get("device_name", self.serial)),
            "appium:udid":self.serial, "appium:noReset":bool(acfg.get("no_reset", True)),
            "appium:newCommandTimeout":int(acfg.get("new_command_timeout", 600)),
            "appium:autoGrantPermissions":bool(acfg.get("auto_grant_permissions", True)),
            "appium:adbExecTimeout":int(acfg.get("adb_exec_timeout_ms", 120000)),
            "appium:uiautomator2ServerInstallTimeout":int(acfg.get("uiautomator2_server_install_timeout_ms", 120000)),
        }
        last = None
        deadline = time.monotonic() + int(acfg.get("appium_timeout_sec", 120))
        while time.monotonic() < deadline:
            try:
                self.driver = webdriver.Remote(self.appium_url, options=UiAutomator2Options().load_capabilities(caps))
                return caps
            except Exception as exc:
                last = exc
                time.sleep(2)
        raise RuntimeError(f"appium_session_timeout: {last}")

    def close(self):
        if self.driver:
            try: self.driver.quit()
            finally: self.driver=None

    def open_url(self, url:str):
        self.adb("shell","am","start","-a","android.intent.action.VIEW","-d",url)

    def launch_app(self, package:str, activity:str|None=None, wait=True):
        if self.telephony and self.telephony.launch(package):
            if activity:
                self.adb("shell", "am", "start", "-n", f"{package}/{activity}")
            if wait: time.sleep(0.5)
            return
        if activity:
            component=f"{package}/{activity}"; args=["shell","am","start","-n",component]
        else:
            args=["shell","monkey","-p",package,"-c","android.intent.category.LAUNCHER","1"]
        self.adb(*args)
        if wait: time.sleep(0.5)

    def _parse_selector(self, selector:str):
        prefixes = {
          "id=": AppiumBy.ID, "xpath=": AppiumBy.XPATH, "desc=": AppiumBy.ACCESSIBILITY_ID,
          "accessibility_id=": AppiumBy.ACCESSIBILITY_ID, "class=": AppiumBy.CLASS_NAME,
          "android=": AppiumBy.ANDROID_UIAUTOMATOR,
        }
        for prefix, by in prefixes.items():
            if selector.startswith(prefix): return by, selector[len(prefix):]
        if selector.startswith("text="):
            text=selector[5:].replace('\\','\\\\').replace('"','\\"')
            return AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{text}")'
        if selector.startswith("text_contains="):
            text=selector[14:].replace('\\','\\\\').replace('"','\\"')
            return AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{text}")'
        raise ValueError("Android selector must start with id=, text=, text_contains=, desc=, accessibility_id=, class=, xpath= or android=")

    def element(self, selector:str):
        if not self.driver: raise RuntimeError("appium_session_unavailable")
        by, value=self._parse_selector(selector); return self.driver.find_element(by, value)

    def screenshot(self, path:Path):
        if not self.driver: raise RuntimeError("appium_session_unavailable")
        path.parent.mkdir(parents=True,exist_ok=True); self.driver.save_screenshot(str(path))

    def press(self, key:str):
        if not self.driver: raise RuntimeError("appium_session_unavailable")
        k=key.upper()
        if len(key)==1 and key.isdigit(): code=7+int(key)
        elif k in KEYCODES: code=KEYCODES[k]
        else: raise ValueError(f"Unsupported Android key: {key}")
        self.driver.press_keycode(code)

    def window_size(self):
        return self.driver.get_window_size()
