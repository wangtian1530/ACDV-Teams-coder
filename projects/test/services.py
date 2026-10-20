"""Business logic dùng chung: login, ensure token, OTP flow, state."""
import asyncio
import json
import logging
import threading

from crypto import fernet
from db import db_get, db_save_tokens
from hrm_client import HrmClient, Hrm2FARequired, TokenExpired

log = logging.getLogger("hrm-bot")

# OTP đang chờ user trả lời
OTP_WAITERS: dict[int, dict] = {}
# Trạng thái chờ nhập liệu (login / set time)
PENDING: dict[int, dict] = {}


def user_tag(tg_id: int) -> str:
    return f"[TG:{tg_id}]"


def make_client(tg_id, username=None, password=None, otp_provider=None):
    """Tạo HrmClient có gắn credentials để auto-recovery."""
    return HrmClient(
        telegram_id=tg_id,
        on_tokens_update=lambda t: db_save_tokens(tg_id, t),
        username=username,
        password=password,
        otp_provider=otp_provider,
    )


def load_tokens_for(tg_id):
    row = db_get(tg_id)
    if not row or not row["tokens_json"]:
        return None
    return json.loads(row["tokens_json"])


def make_otp_provider_sync(tg_id, bot_app, chat_id):
    def provider():
        ev = threading.Event()
        OTP_WAITERS[tg_id] = {"event": ev, "value": None}
        fut = asyncio.run_coroutine_threadsafe(
            bot_app.bot.send_message(
                chat_id,
                "🔐 Tài khoản cần xác thực 2FA. Vui lòng nhập mã OTP (hết hạn 5 phút):"
            ),
            bot_app.loop
        )
        try:
            fut.result(timeout=10)
        except Exception as e:
            log.warning("%s Không gửi được yêu cầu OTP: %s", user_tag(tg_id), e)

        if not ev.wait(timeout=300):
            OTP_WAITERS.pop(tg_id, None)
            log.warning("%s Timeout chờ OTP", user_tag(tg_id))
            raise Exception("⏱ Hết thời gian chờ OTP")
        val = OTP_WAITERS[tg_id]["value"]
        OTP_WAITERS.pop(tg_id, None)
        log.info("%s Đã nhận OTP từ user", user_tag(tg_id))
        return val
    return provider


def _resolve_bot_app(obj):
    """Lấy Application từ Update/Context/CallbackQuery/Message một cách an toàn."""
    if obj is None:
        return None
    app = getattr(obj, "application", None)
    if app is not None:
        return app
    # Các wrapper khác
    bot = getattr(obj, "bot", None) or getattr(obj, "get_bot", lambda: None)()
    if bot is not None:
        app = getattr(bot, "application", None)
        if app is not None:
            return app
    # Từ message
    msg = getattr(obj, "message", None)
    if msg is not None:
        return _resolve_bot_app(msg)
    return None


def _resolve_chat_id(obj, row, tg_id):
    """Lấy chat_id từ obj, fallback về DB."""
    for attr in ("effective_chat", "chat"):
        ch = getattr(obj, attr, None)
        if ch is not None and getattr(ch, "id", None):
            return ch.id
    msg = getattr(obj, "message", None)
    if msg is not None and getattr(msg, "chat", None) is not None:
        return msg.chat.id
    if row is not None and row.get("chat_id"):
        return row["chat_id"]
    return tg_id


def _build_otp_provider(tg_id, obj, row):
    bot_app = _resolve_bot_app(obj)
    chat_id = _resolve_chat_id(obj, row, tg_id)
    if bot_app is None:
        log.warning("%s Không lấy được Application để tạo OTP provider",
                    user_tag(tg_id))
        return None
    try:
        return make_otp_provider_sync(tg_id, bot_app, chat_id)
    except Exception:
        log.exception("%s Tạo OTP provider thất bại", user_tag(tg_id))
        return None


def login_blocking(tg_id, username, password, bot_app=None, chat_id=None):
    otp_provider = None
    if bot_app is not None and chat_id is not None:
        otp_provider = make_otp_provider_sync(tg_id, bot_app, chat_id)
    client = make_client(tg_id, username=username, password=password,
                        otp_provider=otp_provider)
    return client.login(username, password, otp_provider=otp_provider)


async def ensure_logged_in(context, tg_id):
    """Đảm bảo client đã login, tự refresh / login lại nếu cần.

    `context` nên là ContextTypes.DEFAULT_TYPE hoặc JobContext (có `.application`).
    """
    row = db_get(tg_id)
    if not row:
        log.warning("%s ensure_logged_in: chưa có user trong DB", user_tag(tg_id))
        return None, None

    tokens = json.loads(row["tokens_json"]) if row["tokens_json"] else None
    password = fernet.decrypt(row["password_enc"].encode()).decode()

    otp_provider = _build_otp_provider(tg_id, context, row)

    # 1) Có token sẵn → thử dùng luôn
    if tokens:
        client = make_client(tg_id, username=row["username"],
                            password=password, otp_provider=otp_provider)
        client.set_tokens(tokens)
        try:
            client.ensure_token()
            return client, row
        except TokenExpired:
            log.info("%s Token hết hạn, login lại", user_tag(tg_id))
        except Exception:
            log.exception("%s ensure_token lỗi không mong đợi", user_tag(tg_id))

    # 2) Login lại từ đầu
    bot_app = _resolve_bot_app(context)
    chat_id = _resolve_chat_id(context, row, tg_id)
    try:
        new_tokens = await asyncio.to_thread(
            login_blocking, tg_id, row["username"], password, bot_app, chat_id
        )
        db_save_tokens(tg_id, new_tokens)
        client = make_client(tg_id, username=row["username"],
                            password=password, otp_provider=otp_provider)
        client.set_tokens(new_tokens)
        log.info("%s Đăng nhập lại THÀNH CÔNG user=%s",
                 user_tag(tg_id), row["username"])
        return client, row
    except Hrm2FARequired:
        log.warning("%s Cần 2FA khi login lại", user_tag(tg_id))
        raise
    except Exception:
        log.exception("%s Login lại THẤT BẠI", user_tag(tg_id))
        return None, row