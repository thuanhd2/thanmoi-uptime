#!/usr/bin/env python3
"""Sự cố Better Stack còn mở >= MIN_AGE_SEC => tạo issue Paperclip giao Engineering (THA-10037).

Không dùng AI, chỉ stdlib. Chạy bởi launchd vn.thanmoi.incidentwatch (3 phút/lần, incident_watch_run.sh).
Chống trùng 2 lớp: file trạng thái + tìm issue có tiền tố "[BS-<id>]" trong tiêu đề.
Sự cố tự hết => comment vào issue đã tạo. Lỗi bất kỳ => exit 1 (wrapper báo heartbeat /fail).

Env: BETTERSTACK_API_TOKEN, INCIDENT_WATCH_PAPERCLIP_URL, INCIDENT_WATCH_PAPERCLIP_KEY,
     INCIDENT_WATCH_COMPANY_ID, INCIDENT_WATCH_ASSIGNEE_ID (Engineering), INCIDENT_WATCH_CEO_ID (tuỳ chọn),
     INCIDENT_WATCH_STATE (mặc định ~/.local/share/thanmoi-jobs/incident-watch-state.json),
     INCIDENT_WATCH_MIN_AGE_SEC (mặc định 360), INCIDENT_WATCH_DRY_RUN=1, BETTERSTACK_API_BASE.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BS = os.environ.get("BETTERSTACK_API_BASE", "https://uptime.betterstack.com/api/v2").rstrip("/")
MIN_AGE = int(os.environ.get("INCIDENT_WATCH_MIN_AGE_SEC", "360"))
DRY = os.environ.get("INCIDENT_WATCH_DRY_RUN") == "1"
STATE = os.path.expanduser(
    os.environ.get("INCIDENT_WATCH_STATE", "~/.local/share/thanmoi-jobs/incident-watch-state.json"))
ICT = datetime.timezone(datetime.timedelta(hours=7))
SKIP_CAUSES = ("sample incident",)


def need(name):
    v = os.environ.get(name, "")
    if not v:
        raise SystemExit(f"incident_watch: thiếu env {name}")
    return v


def http(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url.split('?')[0]} -> HTTP {e.code} {e.read()[:300]!r}")


def parse_ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_ict(dt):
    return dt.astimezone(ICT).strftime("%H:%M %d/%m")


def bs_get(path, query=""):
    return http("GET", f"{BS}{path}{query}", need("BETTERSTACK_API_TOKEN"))


def open_incidents():
    out, url = [], f"{BS}/incidents?resolved=false"
    while url:
        d = http("GET", url, need("BETTERSTACK_API_TOKEN"))
        out += d["data"]
        url = (d.get("pagination") or {}).get("next")
    return out


class Paperclip:
    def __init__(self):
        self.base = need("INCIDENT_WATCH_PAPERCLIP_URL").rstrip("/")
        self.base = self.base[:-4] if self.base.endswith("/api") else self.base
        self.key = need("INCIDENT_WATCH_PAPERCLIP_KEY")
        self.company = need("INCIDENT_WATCH_COMPANY_ID")

    def call(self, method, path, body=None):
        return http(method, self.base + path, self.key, body)

    def find_issue(self, marker):
        q = urllib.parse.quote(marker)
        for i in self.call("GET", f"/api/companies/{self.company}/issues?q={q}"):
            if marker in i.get("title", ""):
                return i
        return None

    def create(self, title, description):
        body = {"title": title, "description": description, "status": "todo", "priority": "high",
                "assigneeAgentId": need("INCIDENT_WATCH_ASSIGNEE_ID")}
        return self.call("POST", f"/api/companies/{self.company}/issues", body)

    def comment(self, issue_id, text):
        return self.call("POST", f"/api/issues/{issue_id}/comments", {"body": text})


def build_issue(inc, age_s):
    a = inc["attributes"]
    started = parse_ts(a["started_at"])
    marker = f"[BS-{inc['id']}]"
    title = f"{marker} Sự cố Better Stack: {a['name']} — {a['cause']} (từ {fmt_ict(started)} ICT)"
    ceo = os.environ.get("INCIDENT_WATCH_CEO_ID")
    ceo_line = f"Báo: [@CEO](agent://{ceo})\n" if ceo else "Báo: CEO\n"
    content = (a.get("response_content") or "").strip()
    meta = a.get("metadata") or {}
    lines = [
        "Issue tự động (script `incident_watch.py`, không dùng AI). Sự cố đang mở, chưa tự hết.",
        ceo_line,
        f"- Monitor: {a['name']}" + (f" ({meta['Monitor URL']})" if meta.get("Monitor URL") else ""),
        f"- Nguyên nhân Better Stack: {a['cause']}",
        f"- Bắt đầu: {fmt_ict(started)} ICT ({a['started_at']}); đã mở {age_s // 60} phút khi tạo issue",
        f"- Đã ack: {'có' if a.get('acknowledged_at') else 'chưa'}; Better Stack incident id `{inc['id']}`",
    ]
    if meta.get("Response code"):
        lines.append(f"- Mã phản hồi: {meta['Response code']}")
    if content:
        lines += ["", "Thân phản hồi (cắt 1500 ký tự):", "```", content[:1500], "```"]
    lines += ["", "Việc cần làm: xác định ảnh hưởng tới khách, dùng `tools/prod_ops.sh check` / `/api/health`,",
              "ghi vào `incidents/` nếu sự cố ≥ 30 phút hoặc ảnh hưởng doanh thu. Script sẽ comment khi sự cố tự hết."]
    return marker, title, "\n".join(lines)


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=1, sort_keys=True)
    os.replace(tmp, STATE)


def log(msg):
    print(f"{datetime.datetime.now(ICT).isoformat(timespec='seconds')} {msg}")


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    state = load_state()
    incidents = open_incidents()
    pc = None if DRY else Paperclip()
    errors = 0

    for inc in incidents:
        a, iid = inc["attributes"], inc["id"]
        if any(s in (a.get("cause") or "").lower() for s in SKIP_CAUSES):
            continue
        age = int((now - parse_ts(a["started_at"])).total_seconds())
        if age < MIN_AGE or (iid in state and state[iid].get("issue")):
            continue
        marker, title, desc = build_issue(inc, age)
        if DRY:
            log(f"DRY_RUN sẽ tạo issue: {title}")
            continue
        try:
            existing = pc.find_issue(marker)
            if existing:
                state[iid] = {"issue": existing["id"], "identifier": existing.get("identifier"), "resolved": False}
                log(f"đã có issue {existing.get('identifier')} cho {iid}, không tạo lại")
            else:
                made = pc.create(title, desc)
                state[iid] = {"issue": made["id"], "identifier": made.get("identifier"), "resolved": False,
                              "created_at": now.isoformat()}
                log(f"tạo {made.get('identifier')} cho sự cố {iid} (mở {age // 60} phút): {a['name']} / {a['cause']}")
            save_state(state)
        except Exception as e:
            errors += 1
            log(f"LỖI tạo issue cho {iid}: {e}")

    if not DRY:
        open_ids = {i["id"] for i in incidents}
        for iid, s in list(state.items()):
            if s.get("resolved") or iid in open_ids or not s.get("issue"):
                continue
            try:
                a = bs_get(f"/incidents/{iid}")["data"]["attributes"]
                if not a.get("resolved_at"):
                    continue
                dur = int((parse_ts(a["resolved_at"]) - parse_ts(a["started_at"])).total_seconds())
                pc.comment(s["issue"], f"Better Stack báo sự cố `{iid}` đã hết lúc {fmt_ict(parse_ts(a['resolved_at']))} ICT "
                           f"(kéo dài {dur // 3600} giờ {dur % 3600 // 60} phút). Vẫn cần xác định nguyên nhân gốc nếu chưa rõ.")
                s["resolved"] = True
                save_state(state)
                log(f"comment sự cố {iid} đã hết vào {s.get('identifier')}")
            except Exception as e:
                errors += 1
                log(f"LỖI cập nhật sự cố hết {iid}: {e}")

    log(f"xong: {len(incidents)} sự cố mở, lỗi={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        log(f"LỖI: {e}")
        sys.exit(1)
