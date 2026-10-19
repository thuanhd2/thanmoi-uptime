#!/usr/bin/env bash
# Uptime Better Stack theo cửa sổ 7 ngày (00:00 ngày đầu -> 24:00 ngày thứ 7, giờ VN), chỉ đọc. Cần BETTERSTACK_API_TOKEN.
# Dùng: betterstack_weekly.sh [YYYY-MM-DD ngày đầu tuần scorecard, vd 2026-10-13]   (mặc định: 7 ngày kết thúc lúc 00:00 hôm nay)
# Tuần chưa kết thúc: đọc đến thời điểm hiện tại và ghi "tạm tính".
set -e
: "${BETTERSTACK_API_TOKEN:?thiếu BETTERSTACK_API_TOKEN}"
export MON="${1:-}"
python3 - <<'PY'
import os, json, urllib.request, datetime as dt
A = "https://uptime.betterstack.com/api/v2"
H = {"Authorization": "Bearer " + os.environ["BETTERSTACK_API_TOKEN"]}
def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(A + path, headers=H), timeout=30))
ict = dt.timezone(dt.timedelta(hours=7))
now = dt.datetime.now(dt.timezone.utc)
mon = os.environ.get("MON")
if mon:
    start = dt.datetime.strptime(mon, "%Y-%m-%d").replace(tzinfo=ict)
else:
    today = now.astimezone(ict).replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - dt.timedelta(days=7)
end = start + dt.timedelta(days=7)
partial = end > now
to = min(end, now)
utcd = lambda t: t.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")
span = (to - start).total_seconds()
print("== Better Stack, cửa sổ %s -> %s (giờ VN)%s" % (start.strftime("%d/%m %H:%M"), end.strftime("%d/%m %H:%M"), "  [TẠM TÍNH đến " + to.astimezone(ict).strftime("%d/%m %H:%M") + "]" if partial else ""))
print("   check 3 phút, 4 vùng (eu/us/as/au). (A) = API /sla, tính theo NGÀY UTC %s..%s (không cắt theo giờ); (B) = tự tính từ các sự cố, cắt đúng cửa sổ giờ VN." % (utcd(start), utcd(to - dt.timedelta(seconds=1))))
for m in get("/monitors")["data"]:
    mid, name = m["id"], m["attributes"]["pronounceable_name"]
    s = get("/monitors/%s/sla?from=%s&to=%s" % (mid, utcd(start), utcd(to - dt.timedelta(seconds=1))))["data"]["attributes"]
    inc = []
    page = "/incidents?from=%s&to=%s&per_page=50" % (utcd(start - dt.timedelta(days=1)), utcd(end + dt.timedelta(days=1)))
    while page:
        d = get(page); inc += d["data"]
        nxt = d["pagination"].get("next"); page = nxt.replace(A, "") if nxt else None
    rows, down = [], 0
    for i in inc:
        a = i["attributes"]
        if a["name"] != name: continue
        st = dt.datetime.fromisoformat(a["started_at"].replace("Z", "+00:00"))
        rs = dt.datetime.fromisoformat(a["resolved_at"].replace("Z", "+00:00")) if a["resolved_at"] else now
        lo, hi = max(st, start), min(rs, to)
        if hi <= lo: continue
        d_ = (hi - lo).total_seconds(); down += d_
        rows.append("  - %s ICT  %d s  (%s)%s" % (st.astimezone(ict).strftime("%d/%m %H:%M:%S"), d_, a["cause"], "" if a["resolved_at"] else "  [CHƯA XỬ LÝ XONG]"))
    print("\n%s (%s)" % (name, mid))
    print("  (A) uptime %.3f%% | sự cố %s | tổng down %ss | dài nhất %ss" % (s["availability"], s["number_of_incidents"], s["total_downtime"], s["longest_incident"]))
    print("  (B) uptime %.3f%% | sự cố %d | tổng down %ds" % (100 * (1 - down / span), len(rows), down))
    print("\n".join(rows) if rows else "  (không có sự cố)")
    if s["number_of_incidents"] != len(rows): print("  ! (A) và (B) lệch số sự cố: (A) gộp cả ngày UTC ngoài cửa sổ giờ VN; ưu tiên (B), đối chiếu danh sách trên.")
print("\nGhi chú: tổng down của (A) thường lớn hơn thời lượng sự cố ở (B) (API làm tròn theo chu kỳ check 180 s).")
PY
