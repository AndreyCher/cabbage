from __future__ import annotations
import json, threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

class ControlAPIServer:
    def __init__(self,runtime,host="0.0.0.0",port=8090,logger=None,profile_config_path=None,project_name="unknown",worker_type="unknown"):
        self.runtime=runtime;self.host=host;self.port=int(port);self.logger=logger;self.profile_config_path=Path(profile_config_path) if profile_config_path else None;self.project_name=project_name;self.worker_type=worker_type;self._server=None;self._thread=None
    def start(self):
        runtime=self.runtime; logger=self.logger; cfgpath=self.profile_config_path; project=self.project_name; wtype=self.worker_type
        class H(BaseHTTPRequestHandler):
            server_version="WorkerControlAPI/1.0"
            def log_message(self,fmt,*args):
                if logger: logger.info("API %s",fmt%args)
            def parts(self):return [p for p in urlparse(self.path).path.split("/") if p]
            def out(self,status,payload):
                b=json.dumps(payload,ensure_ascii=False).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
            def body(self):
                try:n=int(self.headers.get("Content-Length","0"));return json.loads(self.rfile.read(n).decode()) if n>0 else None
                except Exception:return None
            def do_GET(self):
                p=self.parts()
                if p==["api","v1","health"]:return self.out(200,{"status":"ok","api_version":"v1","project":project,"component":f"worker-{wtype}","worker_type":wtype})
                base=["api","v1","identities",runtime.identity,"runs"]
                if p==base:return self.out(200,{"runs":[runtime.public_status()]})
                if p==base+["current"] or p==base+[runtime.run_id]:return self.out(200,runtime.public_status())
                if p==["api","v1","identities",runtime.identity,"config"]:
                    if not cfgpath or not cfgpath.is_file():return self.out(404,{"error":"profile_config_unavailable"})
                    try:return self.out(200,json.loads(cfgpath.read_text()))
                    except Exception as exc:return self.out(500,{"error":"profile_config_read_failed","message":str(exc)})
                return self.out(404,{"error":"not_found"})
            def do_PATCH(self):
                p=self.parts(); expected=["api","v1","identities",runtime.identity,"config"]
                if p!=expected:return self.out(404,{"error":"not_found"})
                payload=self.body()
                if not isinstance(payload,dict):return self.out(400,{"error":"malformed_json"})
                if not cfgpath:return self.out(404,{"error":"profile_config_unavailable"})
                current={}
                if cfgpath.is_file():
                    try: current=json.loads(cfgpath.read_text())
                    except Exception: current={}
                def merge(a,b):
                    r=dict(a)
                    for k,v in b.items():r[k]=merge(r[k],v) if k in r and isinstance(r[k],dict) and isinstance(v,dict) else v
                    return r
                current=merge(current,payload);cfgpath.parent.mkdir(parents=True,exist_ok=True);cfgpath.write_text(json.dumps(current,indent=2,ensure_ascii=False));return self.out(200,{"status":"updated","identity":runtime.identity,"applies":"next_run","config":current})
            def do_POST(self):
                p=self.parts();prefix=["api","v1","identities",runtime.identity,"runs",runtime.run_id,"inputs"]
                if len(p)!=len(prefix)+1 or p[:len(prefix)]!=prefix:return self.out(404,{"error":"not_found"})
                payload=self.body()
                if payload is None:return self.out(400,{"error":"malformed_json"})
                key=p[-1];ok,reason=runtime.put_input(key,payload)
                if ok:return self.out(202,{"status":"accepted","identity":runtime.identity,"run_id":runtime.run_id,"key":key})
                return self.out(400 if reason=="invalid_input" else 409 if reason in {"run_finished","input_already_exists"} else 404,{"error":reason,"key":key})
        self._server=ThreadingHTTPServer((self.host,self.port),H);self._thread=threading.Thread(target=self._server.serve_forever,daemon=True);self._thread.start();
        if self.logger:self.logger.info("Control API listening on %s:%d",self.host,self.port)
    def stop(self):
        if self._server:self._server.shutdown();self._server.server_close();self._server=None
        if self._thread:self._thread.join(timeout=2);self._thread=None
