#!/usr/bin/env bash
# Báo cáo uptime: nguồn chính = nhánh data trên GitHub, bổ sung = Mac. Tham số truyền thẳng cho uptime_report.py (vd --month 2026-10).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
git clone -q --depth 1 -b data https://github.com/thuanhd2/thanmoi-uptime.git "$tmp/gh"
python3 "$DIR/uptime_report.py" "$@" "$tmp/gh/data" "${UPTIME_OUT:-/Users/thuanho/projects/thanmoi/thanmoi-org/agents/engineering/work/uptime-mac}"
