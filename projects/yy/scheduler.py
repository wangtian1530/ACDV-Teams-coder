"""Lên lịch nhắc nhở hằng ngày cho từng user."""
import asyncio
import logging
from datetime import time as dtime

from telegram.ext import Application, ContextTypes

from config import TZ
from db import db_get, db_all
from formatters import is_draft, is_before_today, short_item
from keyboards import kb_reminder
from services import ensure_logged_in, user_tag

log = logging.getLogger("hrm-bot")

JOB_PREFIX = "reminder_"


async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    tg_id = context.job.data
    row = db_get(tg_id)
    if not row:
        log.info("%s reminder: user không còn trong DB, bỏ qua", user_tag(tg_id))
        return
    chat_id = row["chat_id"] or tg_id
    log.info("%s reminder chạy cho chat=%s", user_tag(tg_id), chat_id)

    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        log.warning("%s reminder: không login được, bỏ qua", user_tag(tg_id))
        return

    try:
        items = await asyncio.to_thread(client.list_overtime)
    except Exception as e:
        log.warning("%s reminder: list lỗi %s", user_tag(tg_id), e)
        return

    drafts = [x for x in items if is_draft(x) and is_before_today(x)]
    hh, mm = row["notify_hour"], row["notify_min"]

    if not drafts:
        log.info("%s reminder: không có nháp trước hôm nay", user_tag(tg_id))
        await context.bot.send_message(
            chat_id,
            f"🌙 *{hh:02d}:{mm:02d}* rồi! Bạn *không có bản nháp tăng ca nào trước hôm nay*.\n"
            "Nếu có tăng ca, hãy tạo nháp trong app HRM nhé.",
            parse_mode="Markdown",
        )
        return

    lines = [f"🌙 *{hh:02d}:{mm:02d}* rồi! Bạn có *{len(drafts)}* bản nháp tăng ca (trước hôm nay):\n"]
    for it in drafts:
        lines.append(short_item(it))
    lines.append("\n👉 Có muốn gửi duyệt không?")
    log.info("%s reminder: gửi thông báo %d nháp", user_tag(tg_id), len(drafts))
    await context.bot.send_message(chat_id, "\n".join(lines),
                                   parse_mode="Markdown",
                                   reply_markup=kb_reminder())


async def reschedule_user_job(app: Application, tg_id: int, hour: int, minute: int):
    name = f"{JOB_PREFIX}{tg_id}"
    for j in app.job_queue.get_jobs_by_name(name):
        j.schedule_removal()
    app.job_queue.run_daily(
        daily_reminder, time=dtime(hour=hour, minute=minute, tzinfo=TZ),
        name=name, data=tg_id
    )
    log.info("%s Đã lên lịch nhắc %02d:%02d", user_tag(tg_id), hour, minute)


async def schedule_all_jobs(app: Application):
    rows = db_all()
    log.info("Scheduler: nạp %d user", len(rows))
    for row in rows:
        await reschedule_user_job(app, row["telegram_id"],
                                  row["notify_hour"], row["notify_min"])