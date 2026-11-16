#!/usr/bin/env python3
"""Thử incident_watch.py với Better Stack + Paperclip giả (không gọi mạng ngoài). Chạy: python3 test/incident_watch_test.py"""
import datetime, json, os, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
now = datetime.datetime.now(datetime.timezone.utc)
iso = lambda m: (now - datetime.timedelta(minutes=m)).isoformat().replace("+00:00", "Z")

def inc(i, mins, cause="Status 503", resolved=None):
    return {"id": i, "attributes": {"name": "app.thanmoi.vn /api/health", "cause": cause, "started_at": iso(mins),
            "resolved_at": resolved, "acknowledged_at": None, "response_content": '{"ok":false}',
            "metadata": {"Monitor URL": "https://app.thanmoi.vn/api/health", "Response code": "503"}}}

S = {"open": [], "single": {}, "issues": [], "comments": [], "creates": 0, "fail_create": False}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = self.path
        if p.startswith("/bs/incidents?"): return self.send(200, {"data": S["open"], "pagination": {"next": None}})
        if p.startswith("/bs/incidents/"): return self.send(200, {"data": S["single"].get(p.rsplit("/", 1)[1]) or inc(p.rsplit("/", 1)[1], 10)})
        if "/issues?q=" in p:
            q = p.split("q=", 1)[1].replace("%5B", "[").replace("%5D", "]")
            return self.send(200, [i for i in S["issues"] if q in i["title"]])
        self.send(404, {})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/issues"):
            if S["fail_create"]: return self.send(500, {"error": "x"})
            S["creates"] += 1; i = {"id": f"uuid{S['creates']}", "identifier": f"THA-{9000 + S['creates']}", **body}
            S["issues"].append(i); return self.send(201, i)
        S["comments"].append((self.path, body)); self.send(201, {})

srv = HTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = tempfile.mkdtemp()
env = {**os.environ, "BETTERSTACK_API_TOKEN": "t", "BETTERSTACK_API_BASE": f"http://127.0.0.1:{port}/bs",
       "INCIDENT_WATCH_PAPERCLIP_URL": f"http://127.0.0.1:{port}", "INCIDENT_WATCH_PAPERCLIP_KEY": "k",
       "INCIDENT_WATCH_COMPANY_ID": "c1", "INCIDENT_WATCH_ASSIGNEE_ID": "eng", "INCIDENT_WATCH_CEO_ID": "ceo",
       "INCIDENT_WATCH_STATE": os.path.join(tmp, "state.json")}

def run(extra=None):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "incident_watch.py")], env={**env, **(extra or {})},
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr

fails = []
def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

S["open"] = [inc("1", 2), inc("2", 7), inc("3", 30, cause="Sample incident")]
rc, out = run(); check("chỉ tạo cho sự cố >= 6 phút, bỏ Sample", rc == 0 and S["creates"] == 1)
i = S["issues"][0]
check("giao Engineering, high, todo, có marker và thân phản hồi",
      i["assigneeAgentId"] == "eng" and i["priority"] == "high" and i["status"] == "todo"
      and i["title"].startswith("[BS-2]") and '{"ok":false}' in i["description"] and "agent://ceo" in i["description"])
rc, out = run(); check("chạy lại không tạo trùng (state)", S["creates"] == 1)
os.remove(env["INCIDENT_WATCH_STATE"]); rc, out = run()
check("mất state vẫn không tạo trùng (tìm theo tiêu đề)", rc == 0 and S["creates"] == 1)
S["open"] = [inc("4", 1)]; run(); check("sự cố 1 phút chưa tạo", S["creates"] == 1)
S["open"] = [inc("5", 9)]; S["fail_create"] = True
rc, out = run(); check("tạo lỗi => exit 1 và không ghi state", rc == 1 and "5" not in json.load(open(env["INCIDENT_WATCH_STATE"])))
S["fail_create"] = False; rc, out = run(); check("lần sau thử lại được", rc == 0 and S["creates"] == 2)
S["open"] = []; S["single"] = {"2": inc("2", 7, resolved=iso(1)), "5": inc("5", 9, resolved=iso(0))}
rc, out = run(); check("hết sự cố => comment 1 lần mỗi issue", rc == 0 and len(S["comments"]) == 2)
rc, out = run(); check("không comment lặp", len(S["comments"]) == 2)
S["open"] = [inc("6", 20)]; n = S["creates"]
rc, out = run({"INCIDENT_WATCH_DRY_RUN": "1", "INCIDENT_WATCH_PAPERCLIP_KEY": ""})
check("DRY_RUN không gọi Paperclip", rc == 0 and S["creates"] == n and "DRY_RUN" in out)
rc, out = run({"BETTERSTACK_API_BASE": "http://127.0.0.1:1/bs"}); check("Better Stack lỗi => exit 1", rc == 1)
print("TẤT CẢ ĐẠT" if not fails else f"{len(fails)} LỖI"); sys.exit(1 if fails else 0)
