"""Cấu hình logging: 2 file riêng (HRM client DEBUG, bot INFO) + error.log + console."""
import os
import logging
import logging.handlers

from config import LOG_DIR

_LOG_FMT = "%(asctime)s.%(msecs)03d [%(levelname)-7s] %(name)s: %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _mk_rotating_handler(path: str, level: int, max_bytes: int, backups: int):
    h = logging.handlers.RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
    )
    h.setLevel(level)
    h.setFormatter(logging.Formatter(_LOG_FMT, _LOG_DATEFMT))
    return h


def _mk_error_handler(path: str):
    """Handler riêng cho WARNING+ (bao gồm auto-recovery, timeout, logout, relogin)."""
    return _mk_rotating_handler(path, logging.WARNING, 10 * 1024 * 1024, 10)


def setup_logging():
    """Bật logging. Gọi 1 lần duy nhất khi khởi động bot."""
    os.makedirs(LOG_DIR, exist_ok=True)

    error_path = os.path.join(LOG_DIR, "error.log")

    # 1) HRM client - DEBUG chi tiết
    hrm_log = logging.getLogger("hrm-client")
    hrm_log.setLevel(logging.DEBUG)
    hrm_log.propagate = False
    hrm_log.addHandler(_mk_rotating_handler(
        os.path.join(LOG_DIR, "hrm_client.log"),
        logging.DEBUG, 50 * 1024 * 1024, 10,
    ))
    hrm_log.addHandler(_mk_error_handler(error_path))

    # 2) Bot - INFO
    bot_log = logging.getLogger("hrm-bot")
    bot_log.setLevel(logging.INFO)
    bot_log.propagate = False
    bot_log.addHandler(_mk_rotating_handler(
        os.path.join(LOG_DIR, "bot.log"),
        logging.INFO, 5 * 1024 * 1024, 5,
    ))
    bot_log.addHandler(_mk_error_handler(error_path))

    # 3) Thư viện khác -> bot.log
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(_mk_rotating_handler(
        os.path.join(LOG_DIR, "bot.log"),
        logging.INFO, 5 * 1024 * 1024, 5,
    ))
    root.addHandler(_mk_error_handler(error_path))

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_LOG_FMT, _LOG_DATEFMT))
    root.addHandler(console)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.Updater").setLevel(logging.INFO)
    logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)