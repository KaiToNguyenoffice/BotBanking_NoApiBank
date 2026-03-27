import json
import logging
import re
from urllib.parse import parse_qs

from aiohttp import web
from telegram.constants import ParseMode

from database.db import async_session
from services.wallet_service import confirm_deposit
from utils.keyboards import main_menu_keyboard
from utils.locale import get_user_lang
from config import (
    WEBHOOK_SECRET,
    WEBHOOK_PORT,
    WEBHOOK_REQUIRE_SECRET,
    WEBHOOK_REQUIRE_PS_LINE,
    WEBHOOK_ALLOW_REF_ONLY,
)
from database.models import Transaction, User
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Literal values MacroDroid sends when Magic Text was typed by hand or not expanded in HTTP body.
_KNOWN_PLACEHOLDERS = frozenset(
    s.lower()
    for s in (
        "[not_body]",
        "[not_text]",
        "[notification_text]",
        "{notification_text}",
        "%notification_text%",
    )
)


def _looks_like_unexpanded_magic_text(ref_raw: str, amount_raw: str) -> bool:
    r, a = (ref_raw or "").strip(), (amount_raw or "").strip()
    if not r or not a:
        return False
    if r != a:
        return False
    if r.lower() in _KNOWN_PLACEHOLDERS:
        return True
    if r.startswith("%") and r.endswith("%") and (
        "notification" in r.lower() or len(r) < 48
    ):
        return True
    if "{notification" in r.lower() and r.endswith("}"):
        return True
    # Typed "[something]" but not a real bank message (no NAP, no digits)
    if r.startswith("[") and r.endswith("]") and "nap" not in r.lower():
        if not any(ch.isdigit() for ch in r):
            return True
    return False



_RE_PS_VND = re.compile(r"PS:\s*[+]?\s*([\d.,]+)\s*VND", re.IGNORECASE)


def _parse_ps_line_amount(text: str) -> float | None:
    """Số tiền dòng PS: trong tin nhắn ngân hàng."""
    m = _RE_PS_VND.search(text or "")
    if not m:
        return None
    raw = m.group(1).replace(",", "").replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_plain_amount(s: str) -> float | None:
    """
    Số từ field amount thuần (MacroDroid): '20.000', '1.000.000', '20000'.
    Coi dấu . và , là phân nghìn (VND).
    """
    s = (s or "").strip()
    if not s:
        return None
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    raw = s.replace(",", "").replace(".", "")
    if not raw.isdigit():
        return None
    try:
        return float(raw)
    except ValueError:
        return None


# Chấp nhận khi số tiền nhận >= số tiền đơn (cho phép lệch làm tròn ±10đ)
WEBHOOK_AMOUNT_TOLERANCE = 10.0


def _is_underpayment(received: float, order: float, tol: float = WEBHOOK_AMOUNT_TOLERANCE) -> bool:
    """True nếu thiếu tiền so với đơn (nhỏ hơn order - tol)."""
    return float(received) + tol < float(order)


_SECRET_FORM_KEYS = ("secret", "webhook_secret", "key", "token", "sig", "k")


def _dict_from_form_payload(payload) -> dict:
    """Single-valued form fields from aiohttp request.post()."""

    def pick(key: str) -> str:
        v = payload.get(key)
        return "" if v is None else str(v)

    secret = ""
    for k in _SECRET_FORM_KEYS:
        secret = pick(k)
        if secret:
            break
    return {"secret": secret, "ref": pick("ref"), "amount": pick("amount")}


async def _load_webhook_payload(request: web.Request) -> dict | None:
    """
    JSON body (application/json) or form (application/x-www-form-urlencoded / multipart).
    MacroDroid often sends empty/wrong JSON when using Magic Text in raw JSON; form fields are safer.
    """
    ct = (request.headers.get("Content-Type") or "").split(";")[0].strip().lower()

    if ct == "application/x-www-form-urlencoded":
        try:
            payload = await request.post()
            data = _dict_from_form_payload(payload)
            logger.info(f"Incoming Webhook (form): secret present={bool(data.get('secret'))}")
            return data
        except Exception as e:
            logger.error(f"Failed to parse form body: {e}")
            return None

    if ct.startswith("multipart/") and "form-data" in ct:
        try:
            payload = await request.post()
            data = _dict_from_form_payload(payload)
            logger.info(f"Incoming Webhook (multipart): secret present={bool(data.get('secret'))}")
            return data
        except Exception as e:
            logger.error(f"Failed to parse multipart body: {e}")
            return None

    try:
        text = await request.text()
    except Exception as e:
        logger.error(f"Failed to read body: {e}")
        return None

    if not text.strip():
        logger.error(f"Empty webhook body (Content-Type={ct!r})")
        return None

    if "application/json" in ct or ct in ("", "text/plain") or text.lstrip().startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                logger.info("Incoming Webhook (JSON dict)")
                return data
            logger.error(f"JSON root is not an object: {type(data)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}; body[:240]={text[:240]!r}")

    if "=" in text and "\r" not in text[:80]:
        qs = parse_qs(text.strip(), keep_blank_values=True)

        def pick(k: str) -> str:
            v = qs.get(k)
            return v[0] if v else ""

        secret = ""
        for sk in _SECRET_FORM_KEYS:
            secret = pick(sk)
            if secret:
                break
        data = {"secret": secret, "ref": pick("ref"), "amount": pick("amount")}
        if data["secret"] or data["ref"] or data["amount"]:
            logger.info("Incoming Webhook (parsed as x-www-form-urlencoded without header)")
            return data

    return None


