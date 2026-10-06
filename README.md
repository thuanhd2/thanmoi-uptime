# thanmoi-uptime

Monitor ngoài VPS cho KR10 (uptime ≥ 99,5%). Repo công khai CHỈ để GitHub Actions chạy miễn phí; không chứa bí mật.

- `.github/workflows/probe.yml`: cron `*/5` gọi `https://app.thanmoi.vn/api/health` + `https://thanmoi.vn/`; cron `3,33` gọi `/api/health?deep=1`. Kết quả append vào nhánh `data` (`data/YYYY-MM.csv`).
- `probe.sh`: cùng script chạy trên Mac (launchd) làm bản dự phòng.
- `mac-probe.sh` + `~/Library/LaunchAgents/vn.thanmoi.uptime.plist`: bản dự phòng Mac, ghi vào `thanmoi-org/agents/engineering/work/uptime-mac/`.
- `report.sh [--month 2026-10]`: clone nhánh `data` + đọc CSV Mac, chạy `uptime_report.py`.
