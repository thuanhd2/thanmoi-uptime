# thanmoi-uptime

Monitor ngoài VPS cho KR10 (uptime ≥ 99,5%). Repo công khai CHỈ để GitHub Actions chạy miễn phí; không chứa bí mật.

- `.github/workflows/probe.yml`: cron `*/5` gọi `https://app.thanmoi.vn/api/health` + `https://thanmoi.vn/`; cron `3,33` gọi `/api/health?deep=1`. Kết quả append vào nhánh `data` (`data/YYYY-MM.csv`).
- `probe.sh`: cùng script chạy trên Mac (launchd) làm bản dự phòng.
- `mac-probe.sh` + `~/Library/LaunchAgents/vn.thanmoi.uptime.plist`: bản dự phòng Mac, ghi vào `thanmoi-org/agents/engineering/work/uptime-mac/`.
- `report.sh [--month 2026-10]`: clone nhánh `data` + đọc CSV Mac, chạy `uptime_report.py`.

**Cập nhật 2026-10-06 (THA-3284):** cron GitHub không bao giờ bắn (0 lượt sau ~2 giờ) → đã gỡ `schedule`, workflow chỉ còn `workflow_dispatch`. Nguồn chính nay là Better Stack free (2 monitor: app /api/health keyword `"ok":true`, thanmoi.vn; check 3 phút) — đọc bằng `betterstack_report.sh [YYYY-MM]` (cần `BETTERSTACK_API_TOKEN`). Mac launchd giữ làm dự phòng.
