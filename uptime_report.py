#!/usr/bin/env python3
"""Báo cáo uptime từ CSV probe (ts_utc,target,http,ms,status,attempts).

Mỗi mục tiêu chia thành các ô 5 phút. Ô có mẫu 'down' => down; có mẫu và không down => up;
không có mẫu => không rõ (KHÔNG tính là up). uptime% = up/(up+down); coverage% = (up+down)/tổng ô.
Nhiều nguồn: nguồn đứng trước thắng; nguồn sau chỉ lấp ô nguồn trước không rõ.

  uptime_report.py [--start YYYY-MM-DD] [--tz 7] [--end ISO] [--month 2026-10] FILE_OR_DIR [FILE_OR_DIR ...]
"""
import argparse, csv, glob, os, sys
from datetime import datetime, timedelta, timezone

SLOT = 300

def load(paths):
    rows = []
    for p in paths:
        files = sorted(glob.glob(os.path.join(p, "*.csv"))) if os.path.isdir(p) else [p]
        src = []
        for f in files:
            with open(f, newline="") as fh:
                for r in csv.DictReader(fh):
                    try:
                        t = datetime.strptime(r["ts_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    except (ValueError, KeyError, TypeError):
                        continue
                    src.append((t, r["target"], r["status"] == "up"))
        rows.append(src)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--start", help="YYYY-MM-DD (theo --tz); mặc định = mẫu đầu tiên của bất kỳ nguồn nào")
    ap.add_argument("--end", help="ISO UTC, mặc định = bây giờ")
    ap.add_argument("--tz", type=float, default=7, help="múi giờ nhóm theo ngày (mặc định +7 ICT)")
    ap.add_argument("--month", help="chỉ in tổng tháng này (YYYY-MM)")
    a = ap.parse_args()

    tz = timezone(timedelta(hours=a.tz))
    sources = load(a.paths)
    allts = [t for src in sources for t, _, _ in src]
    if a.start:
        start = datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=tz).astimezone(timezone.utc)
    elif allts:
        start = min(allts)
    else:
        sys.exit("chưa có dữ liệu")
    end = datetime.fromisoformat(a.end.replace("Z", "+00:00")) if a.end else datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    s0 = int(start.timestamp()) // SLOT
    s1 = int(end.timestamp()) // SLOT  # ô đang chạy dở không tính

    per = {}  # target -> {slot: (state, src_idx)}
    for i, src in enumerate(sources):
        tmp = {}
        for t, tgt, up in src:
            s = int(t.timestamp()) // SLOT
            if s0 <= s < s1:
                k = (tgt, s)
                tmp[k] = tmp.get(k, True) and up
        for (tgt, s), up in tmp.items():
            d = per.setdefault(tgt, {})
            if s not in d:
                d[s] = (up, i)

    def fmt(up, down, total):
        known = up + down
        u = f"{100*up/known:.3f}%" if known else "n/a"
        c = f"{100*known/total:.1f}%" if total else "n/a"
        return f"{u:>9} up={up} down={down} unknown={total-known} coverage={c}"

    print(f"Khoảng đo: {start:%Y-%m-%d %H:%M}Z -> {datetime.fromtimestamp(s1*SLOT, timezone.utc):%Y-%m-%d %H:%M}Z  (ngày theo UTC{a.tz:+g})")
    print("uptime% = up/(up+down); ô 5 phút không có mẫu = không rõ, không tính up\n")
    for tgt in sorted(per) or ["(chưa có dữ liệu)"]:
        d = per.get(tgt, {})
        # từng ngày + tổng tháng
        days, months = {}, {}
        for s in range(s0, s1):
            dt = datetime.fromtimestamp(s * SLOT, timezone.utc).astimezone(tz)
            st = d.get(s)
            for bucket, key in ((days, dt.strftime("%Y-%m-%d")), (months, dt.strftime("%Y-%m"))):
                c = bucket.setdefault(key, [0, 0, 0])
                c[2] += 1
                if st:
                    c[0 if st[0] else 1] += 1
        print(f"== {tgt}")
        if not a.month:
            for k, (u, dn, tot) in sorted(days.items()):
                print(f"  {k}  {fmt(u, dn, tot)}")
        for k, (u, dn, tot) in sorted(months.items()):
            if not a.month or k == a.month:
                print(f"  THÁNG {k}  {fmt(u, dn, tot)}")
        print()

if __name__ == "__main__":
    main()
