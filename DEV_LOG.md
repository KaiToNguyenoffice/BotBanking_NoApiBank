# DEV_LOG

## 2026-03-26 — Initial Build

### Tạo mới
- **Toàn bộ project** Bot Telegram Shop tự động bán hàng kỹ thuật số
- **Database**: SQLite + SQLAlchemy async, 5 bảng (users, products, stock_items, transactions, orders)
- **Services**: product_service (atomic purchase, CRUD, bulk stock), wallet_service (deposit/confirm/reject, balance, history)
- **Handlers**: start, products (xem/mua), wallet (nạp tiền bank transfer), loyalty (điểm danh/đổi CapCut), admin (stats, add product, import stock, duyệt nạp tiền, manual deposit), language (vi/en)
- **Utils**: keyboards (InlineKeyboard builders), formatters (message templates), decorators (admin_only)
- **Entry point**: bot.py với polling mode, auto init DB

### Chi tiết kiến trúc
- Purchase flow: atomic transaction (check balance → grab stock → deduct → create order + tx record)
- Deposit flow: pending → admin approve/reject → credit balance + notify user
- Loyalty: 1 điểm/ngày, đổi 30 điểm = 1 TK CapCut
- Admin panel: /admin command, multi-step flows cho add product và import stock

### Improvement: VietQR Deposit Flow
- Rewrite `handlers/wallet.py`: flow mới nhập số tiền tự do → generate VietQR URL → gửi ảnh QR code + caption + nút "Huỷ đơn"
- Thêm `BANK_BIN`, `MIN_DEPOSIT`, `VIETQR_TEMPLATE` vào `config.py`
- Cập nhật `bot.py`: bỏ các handler deposit cũ (amount selection, method selection), thêm `cancel_deposit_callback`
- VietQR API: `https://img.vietqr.io/image/{BIN}-{STK}-{template}.png?amount=X&addInfo=Y`
