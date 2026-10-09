# thanmoi-uptime

Monitor ngoài VPS cho KR10 (uptime ≥ 99,5%). Repo công khai CHỈ để GitHub Actions chạy miễn phí; không chứa bí mật.

- `.github/workflows/probe.yml`: cron `*/5` gọi `https://app.thanmoi.vn/api/health` + `https://thanmoi.vn/`; cron `3,33` gọi `/api/health?deep=1`. Kết quả append vào nhánh `data` (`data/YYYY-MM.csv`).
- `probe.sh`: cùng script chạy trên Mac (launchd) làm bản dự phòng.
- `mac-probe.sh` + `~/Library/LaunchAgents/vn.thanmoi.uptime.plist`: bản dự phòng Mac, ghi vào `thanmoi-org/agents/engineering/work/uptime-mac/`.
- `report.sh [--month 2026-10]`: clone nhánh `data` + đọc CSV Mac, chạy `uptime_report.py`.

**Cập nhật 2026-10-06 (THA-3284):** cron GitHub không bao giờ bắn (0 lượt sau ~2 giờ) → đã gỡ `schedule`, workflow chỉ còn `workflow_dispatch`. Nguồn chính nay là Better Stack free (2 monitor: app /api/health keyword `"ok":true`, thanmoi.vn; check 3 phút) — đọc bằng `betterstack_report.sh [YYYY-MM]` (cần `BETTERSTACK_API_TOKEN`). Mac launchd giữ làm dự phòng.

## Hành trình khách trả phí (THA-3746)
`journey.mjs` (Playwright-core + Chromium headless, viewport 390px) chạy MỖI GIỜ (:07, launchd `vn.thanmoi.journey` → `journey-run.sh`):
1. `https://thanmoi.vn/thiep-tat-nien` 200 và ≥10 nút CTA `https://app.thanmoi.vn/app/new?template=<id>`; mọi CTA chuyển (3xx) tới `/app/draft?template=<id>`.
2. Mở `/app/draft?template=<id>` (mẫu xoay theo giờ) trong trình duyệt: HTTP 200, ≥3 JS `/_next/static/` đều <400, không `pageerror`/`console.error`, hiện bảng chỉnh sửa + khung xem trước thiệp có chữ.
3. Tab "Xuất bản" → "Đăng nhập để xuất bản" → cửa đăng nhập có "Tiếp tục với Google" (`/api/auth/google` 302 tới accounts.google.com), `/app/login`, `/app/register` 200.
4. `/api/public/pricing` có bảng giá hợp lệ (wedding, yearend); webhook SePay `POST` không khoá trả 401 (route sống).
Hỏng thì thử lại 1 lần sau 45s; hỏng cả hai → ping `<heartbeat>/fail` (Better Stack mở incident + email ngay). Đạt → ping heartbeat. Heartbeat 505397, period 1h + grace 20 phút (Mac tắt/script chết ⇒ đỏ sau ≤80 phút). URL heartbeat nằm trong `~/.config/thanmoi-uptime.env` (không commit). Log: `thanmoi-org/agents/engineering/work/uptime-mac/journey-YYYY-MM.csv`.
Không ghi gì lên production: không đăng nhập, không tạo đơn/thiệp; chặn host ngoài (Pixel/analytics) và `/api/funnel`; UA chứa `ThanMoiUptimeMonitor` để bộ lọc bot loại khỏi số khách.
**Giới hạn:** KHÔNG kiểm bước tạo đơn/QR thật (cần đăng nhập + ghi `orders` production; không có môi trường staging an toàn) — chỉ kiểm tới trước tạo đơn + bảng giá + webhook sống. Không bắt lỗi chỉ xảy ra sau đăng nhập (lưu thiệp, tải ảnh, nhạc, `adopt`), lỗi riêng thiết bị/trình duyệt khác, lỗi lúc tải cao. Chỉ chạy từ 1 Mac ở VN (không kiểm theo vùng). Một mẫu/giờ đi hết editor; 15 mẫu còn lại chỉ kiểm CTA→draft.
Thử lỗi cục bộ: `FAULT=cta|cta_redirect|editor_js|editor_blank|publish|google|pricing|webhook node test/fault-proxy.mjs` rồi chạy `journey.mjs` với `LANDING_URL=http://127.0.0.1:3901 APP_URL=http://127.0.0.1:3902 PROD_APP_ORIGIN=http://127.0.0.1:3902`.
