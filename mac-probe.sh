#!/usr/bin/env bash
# Bản dự phòng chạy trên Mac (launchd, mỗi 5 phút). Ghi vào $OUT/YYYY-MM.csv; deep mỗi >=30 phút.
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="${UPTIME_OUT:-/Users/thuanho/projects/thanmoi/thanmoi-org/agents/engineering/work/uptime-mac}"
mkdir -p "$OUT"; f="$OUT/$(date -u +%Y-%m).csv"
[ -f "$f" ] || echo "ts_utc,target,http,ms,status,attempts" > "$f"
"$DIR/probe.sh" shallow >> "$f"
stamp="$OUT/.last-deep"
if [ -z "$(find "$stamp" -mmin -29 2>/dev/null)" ]; then "$DIR/probe.sh" deep >> "$f"; touch "$stamp"; fi
