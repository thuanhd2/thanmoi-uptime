#!/usr/bin/env bash
# Usage: probe.sh shallow|deep  -> prints CSV lines: ts_utc,target,http,ms,status,attempts
# status=up khi HTTP 200 (và với health: body có "ok":true); down nếu 2 lần thử đều lỗi (cách nhau 10s).
set -u
mode="${1:-shallow}"
if [ "$mode" = deep ]; then
  targets="health_deep|https://app.thanmoi.vn/api/health?deep=1|json"
else
  targets="health|https://app.thanmoi.vn/api/health|json
landing|https://thanmoi.vn/|none"
fi
body=$(mktemp); trap 'rm -f "$body"' EXIT
while IFS='|' read -r name url check; do
  [ -z "$name" ] && continue
  status=down; attempts=0; code=000; ms=0
  for try in 1 2; do
    attempts=$try
    out=$(curl -s -o "$body" -w '%{http_code} %{time_total}' -m 20 -A 'thanmoi-uptime/1' "$url" 2>/dev/null) || out="000 20"
    code=${out% *}; secs=${out#* }
    ms=$(awk -v s="$secs" 'BEGIN{printf "%d", s*1000}')
    if [ "$code" = 200 ]; then
      if [ "$check" = json ] && ! grep -q '"ok" *: *true' "$body"; then :; else status=up; break; fi
    fi
    [ "$try" = 1 ] && sleep 10
  done
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),$name,$code,$ms,$status,$attempts"
done <<< "$targets"
