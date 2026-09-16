from __future__ import annotations
import json, random, time, urllib.request
from pathlib import Path
from typing import Any
from .runtime import FatalActionError, ShutdownRequested

class ActionEngine:
    def __init__(self, device, run_dir:Path, logger, runtime=None, continue_on_error_default=False):
        self.device=device; self.run_dir=run_dir; self.logger=logger; self.runtime=runtime; self.continue_on_error_default=continue_on_error_default

    def _wait(self,a):
        lo=float(a.get("min",a.get("seconds",1))); hi=float(a.get("max",lo)); delay=random.uniform(lo,hi); time.sleep(delay); return {"seconds":round(delay,3)}
    def _webhook(self,a):
        url=a["url"]; method=str(a.get("method","GET")).upper(); headers={str(k):str(v) for k,v in a.get("headers",{}).items()}; body=None
        if "json" in a: body=json.dumps(a["json"]).encode(); headers.setdefault("Content-Type","application/json")
        req=urllib.request.Request(url,data=body,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=float(a.get("timeout_ms",10000))/1000) as r:
                raw=r.read(); ctype=r.headers.get("Content-Type",""); payload=json.loads(raw) if "json" in ctype and raw else raw.decode(errors="replace")
        except Exception as exc: raise FatalActionError(str(exc),reason="webhook_failed") from exc
        if a.get("save_as") and self.runtime: self.runtime.set_webhook_result(a["save_as"],payload)
        return {"status":getattr(r,"status",200),"save_as":a.get("save_as")}
    def execute(self,a,index):
        t=a["type"]
        if t=="wait": return self._wait(a)
        if t=="wait_input":
            key=str(a["key"]); ok,val=self.runtime.wait_for_input(key,float(a.get("timeout_sec",300)))
            if not ok:
                if a.get("on_timeout","fail")=="default": self.runtime.set_default_input(key,a.get("default")); return {"key":key,"default_used":True}
                raise FatalActionError(f"Runtime input {key!r} timed out",reason="input_timeout",details={"key":key})
            return {"key":key,"received":True}
        if t=="webhook": return self._webhook(a)
        if t in {"open","new_tab"}: self.device.open_url(str(a["url"])); return {"url":a["url"]}
        if t=="go_back": self.device.press("BACK"); return {}
        if t=="launch_app": self.device.launch_app(str(a["package"]),a.get("activity")); return {"package":a["package"],"activity":a.get("activity")}
        if t=="click":
            if "selector" in a: self.device.element(str(a["selector"])).click(); return {"selector":a["selector"]}
            if "x" in a and "y" in a: self.device.driver.execute_script("mobile: clickGesture", {"x":int(a["x"]),"y":int(a["y"])}); return {"x":int(a["x"]),"y":int(a["y"])}
            raise ValueError("click requires selector or x/y")
        if t=="tap": self.device.driver.execute_script("mobile: clickGesture", {"x":int(a["x"]),"y":int(a["y"])}); return {"x":int(a["x"]),"y":int(a["y"])}
        if t=="type":
            el=self.device.element(str(a["selector"]));
            if a.get("clear",False): el.clear()
            el.send_keys(str(a.get("text",""))); return {"selector":a["selector"],"length":len(str(a.get("text","")))}
        if t=="press": self.device.press(str(a["key"])); return {"key":a["key"]}
        if t=="screenshot":
            name=str(a.get("name",f"{index:03d}.png")); p=self.run_dir/"screenshots"/name; self.device.screenshot(p); return {"file":str(p)}
        if t=="scroll":
            size=self.device.window_size(); w,h=int(size["width"]),int(size["height"]); direction=str(a.get("direction","down")).lower(); percent=float(a.get("percent",0.7))
            self.device.driver.execute_script("mobile: scrollGesture", {"left":int(w*.1),"top":int(h*.15),"width":int(w*.8),"height":int(h*.7),"direction":direction,"percent":percent})
            return {"direction":direction,"percent":percent}
        if t=="swipe":
            self.device.driver.execute_script("mobile: swipeGesture", {"left":int(a.get("left",0)),"top":int(a.get("top",0)),"width":int(a.get("width",self.device.window_size()["width"])),"height":int(a.get("height",self.device.window_size()["height"])),"direction":str(a.get("direction","up")),"percent":float(a.get("percent",0.75))})
            return {"direction":a.get("direction","up")}
        raise ValueError(f"Unsupported action type: {t}")

    def run(self, actions:list[dict[str,Any]]):
        out=[]
        for index, raw in enumerate(actions,1):
            if self.runtime: self.runtime.raise_if_shutdown_requested(); self.runtime.set_action(index)
            t=raw.get("type","<missing>"); started=time.time(); self.logger.info("ACTION %03d %-20s %s",index,t,raw)
            try:
                a=self.runtime.resolve_value(raw) if self.runtime else raw; data=self.execute(a,index); status="PASS"; self.logger.info("PASS   %03d %-20s",index,t)
            except Exception as exc:
                status="FAIL"; reason=getattr(exc,"reason","action_failed"); data={"error":str(exc) or type(exc).__name__,"reason":reason}; self.logger.error("FAIL   %03d %-20s reason=%s message=%s",index,t,reason,data["error"])
                out.append({"index":index,"type":t,"status":status,"duration_sec":round(time.time()-started,3),"data":data})
                if isinstance(exc, (FatalActionError, ShutdownRequested)):
                    raise
                if not bool(raw.get("continue_on_error",self.continue_on_error_default)):
                    if isinstance(exc,FatalActionError): raise
                    raise FatalActionError(data["error"],reason=reason,details={"failed_action":index,"action_type":t}) from exc
                continue
            out.append({"index":index,"type":t,"status":status,"duration_sec":round(time.time()-started,3),"data":data})
        return out