def _merge_secret_from_request(request: web.Request, data: dict) -> None:
    """
    Some clients (e.g. MacroDroid) drop or mishandle the form field 'secret' while ref/amount arrive.
    Accept secret from: JSON/body aliases, query (?secret= or ?k= / ?key= / ?token=), or headers.
    """
    if data.get("secret"):
        return
    # JSON body may use key/token instead of secret
    for alt in _SECRET_FORM_KEYS[1:]:  # skip duplicate 'secret'
        v = data.get(alt)
        if v:
            data["secret"] = str(v).strip()
            logger.info(f"Webhook: secret from body key {alt!r}")
            return
    for qname in _SECRET_FORM_KEYS:
        q = request.rel_url.query.get(qname)
        if q:
            data["secret"] = q.strip()
            logger.info(f"Webhook: secret from query param {qname!r}")
            return
    h = request.headers.get("X-Webhook-Secret") or request.headers.get("x-webhook-secret")
    if h:
        data["secret"] = h.strip()
        logger.info("Webhook: secret from X-Webhook-Secret header")
        return
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        data["secret"] = auth[7:].strip()
        logger.info("Webhook: secret from Authorization Bearer")


async def handle_deposit_webhook(request):
    """
    Handle POST request from MacroDroid.
    ref required. Need PS line or amount field to verify received >= order, unless WEBHOOK_ALLOW_REF_ONLY=true.
    """
    data = await _load_webhook_payload(request)
    if data is None:
        return web.Response(
            text="Invalid or empty body. Use JSON or form: secret, ref, amount.",
            status=400,
        )
    _merge_secret_from_request(request, data)
    logger.info(f"Incoming Webhook Raw Data: {data}")

    # 1. Verify secret (optional when WEBHOOK_REQUIRE_SECRET=false — not for public URLs)
    if WEBHOOK_REQUIRE_SECRET:
        if data.get("secret") != WEBHOOK_SECRET:
            logger.warning(f"Unauthorized webhook attempt with secret: {data.get('secret')}")
            return web.Response(text="Unauthorized", status=401)
    elif not data.get("secret"):
        logger.warning(
            "Webhook accepted without secret (WEBHOOK_REQUIRE_SECRET=false); restrict access e.g. firewall/ngrok only."
        )

    ref_raw = data.get("ref", "")
    amount_raw = data.get("amount", "")

    if not ref_raw:
        return web.Response(text="Missing ref", status=400)

    if amount_raw and _looks_like_unexpanded_magic_text(str(ref_raw), str(amount_raw)):
        logger.warning(
            "MacroDroid sent an unexpanded placeholder as ref/amount (copy-paste or wrong Magic Text). "
            f"ref={ref_raw!r}"
        )
        return web.Response(
            text=(
                "Lỗi MacroDroid: ref/amount vẫn là placeholder. "
                "Không copy [not_body] từ tài liệu. "
                "Chèn Magic Text từ nút trong ô JSON, hoặc dùng hành động Đặt biến chuỗi + HTTP (xem macrodroid_guide.md)."
            ),
            status=400,
        )

    combined = f"{ref_raw} {amount_raw}"
    # Regex to find mã nạp: NAP + 8 digits/letters
    ref_match = re.search(r"NAP[A-Z0-9]{8,}", combined, re.IGNORECASE)

    if not ref_match:
        logger.warning(f"Could not extract NAP code from: {ref_raw}")
        return web.Response(text="Mã nạp không hợp lệ hoặc thiếu", status=400)

    ref = ref_match.group(0).upper()

    amount_from_body: float | None = None
    if (amount_raw or "").strip():
        amount_from_body = _parse_ps_line_amount(combined)
        if amount_from_body is None:
            amount_match = re.search(r"\+([\d,.]+)", combined)
            if amount_match:
                amount_str = amount_match.group(1).replace(",", "").replace(".", "")
                amount_from_body = float(amount_str)
            else:
                amount_from_body = _parse_plain_amount(amount_raw)
                if amount_from_body is None:
                    nums = re.findall(r'[\d]{4,}(?:[.,]\d+)*', combined)
                    if nums:
                        amount_from_body = float(nums[-1].replace(",", "").replace(".", ""))
                if amount_from_body is None:
                    logger.warning(f"Could not extract amount from: {amount_raw}")
                    return web.Response(text="Số tiền không hợp lệ", status=400)

    async with async_session() as session:
        # Find the pending transaction with this ref (case-insensitive)
        result = await session.execute(
            select(Transaction).where(
                Transaction.payment_ref.ilike(ref),
                Transaction.status == "pending",
                Transaction.type == "deposit"
            )
        )
        tx = result.scalar_one_or_none()

        if not tx:
            logger.warning(f"No pending transaction found for ref: {ref}")
            return web.Response(text="Transaction not found or already processed", status=404)

        # Số tiền thực nhận: ưu tiên PS, sau đó amount trong body (không có cả hai → không đối chiếu được)
        ps_amt = _parse_ps_line_amount(combined)
        received: float | None = ps_amt if ps_amt is not None else amount_from_body

        if ps_amt is None and WEBHOOK_REQUIRE_PS_LINE:
            logger.warning(f"Missing PS line in webhook body for {ref}")
            return web.Response(
                text=(
                    "Thiếu dòng PS:...VND. Gửi kèm toàn bộ nội dung thông báo TPBank "
                    "(đặt trong ref hoặc amount)."
                ),
                status=400,
            )

        if received is None:
            if not WEBHOOK_ALLOW_REF_ONLY:
                logger.warning(f"No PS/amount to verify transfer for {ref}")
                return web.Response(
                    text=(
                        "Cần đối chiếu số tiền chuyển khoản: gửi tin có dòng PS:...VND "
                        "hoặc field amount (số từ SMS). Chỉ gửi mã NAP không đủ "
                        "(bật WEBHOOK_ALLOW_REF_ONLY=true nếu chấp nhận rủi ro)."
                    ),
                    status=400,
                )
            logger.warning(
                f"Ref-only confirm for {ref} (WEBHOOK_ALLOW_REF_ONLY=true; cannot detect underpayment)"
            )

        elif _is_underpayment(received, tx.amount):
            logger.warning(
                f"Underpayment for {ref}: order {tx.amount}, received {received}"
            )
            return web.Response(
                text="Số tiền nhận phải lớn hơn hoặc bằng số tiền đơn (QR). Không xác nhận nạp.",
                status=400,
            )

        amount = float(tx.amount)
        if received is not None:
            logger.info(f"Parsed webhook: Ref={ref}, order={tx.amount}, verified received={received}")
        else:
            logger.info(f"Parsed webhook: Ref={ref}, Amount={amount} (ref-only, no bank amount)")

        # Confirm deposit (luôn cộng đúng số tiền đơn chờ, kể cả khi SMS ghi số lớn hơn)
        credited = float(tx.amount)
        res = await confirm_deposit(session, tx.id)
        if res["success"]:
            # Notify user via bot (we need application instance for this)
            app = request.app['bot_app']
            try:
                lang = await get_user_lang(session, res["user_id"])
                await app.bot.send_message(
                    chat_id=res["user_id"],
                    text=f"✅ **NẠP TIỀN THÀNH CÔNG (TỰ ĐỘNG)!**\n\n💰 Số tiền: {credited:,.0f}đ\n💰 Số dư mới: {res['balance']:,.0f}đ",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_menu_keyboard(lang),
                )
            except Exception as e:
                logger.error(f"Failed to notify user {res['user_id']}: {e}")
            
            return web.json_response(
                {"status": "success", "amount": credited, "new_balance": res["balance"]}
            )
        else:
            return web.json_response({"status": "error", "message": res["message"]}, status=400)

async def start_webhook_server(bot_app):
    app = web.Application()
    app['bot_app'] = bot_app
    app.router.add_post('/webhook/deposit', handle_deposit_webhook)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEBHOOK_PORT)
    await site.start()
    logger.info(f"Webhook server started on port {WEBHOOK_PORT}")
