#!/usr/bin/env bash
# Uptime từ Better Stack (nguồn chính cho KR10). Cần BETTERSTACK_API_TOKEN. Dùng: betterstack_report.sh [YYYY-MM]
set -e
month="${1:-$(date -u +%Y-%m)}"
from="${month}-01"
to=$(python3 -c "import datetime,sys;y,m=map(int,'$month'.split('-'));e=datetime.date(y+(m==12),m%12+1,1);print(min(e,datetime.datetime.utcnow().date()+datetime.timedelta(days=1)))")
api=https://uptime.betterstack.com/api/v2
auth="Authorization: Bearer ${BETTERSTACK_API_TOKEN:?thiếu BETTERSTACK_API_TOKEN}"
echo "== Better Stack ($from -> $to, check 3 phút, 4 vùng)"
curl -sf -H "$auth" "$api/monitors" | python3 -c "import sys,json;[print(m['id'],m['attributes']['pronounceable_name']) for m in json.load(sys.stdin)['data']]" |
while read -r id name; do
  curl -sf -H "$auth" "$api/monitors/$id/sla?from=$from&to=$to" | python3 -c "
import sys,json;a=json.load(sys.stdin)['data']['attributes']
print('  %-28s %8.3f%% up  downtime=%ss incidents=%s longest=%ss'%('$name',a['availability'],a['total_downtime'],a['number_of_incidents'],a['longest_incident']))"
done
