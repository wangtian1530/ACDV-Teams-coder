"""Entry point: khởi động Telegram bot quản lý tăng ca HRM VFR.

Cấu trúc module:
    config.py        - hằng số cấu hình
    logger_setup.py  - cấu hình logging 2 file riêng
    crypto.py        - Fernet key / mã hoá mật khẩu
    db.py            - SQLite
    formatters.py    - format + phân loại item tăng ca
    hrm_client.py    - HTTP client HRM (requests)
    services.py      - business logic login / token / OTP
    keyboards.py     - inline keyboard
    scheduler.py     - job nhắc nhở hằng ngày
    handlers.py      - Telegram handlers
"""
import logging

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from config import BOT_TOKEN
from logger_setup import setup_logging
from db import init_db
from handlers import (
    cmd_start, cmd_login, cmd_logout,
    on_callback, on_text, on_error,
)
from scheduler import schedule_all_jobs

log = logging.getLogger("hrm-bot")


async def post_init(app: Application):
    await schedule_all_jobs(app)


def main():
    setup_logging()
    init_db()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("login", cmd_login))
    app.add_handler(CommandHandler("logout", cmd_logout))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    log.info("Bot đang chạy (button UI)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()