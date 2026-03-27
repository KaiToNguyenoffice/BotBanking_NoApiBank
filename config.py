import os
from dotenv import load_dotenv

load_dotenv()

# === Bot ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# === Database ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_shop.db")

# === Payment ===
CASSO_API_KEY = os.getenv("CASSO_API_KEY", "")
BANK_ACCOUNT_NUMBER = os.getenv("BANK_ACCOUNT_NUMBER", "")
BANK_ACCOUNT_NAME = os.getenv("BANK_ACCOUNT_NAME", "")
BANK_NAME = os.getenv("BANK_NAME", "")
BANK_BIN = os.getenv("BANK_BIN", "")  #
MIN_DEPOSIT = int(os.getenv("MIN_DEPOSIT", "10000"))

# === App ===
CURRENCY_SYMBOL = "đ"
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
DAILY_POINTS = 1
BUY_10_GET_2_CATEGORY = "capcut"  
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change_this_secret_123")
# If false: webhook does not require secret (unsafe if URL is public; dev/local only).
WEBHOOK_REQUIRE_SECRET = os.getenv("WEBHOOK_REQUIRE_SECRET", "true").lower() in (
    "1",
    "true",
    "yes",
)
# If true: webhook must include bank SMS with PS:...VND. If false: chỉ cần ref (MacroDroid gửi mã NAP).
WEBHOOK_REQUIRE_PS_LINE = os.getenv("WEBHOOK_REQUIRE_PS_LINE", "false").lower() in (
    "1",
    "true",
    "yes",
)
# If true: chỉ gửi mã NAP vẫn nạp (không đối chiếu số tiền thật — rủi ro chuyển thiếu).
# If false (mặc định): bắt buộc có dòng PS hoặc field amount để so với đơn.
WEBHOOK_ALLOW_REF_ONLY = os.getenv("WEBHOOK_ALLOW_REF_ONLY", "false").lower() in (
    "1",
    "true",
    "yes",
)

# === VietQR ===
VIETQR_TEMPLATE = "compact"  
