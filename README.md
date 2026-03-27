# BotBanking_NoApiBank

Bot Telegram Shop (Digital) — nạp tiền qua VietQR + webhook, không dùng API ngân hàng chính thức.

Bot bán hàng kỹ thuật số trên Telegram: đa ngôn ngữ (vi/en), ví nội bộ, VietQR nạp tiền, webhook tự động xác nhận chuyển khoản (ví dụ MacroDroid), mua hàng giao key trong một giao dịch DB, chương trình điểm thưởng, và panel admin trên bot.

## Yêu cầu

- Python **3.10+**
- Kết nối Internet để Telegram Bot API và (tuỳ chọn) VietQR hoạt động

## Công nghệ

| Thành phần | Ghi chú |
|------------|---------|
| `python-telegram-bot` 21.x | Long polling (`run_polling`) |
| SQLAlchemy 2 async + `aiosqlite` | SQLite mặc định |
| `aiohttp` | HTTP server webhook nạp tiền (chạy song song với bot) |
| `python-dotenv` | Đọc `.env` |

## Tính năng chính

- **i18n:** Chuỗi giao diện trong `locales/vi.json`, `locales/en.json`; người dùng chọn ngôn ngữ trong menu.
- **Ví & nạp tiền:** Nhập số tiền tối thiểu theo `MIN_DEPOSIT` → tạo giao dịch `pending` + mã `NAP…` → hiển thị QR VietQR (`img.vietqr.io`) và thông tin chuyển khoản.
- **Webhook nạp tự động:** `POST /webhook/deposit` trên cổng `WEBHOOK_PORT`; đối chiếu mã `NAP` với đơn chờ, kiểm tra số tiền (SMS dòng `PS:…VND` hoặc field `amount` tuỳ cấu hình) → `confirm_deposit` và gửi tin nhắn xác nhận cho user.
- **Mua hàng:** Một luồng DB (khóa user + lấy stock) tránh race khi trừ tiền và giao key; stock là từng dòng `stock_items`, sau khi bán thì xóa bản ghi stock đã giao.
- **Loyalty:** Điểm danh mỗi ngày (`DAILY_POINTS` trong `config.py`); đổi quà CapCut khi đủ điểm (sản phẩm `category == "capcut"` trong DB).
- **Admin:** `/admin` — thống kê, thêm sản phẩm, import kho (nhiều dòng), duyệt/huỷ nạp chờ, nạp tay, tra cứu user, danh sách khách hàng (chỉ `ADMIN_IDS`).

## Cài đặt

```powershell
cd d:\Bot_tele
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Sao chép **`.env.example`** thành **`.env`**, điền giá trị thật (xem bảng dưới). File `.env` không commit được (chứa bí mật). Chỉnh `config.py` nếu cần hằng số kinh doanh (điểm/ngày, template VietQR, v.v.).

```powershell
copy .env.example .env
```

## Biến môi trường (`.env`)

| Biến | Bắt buộc | Mô tả |
|------|----------|--------|
| `BOT_TOKEN` | Có | Token từ [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | Khuyến nghị | Danh sách Telegram user ID, cách nhau dấu phẩy (vd: `123,456`) |
| `DATABASE_URL` | Không | Mặc định `sqlite+aiosqlite:///bot_shop.db` |
| `BANK_BIN` | Có (nạp VietQR) | BIN ngân hàng (VietQR) |
| `BANK_ACCOUNT_NUMBER` | Có | Số tài khoản |
| `BANK_ACCOUNT_NAME` | Có | Tên chủ TK (URL-encode khi gọi VietQR) |
| `BANK_NAME` | Tuỳ | Hiển thị trong tin nhắn hướng dẫn |
| `MIN_DEPOSIT` | Không | Số tiền nạp tối thiểu (VND), mặc định `10000` |
| `WEBHOOK_PORT` | Không | Cổng server webhook, mặc định `8443` |
| `WEBHOOK_SECRET` | Khuyến nghị | Chuỗi bí mật; client gửi kèm (form/json/query/header) |
| `WEBHOOK_REQUIRE_SECRET` | Không | `true`/`false` — nếu `false` không kiểm tra secret (chỉ nên dùng mạng kín/dev) |
| `WEBHOOK_REQUIRE_PS_LINE` | Không | `true` bắt buộc có dòng `PS:…VND` trong nội dung gửi lên |
| `WEBHOOK_ALLOW_REF_ONLY` | Không | `true` cho phép xác nhận chỉ với mã `NAP` (không đối chiếu số tiền — rủi ro) |
| `CASSO_API_KEY` | Không | Được đọc trong `config.py` nhưng **chưa dùng** trong mã nguồn hiện tại |

## Webhook nạp tiền (tích hợp bên ngoài)

- **URL:** `http://<host>:<WEBHOOK_PORT>/webhook/deposit`
- **Method:** `POST`
- **Nội dung:** JSON hoặc form (`application/x-www-form-urlencoded` / `multipart`) với các field tối thiểu: `ref` (hoặc chuỗi chứa mã `NAP…`), `secret` (nếu bật `WEBHOOK_REQUIRE_SECRET`), và tùy chế độ: toàn bộ SMS hoặc `amount` để parse số tiền.
- Secret có thể thay bằng query (`?secret=`), header `X-Webhook-Secret`, hoặc `Authorization: Bearer …` (xem `services/webhook_service.py`).
- Mở cổng / reverse proxy / tunnel (ngrok, v.v.) sao cho thiết bị gửi webhook (điện thoại automation) truy cập được tới máy chạy bot.

## Chạy

```powershell
.\venv\Scripts\activate
python bot.py
```

Bot khởi tạo DB (`init_db`), sau đó bật polling và khởi động webhook server trong `post_init`.

## Lệnh Telegram

| Lệnh | Chức năng |
|------|-----------|
| `/start` | Menu chính, tạo/cập nhật user |
| `/myid` | Hiển thị Telegram ID |
| `/admin` | Panel quản trị (chỉ `ADMIN_IDS`) |

Menu inline: sản phẩm, ví, nạp tiền, điểm danh, đổi thưởng, ngôn ngữ, làm mới; nút API key hiện placeholder (theo locale).

## Cấu trúc thư mục

```
Bot_tele/
├── bot.py              # Đăng ký handler, post_init (DB + webhook)
├── config.py           # Cấu hình từ env + hằng số app
├── requirements.txt
├── database/
│   ├── db.py           # Engine async, init tables
│   └── models.py       # User, Product, StockItem, Transaction, Order
├── handlers/           # start, products, wallet, loyalty, language, admin
├── services/           # wallet_service, product_service, webhook_service
├── utils/              # keyboards, locale, formatters, …
└── locales/            # vi.json, en.json
```

File SQLite mặc định: `bot_shop.db` tại thư mục làm việc khi dùng `DATABASE_URL` mặc định.

## Mô hình dữ liệu (tóm tắt)

- **users:** `telegram_id`, `balance`, `loyalty_points`, `language`, `last_daily`, …
- **products:** giá, `category`, `warranty_hours`, `is_active`, …
- **stock_items:** `data` (key/nội dung giao cho khách), `status` available/sold/…
- **transactions:** deposit / purchase; `status` pending/completed; `payment_ref` (mã `NAP…` cho đơn chờ)
- **orders:** lịch sử giao hàng, `delivered_data`, bảo hành nếu có

---

Chi tiết phát triển có thể xem `DEV_LOG.md`.
