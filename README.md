# thanmoi-uptime

Monitor ngoài VPS cho KR10 (uptime ≥ 99,5%). Repo công khai CHỈ để GitHub Actions chạy miễn phí; không chứa bí mật.

- `.github/workflows/probe.yml`: cron `*/5` gọi `https://app.thanmoi.vn/api/health` + `https://thanmoi.vn/`; cron `3,33` gọi `/api/health?deep=1`. Kết quả append vào nhánh `data` (`data/YYYY-MM.csv`).
- `probe.sh`: cùng script chạy trên Mac (launchd) làm bản dự phòng.
- `uptime_report.py`: tính uptime theo ngày/tháng. `git fetch origin data && git --work-tree=... ` hoặc `gh api`/clone nhánh `data` rồi: `./uptime_report.py <thư-mục-data> [<csv-mac>]`.
