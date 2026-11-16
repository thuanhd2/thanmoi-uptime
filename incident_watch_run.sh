#!/usr/bin/env bash
# Chạy incident_watch.py (launchd vn.thanmoi.incidentwatch, 3 phút/lần) rồi ping heartbeat của chính nó.
# Thành công => ping INCIDENT_WATCH_HEARTBEAT_URL; lỗi => /fail. Mac tắt/script chết => heartbeat đỏ theo period+grace.
# Env đọc từ ~/.config/thanmoi-uptime.env (không commit); xem incident_watch.py.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
DIR="$(cd "$(dirname "$0")" && pwd)"
set -a; [ -f "$HOME/.config/thanmoi-uptime.env" ] && . "$HOME/.config/thanmoi-uptime.env"; set +a
OUT="${JOURNEY_LOG_DIR:-/Users/thuanho/projects/thanmoi/thanmoi-org/agents/engineering/work/uptime-mac}"
mkdir -p "$OUT"
out="$(/usr/bin/python3 "$DIR/incident_watch.py" 2>&1)"; rc=$?
printf '%s\n' "$out" | grep -v -E '^\S+ xong: [0-9]+ sự cố mở, lỗi=0$' >> "$OUT/incident-watch-$(date -u +%Y-%m).log"
HB="${INCIDENT_WATCH_HEARTBEAT_URL:-}"
if [ -n "$HB" ]; then
  if [ "$rc" = 0 ]; then curl -fsS -m 20 --retry 2 -o /dev/null "$HB"
  else curl -fsS -m 20 --retry 2 -o /dev/null --data-raw "$(printf '%s' "$out" | tail -c 500)" "$HB/fail"; fi
fi
exit "$rc"
