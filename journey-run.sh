#!/usr/bin/env bash
# Chạy journey.mjs mỗi giờ (launchd vn.thanmoi.journey) rồi đẩy kết quả lên Better Stack heartbeat.
# Đạt => ping heartbeat; hỏng (sau 2 lần thử) => ping /fail kèm lý do => Better Stack mở incident + email ngay.
# Mac tắt/ngủ/script chết => heartbeat không được ping => báo đỏ sau period+grace (80 phút).
# Env: JOURNEY_HEARTBEAT_URL (bắt buộc; đọc thêm từ ~/.config/thanmoi-uptime.env), JOURNEY_LOG_DIR.
export PATH="$HOME/.asdf/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -z "$JOURNEY_HEARTBEAT_URL" ] && [ -f "$HOME/.config/thanmoi-uptime.env" ] && . "$HOME/.config/thanmoi-uptime.env"
HB="${JOURNEY_HEARTBEAT_URL:?thiếu JOURNEY_HEARTBEAT_URL}"
OUT="${JOURNEY_LOG_DIR:-/Users/thuanho/projects/thanmoi/thanmoi-org/agents/engineering/work/uptime-mac}"
mkdir -p "$OUT"; f="$OUT/journey-$(date -u +%Y-%m).csv"
[ -f "$f" ] || echo "ts_utc,ok,ms,attempts,failed_step,error" > "$f"
cd "$DIR" || exit 1
res="$(perl -e 'alarm 170; exec @ARGV' node journey.mjs 2>/dev/null)"
[ -n "$res" ] || res='{"ok":false,"ms":0,"attempts":0,"steps":[{"name":"runner","ok":false,"error":"journey.mjs không chạy xong trong 170s hoặc không có kết quả"}]}'
line="$(printf '%s' "$res" | python3 -c '
import sys,json,datetime
d=json.load(sys.stdin);bad=[s for s in d["steps"] if not s["ok"]]
b=bad[0] if bad else {}
e=(b.get("error") or "").replace(",",";").replace("\"","")
print("%s,%s,%s,%s,%s,%s"%(d.get("ts") or datetime.datetime.utcnow().isoformat()+"Z","up" if d["ok"] else "down",d["ms"],d.get("attempts",0),b.get("name",""),e))
print("OK" if d["ok"] else "FAIL")
print(("hành trình hỏng ở bước "+b["name"]+": "+(b.get("error") or "")) if bad else "")
')"
echo "$(printf '%s\n' "$line" | sed -n 1p)" >> "$f"
status="$(printf '%s\n' "$line" | sed -n 2p)"; msg="$(printf '%s\n' "$line" | sed -n 3p)"
if [ "$status" = OK ]; then curl -fsS -m 20 --retry 2 -o /dev/null "$HB"; else curl -fsS -m 20 --retry 2 -o /dev/null --data-raw "$msg" "$HB/fail"; fi
