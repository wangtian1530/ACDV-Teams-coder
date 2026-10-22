"""Toàn bộ handlers: commands, callback, text, OTP flow."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from config import TZ
from db import db_get, db_set_time, db_delete, db_upsert
from formatters import (
    md_escape, is_draft, is_before_today, short_item,
    parse_utc, fmt_remain,
    calc_workday_stats, fmt_workday_stats,
)
from hrm_client import HrmClient, Hrm2FARequired
from keyboards import (
    kb_main, kb_back, kb_cancel, kb_settings,
    kb_drafts, kb_cutoff, kb_workday_cutoffs,
)
from scheduler import reschedule_user_job
from services import (
    OTP_WAITERS, PENDING, user_tag,
    login_blocking, ensure_logged_in,
)

log = logging.getLogger("hrm-bot")


# ================== SCREEN ==================
async def show_home(query_or_msg, context, tg_id, edit=True):
    row = db_get(tg_id)
    logged = row is not None
    if logged:
        text = (
            "🏠 *Menu chính*\n\n"
            "Chọn thao tác bên dưới 👇\n"
            f"⏰ Giờ nhắc: `{row['notify_hour']:02d}:{row['notify_min']:02d}`"
        )
    else:
        text = (
            "👋 *Bot quản lý tăng ca HRM VFR*\n\n"
            "Bạn chưa liên kết tài khoản. Nhấn *Đăng nhập HRM* để bắt đầu."
        )
    kb = kb_main(logged)
    if edit and hasattr(query_or_msg, "edit_message_text"):
        try:
            await query_or_msg.edit_message_text(text, parse_mode="Markdown",
                                                 reply_markup=kb)
            return
        except Exception:
            pass
    await query_or_msg.reply_text(text, parse_mode="Markdown", reply_markup=kb)


# ================== COMMANDS ==================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    log.info("%s /start", user_tag(tg_id))
    PENDING.pop(tg_id, None)
    await show_home(update.message, context, tg_id, edit=False)


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vẫn hỗ trợ /login user pass."""
    user = update.effective_user
    chat = update.effective_chat
    tg_id = user.id
    if not context.args or len(context.args) < 2:
        await show_home(update.message, context, tg_id, edit=False)
        return
    username, password = context.args[0], context.args[1]
    try:
        if chat.type != "private":
            await context.bot.delete_message(chat.id, update.message.message_id)
    except Exception:
        pass

    log.info("%s /login user=%s", user_tag(tg_id), username)
    msg = await update.message.reply_text("🔐 Đang đăng nhập HRM...")
    try:
        tokens = await asyncio.to_thread(
            login_blocking, tg_id, username, password,
            context.application, chat.id,
        )
        db_upsert(tg_id, chat.id, username, password, tokens)
        p = HrmClient.decode_jwt(tokens["access_token"])
        log.info("%s /login THÀNH CÔNG user=%s", user_tag(tg_id), username)
        await msg.edit_text(
            f"✅ *Đăng nhập thành công!*\n"
            f"👤 {md_escape(p.get('hrm_fullname', '?'))} "
            f"({md_escape(p.get('hrm_username', '?'))})",
            parse_mode="Markdown",
            reply_markup=kb_main(True),
        )
    except Hrm2FARequired:
        log.warning("%s /login yêu cầu 2FA", user_tag(tg_id))
        await msg.edit_text("❌ Không xử lý được 2FA. Thử lại.")
    except Exception as e:
        log.exception("%s /login THẤT BẠI", user_tag(tg_id))
        await msg.edit_text(f"❌ Đăng nhập thất bại: {e}")


async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    db_delete(tg_id)
    PENDING.pop(tg_id, None)
    log.info("%s /logout", user_tag(tg_id))
    await update.message.reply_text("🚪 Đã xoá liên kết Telegram ↔ HRM.",
                                    reply_markup=kb_main(False))


# ================== LOGIN FLOW ==================
async def start_login_flow(query, tg_id):
    PENDING[tg_id] = {"action": "login_user"}
    await query.edit_message_text(
        "🔐 *Đăng nhập HRM*\n\nBước 1/2: Nhập *tài khoản* (username) của bạn:",
        parse_mode="Markdown",
        reply_markup=kb_cancel(),
    )


async def handle_login_user(update, tg_id, text):
    PENDING[tg_id] = {"action": "login_pass", "username": text}
    log.info("%s Login flow: nhập username=%s", user_tag(tg_id), text)
    await update.message.reply_text(
        "Bước 2/2: Nhập *mật khẩu* HRM:",
        parse_mode="Markdown",
        reply_markup=kb_cancel(),
    )


async def handle_login_pass(update, context, tg_id, password):
    state = PENDING.pop(tg_id, {})
    username = state.get("username")
    user = update.effective_user
    chat = update.effective_chat

    try:
        if chat.type != "private":
            await context.bot.delete_message(chat.id, update.message.message_id)
    except Exception:
        pass

    msg = await update.message.reply_text("🔐 Đang đăng nhập HRM...")
    try:
        tokens = await asyncio.to_thread(
            login_blocking, tg_id, username, password,
            context.application, chat.id,
        )
        db_upsert(tg_id, chat.id, username, password, tokens)
        p = HrmClient.decode_jwt(tokens["access_token"])
        log.info("%s Login flow THÀNH CÔNG user=%s", user_tag(tg_id), username)
        await msg.edit_text(
            f"✅ *Đăng nhập thành công!*\n"
            f"👤 {md_escape(p.get('hrm_fullname', '?'))} "
            f"({md_escape(p.get('hrm_username', '?'))})",
            parse_mode="Markdown",
        )
        await show_home(msg, context, tg_id, edit=False)
    except Hrm2FARequired:
        log.warning("%s Login flow yêu cầu 2FA", user_tag(tg_id))
        await msg.edit_text("❌ Không xử lý được 2FA. Thử lại sau.")
    except Exception as e:
        log.exception("%s Login flow THẤT BẠI", user_tag(tg_id))
        await msg.edit_text(f"❌ Đăng nhập thất bại: {e}",
                            reply_markup=kb_main(False))


# ================== ACTIONS ==================
async def action_list(query, context, tg_id):
    log.info("%s action=list", user_tag(tg_id))
    await query.edit_message_text("⏳ Đang tải...")
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        log.warning("%s action=list: chưa login", user_tag(tg_id))
        await query.edit_message_text("❌ Chưa đăng nhập hoặc login lại thất bại.",
                                      reply_markup=kb_main(False))
        return
    try:
        items = await asyncio.to_thread(client.list_overtime)
        log.info("%s action=list OK — %d bản ghi", user_tag(tg_id), len(items))
    except Exception as e:
        log.exception("%s action=list THẤT BẠI", user_tag(tg_id))
        await query.edit_message_text(f"❌ Lỗi: {e}", reply_markup=kb_back())
        return
    if not items:
        await query.edit_message_text("📭 Không có bản ghi tăng ca nào.",
                                      reply_markup=kb_back())
        return
    lines = [f"📋 *{len(items)} bản ghi tăng ca*\n"]
    for it in items[:60]:
        lines.append(short_item(it))
    if len(items) > 60:
        lines.append(f"\n… và {len(items)-60} bản ghi khác.")
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown",
                                  reply_markup=kb_back())


async def action_draft(query, context, tg_id):
    log.info("%s action=draft", user_tag(tg_id))
    await query.edit_message_text("⏳ Đang tải bản nháp...")
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        log.warning("%s action=draft: chưa login", user_tag(tg_id))
        await query.edit_message_text("❌ Chưa đăng nhập.", reply_markup=kb_main(False))
        return
    try:
        items = await asyncio.to_thread(client.list_overtime)
        drafts = [x for x in items if is_draft(x)]
        log.info("%s action=draft OK — %d nháp / %d tổng",
                 user_tag(tg_id), len(drafts), len(items))
    except Exception as e:
        log.exception("%s action=draft THẤT BẠI", user_tag(tg_id))
        await query.edit_message_text(f"❌ Lỗi: {e}", reply_markup=kb_back())
        return
    if not drafts:
        await query.edit_message_text("📭 Không có bản nháp tăng ca nào.",
                                      reply_markup=kb_back())
        return
    txt = [f"📝 *{len(drafts)} bản nháp*\n",
           "Nhấn nút để gửi duyệt từng bản, hoặc gửi tất cả nháp *trước hôm nay*:\n"]
    for it in drafts[:20]:
        txt.append(short_item(it))
    await query.edit_message_text("\n".join(txt), parse_mode="Markdown",
                                  reply_markup=kb_drafts(drafts))


async def _submit_drafts(query, context, tg_id, drafts, context_label):
    if not drafts:
        await query.edit_message_text(
            "📭 Không có bản nháp nào *trước hôm nay* để gửi.",
            parse_mode="Markdown", reply_markup=kb_back(),
        )
        return
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        await query.edit_message_text("❌ Chưa đăng nhập.", reply_markup=kb_main(False))
        return
    ids = [x["ID"] for x in drafts]
    res = await asyncio.to_thread(client.submit_overtime, ids)
    await query.edit_message_text(
        f"✅ Đã gửi *{len(drafts)}* bản nháp ({context_label}).\n"
        f"Server: `{res.get('Status')}` – {md_escape(res.get('Message',''))}",
        parse_mode="Markdown", reply_markup=kb_back(),
    )


async def action_submit_today(query, context, tg_id):
    log.info("%s action=submit_before_today", user_tag(tg_id))
    await query.edit_message_text("⏳ Đang gửi duyệt các nháp trước hôm nay...")
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        log.warning("%s action=submit_before_today: chưa login", user_tag(tg_id))
        await query.edit_message_text("❌ Chưa đăng nhập.", reply_markup=kb_main(False))
        return
    try:
        items = await asyncio.to_thread(client.list_overtime)
        drafts = [x for x in items if is_draft(x) and is_before_today(x)]
        log.info("%s action=submit_before_today — %d nháp cần gửi (tổng %d)",
                 user_tag(tg_id), len(drafts), len(items))
        if not drafts:
            await query.edit_message_text(
                "📭 Không có bản nháp nào *trước hôm nay* để gửi.",
                parse_mode="Markdown", reply_markup=kb_back(),
            )
            return
        ids = [x["ID"] for x in drafts]
        res = await asyncio.to_thread(client.submit_overtime, ids)
        log.info("%s action=submit_before_today THÀNH CÔNG — %d bản, status=%s",
                 user_tag(tg_id), len(drafts), res.get("Status"))
        await query.edit_message_text(
            f"✅ Đã gửi *{len(drafts)}* bản nháp (trước hôm nay).\n"
            f"Server: `{res.get('Status')}` – {md_escape(res.get('Message',''))}",
            parse_mode="Markdown", reply_markup=kb_back(),
        )
    except Exception as e:
        log.exception("%s action=submit_before_today THẤT BẠI", user_tag(tg_id))
        await query.edit_message_text(f"❌ Lỗi: {e}", reply_markup=kb_back())


async def action_submit_one(query, context, tg_id, item_id):
    log.info("%s action=submit_one id=%s", user_tag(tg_id), item_id[:8])
    await query.edit_message_text("⏳ Đang gửi duyệt bản nháp...")
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        await query.edit_message_text("❌ Chưa đăng nhập.", reply_markup=kb_main(False))
        return
    try:
        res = await asyncio.to_thread(client.submit_overtime, [item_id])
        log.info("%s action=submit_one THÀNH CÔNG id=%s status=%s",
                 user_tag(tg_id), item_id[:8], res.get("Status"))
        await query.edit_message_text(
            f"✅ Đã gửi `{item_id[:8]}`.\n"
            f"Server: `{res.get('Status')}` – {md_escape(res.get('Message',''))}",
            parse_mode="Markdown", reply_markup=kb_back(),
        )
    except Exception as e:
        log.exception("%s action=submit_one THẤT BẠI id=%s", user_tag(tg_id), item_id[:8])
        await query.edit_message_text(f"❌ Lỗi: {e}", reply_markup=kb_back())


async def action_me(query, context, tg_id):
    log.info("%s action=me", user_tag(tg_id))
    row = db_get(tg_id)
    if not row:
        await query.edit_message_text("Chưa liên kết. Hãy /start lại.",
                                      reply_markup=kb_main(False))
        return
    tokens = json.loads(row["tokens_json"]) if row["tokens_json"] else {}
    p = HrmClient.decode_jwt(tokens.get("access_token", ""))
    exp = p.get("exp", 0)
    exp_s = (datetime.fromtimestamp(exp, tz=timezone.utc).astimezone(TZ)
             .strftime("%d/%m/%Y %H:%M")) if exp else "?"
    await query.edit_message_text(
        f"👤 *{md_escape(p.get('hrm_fullname', row['username']))}*\n"
        f"🔑 Username: `{md_escape(row['username'])}`\n"
        f"⏰ Nhắc lúc: `{row['notify_hour']:02d}:{row['notify_min']:02d}`\n"
        f"♻️ Access token hết hạn: `{exp_s}`",
        parse_mode="Markdown",
        reply_markup=kb_back(),
    )


async def action_settings(query, context, tg_id):
    log.info("%s action=settings", user_tag(tg_id))
    row = db_get(tg_id)
    if not row:
        await query.edit_message_text("Chưa liên kết.", reply_markup=kb_main(False))
        return
    await query.edit_message_text(
        "⚙️ *Cài đặt*\n\nChọn thao tác:",
        parse_mode="Markdown",
        reply_markup=kb_settings(row),
    )


# ---------- KỲ CHỐT CÔNG ----------
async def action_cutoff(query, context, tg_id):
    log.info("%s action=cutoff", user_tag(tg_id))
    await query.edit_message_text("⏳ Đang tải kỳ chốt công...")
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        await query.edit_message_text("❌ Chưa đăng nhập.", reply_markup=kb_main(False))
        return
    try:
        res = await asyncio.to_thread(client.get_cutoff_duration_by_profile)
        log.info("%s action=cutoff OK status=%s", user_tag(tg_id), res.get("Status"))
    except Exception as e:
        log.exception("%s action=cutoff THẤT BẠI", user_tag(tg_id))
        await query.edit_message_text(f"❌ Lỗi: {e}", reply_markup=kb_back())
        return

    if res.get("Status") != "SUCCESS":
        log.warning("%s action=cutoff server error: %s", user_tag(tg_id), res.get("Message"))
        await query.edit_message_text(
            f"❌ Server trả lỗi: `{md_escape(res.get('Message','?'))}`",
            parse_mode="Markdown", reply_markup=kb_back(),
        )
        return

    periods = res.get("Data") or []
    if not periods:
        await query.edit_message_text("📭 Không có kỳ chốt công nào.",
                                      reply_markup=kb_back())
        return

    now = datetime.now(timezone.utc)

    current_idx = -1
    for i, p in enumerate(periods):
        try:
            s = parse_utc(p["DateStart"])
            e = parse_utc(p["DateEnd"])
        except Exception:
            continue
        if s <= now <= e:
            current_idx = i
            break

    lines = ["📅 *Kỳ chốt công*\n"]
    if current_idx >= 0:
        cur = periods[current_idx]
        try:
            s = parse_utc(cur["DateStart"]).astimezone(TZ)
            e = parse_utc(cur["DateEnd"]).astimezone(TZ)
            remain = fmt_remain((e - now.astimezone(TZ)).total_seconds())
            lines.append(
                f"🟢 *Đang trong kỳ:* {md_escape(cur.get('CutOffDurationName','?'))}\n"
                f"   {s.strftime('%d/%m/%Y')} → {e.strftime('%d/%m/%Y')}\n"
                f"   ⏳ _{remain}_"
            )
        except Exception:
            lines.append(f"🟢 *Đang trong kỳ:* {md_escape(cur.get('CutOffDurationName','?'))}")
    else:
        lines.append("⚪ Hiện không nằm trong kỳ chốt công nào.")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=kb_cutoff(periods, current_idx),
    )


async def action_cutoff_detail(query, context, tg_id, index_or_all):
    log.info("%s action=cutoff_detail key=%s", user_tag(tg_id), index_or_all)
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        await query.edit_message_text("❌ Chưa đăng nhập.", reply_markup=kb_main(False))
        return
    try:
        res = await asyncio.to_thread(client.get_cutoff_duration_by_profile)
    except Exception as e:
        log.exception("%s action=cutoff_detail THẤT BẠI", user_tag(tg_id))
        await query.edit_message_text(f"❌ Lỗi: {e}", reply_markup=kb_back())
        return

    periods = (res.get("Data") or []) if res.get("Status") == "SUCCESS" else []
    if not periods:
        await query.edit_message_text("📭 Không có dữ liệu.", reply_markup=kb_back())
        return

    now = datetime.now(timezone.utc)

    if index_or_all == "all":
        lines = [f"📅 *Tất cả kỳ chốt công* ({len(periods)})\n"]
        for p in periods:
            name = md_escape(p.get("CutOffDurationName", "?"))
            try:
                s = parse_utc(p["DateStart"]).astimezone(TZ)
                e = parse_utc(p["DateEnd"]).astimezone(TZ)
            except Exception:
                continue
            is_current = parse_utc(p["DateStart"]) <= now <= parse_utc(p["DateEnd"])
            mark = "🟢" if is_current else "▫️"
            lines.append(
                f"{mark} *{name}*\n"
                f"     {s.strftime('%d/%m/%Y')} → {e.strftime('%d/%m/%Y')}"
            )
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown",
                                      reply_markup=kb_back())
        return

    try:
        idx = int(index_or_all)
        p = periods[idx]
    except Exception:
        log.warning("%s cutoff_detail index không hợp lệ: %s", user_tag(tg_id), index_or_all)
        await query.edit_message_text("⚠️ Không tìm thấy kỳ.", reply_markup=kb_back())
        return

    name = md_escape(p.get("CutOffDurationName", "?"))
    try:
        s_utc = parse_utc(p["DateStart"])
        e_utc = parse_utc(p["DateEnd"])
        s = s_utc.astimezone(TZ)
        e = e_utc.astimezone(TZ)
    except Exception:
        await query.edit_message_text("⚠️ Lỗi parse thời gian.", reply_markup=kb_back())
        return

    is_current = s_utc <= now <= e_utc
    remain = fmt_remain((e_utc - now).total_seconds()) if is_current else "—"
    total_days = (e_utc - s_utc).total_seconds() / 86400
    elapsed = max(0.0, (now - s_utc).total_seconds()) if is_current else 0.0
    pct = min(100.0, (elapsed / (total_days * 86400)) * 100) if is_current and total_days > 0 else 0

    filled = int(pct // 10)
    bar = "█" * filled + "░" * (10 - filled)

    lines = [
        f"📅 *{name}*",
        f"{'🟢 Đang trong kỳ' if is_current else '⚪ Kỳ đã qua / sắp tới'}",
        "",
        f"🗓 Bắt đầu: `{s.strftime('%d/%m/%Y %H:%M')}`",
        f"🏁 Kết thúc: `{e.strftime('%d/%m/%Y %H:%M')}`",
        f"⏱ Tổng: `{total_days:.1f}` ngày",
    ]
    if is_current:
        lines.append(f"⏳ _{remain}_")
        lines.append(f"`{bar}` {pct:.0f}%")

    await query.edit_message_text("\n".join(lines), parse_mode="Markdown",
                                  reply_markup=kb_back())


# ---------- BẢNG CÔNG CHI TIẾT ----------
async def action_workday_select(query, context, tg_id):
    """Hiển thị list kỳ chốt công để user chọn xem bảng công chi tiết."""
    log.info("%s action=workday_select", user_tag(tg_id))
    await query.edit_message_text("⏳ Đang tải kỳ chốt công...")
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        log.warning("%s action=workday_select: chưa login", user_tag(tg_id))
        await query.edit_message_text("❌ Chưa đăng nhập.", reply_markup=kb_main(False))
        return
    try:
        res = await asyncio.to_thread(client.get_cutoff_duration_by_profile)
    except Exception as e:
        log.exception("%s action=workday_select THẤT BẠI", user_tag(tg_id))
        await query.edit_message_text(f"❌ Lỗi: {e}", reply_markup=kb_back())
        return

    periods = (res.get("Data") or []) if res.get("Status") == "SUCCESS" else []
    if not periods:
        await query.edit_message_text("📭 Không có kỳ chốt công nào.",
                                      reply_markup=kb_back())
        return

    now = datetime.now(timezone.utc)
    current_idx = -1
    for i, p in enumerate(periods):
        try:
            s = parse_utc(p["DateStart"]); e = parse_utc(p["DateEnd"])
            if s <= now <= e:
                current_idx = i
                break
        except Exception:
            continue

    await query.edit_message_text(
        "📊 *Bảng công chi tiết*\n\nChọn kỳ chốt công để xem:",
        parse_mode="Markdown",
        reply_markup=kb_workday_cutoffs(periods, current_idx),
    )


async def action_workday_detail(query, context, tg_id, idx_str):
    """Lấy và hiển thị bảng công chi tiết theo index kỳ chốt."""
    log.info("%s action=workday_detail idx=%s", user_tag(tg_id), idx_str)
    await query.edit_message_text("⏳ Đang tải bảng công chi tiết...")
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        await query.edit_message_text("❌ Chưa đăng nhập.", reply_markup=kb_main(False))
        return

    # B1: cần CutOffDurationID → lấy lại danh sách kỳ chốt
    try:
        res_cut = await asyncio.to_thread(client.get_cutoff_duration_by_profile)
    except Exception as e:
        log.exception("%s action=workday_detail: không lấy được kỳ chốt", user_tag(tg_id))
        await query.edit_message_text(f"❌ Lỗi kỳ chốt: {e}", reply_markup=kb_back())
        return

    periods = (res_cut.get("Data") or []) if res_cut.get("Status") == "SUCCESS" else []
    try:
        idx = int(idx_str)
        p = periods[idx]
        cutoff_id = p["ID"]
        cutoff_name = p.get("CutOffDurationName", "?")
    except Exception:
        log.warning("%s workday_detail index không hợp lệ: %s", user_tag(tg_id), idx_str)
        await query.edit_message_text("⚠️ Không tìm thấy kỳ.", reply_markup=kb_back())
        return

    # B2: gọi API bảng công chi tiết
    try:
        res = await asyncio.to_thread(client.get_workday_detail, cutoff_id)
    except Exception as e:
        log.exception("%s action=workday_detail THẤT BẠI", user_tag(tg_id))
        await query.edit_message_text(f"❌ Lỗi: {e}", reply_markup=kb_back())
        return

    if res.get("Status") != "SUCCESS":
        log.warning("%s workday server error: %s", user_tag(tg_id), res.get("Message"))
        await query.edit_message_text(
            f"❌ Server trả lỗi: `{md_escape(res.get('Message','?'))}`",
            parse_mode="Markdown", reply_markup=kb_back(),
        )
        return

    data = res.get("Data") or []
    if not data:
        await query.edit_message_text("📭 Không có dữ liệu công trong kỳ này.",
                                      reply_markup=kb_back())
        return

    profile = data[0]
    stats = calc_workday_stats(profile)
    text = fmt_workday_stats(stats, cutoff_name)
    log.info(
        "%s workday OK — user=%s std=%.2f actual=%.2f ot_wd=%.2f ot_sun=%.2f",
        user_tag(tg_id), stats.get("employee_id"),
        stats["standard_workdays"], stats["actual_workdays"],
        stats["overtime"]["weekday_hours"], stats["overtime"]["sunday_hours"],
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb_back())


async def start_settime_flow(query, tg_id):
    PENDING[tg_id] = {"action": "set_time"}
    await query.edit_message_text(
        "⏰ Nhập giờ nhắc theo định dạng *HH:MM* (VD: `20:30`):",
        parse_mode="Markdown",
        reply_markup=kb_cancel(),
    )


async def handle_set_time(update, context, tg_id, text):
    PENDING.pop(tg_id, None)
    try:
        h, m = map(int, text.strip().split(":"))
        assert 0 <= h < 24 and 0 <= m < 60
    except Exception:
        log.warning("%s set_time sai định dạng: %r", user_tag(tg_id), text)
        await update.message.reply_text("❌ Định dạng sai. VD: 20:30",
                                        reply_markup=kb_main(True))
        return
    db_set_time(tg_id, h, m)
    await reschedule_user_job(context.application, tg_id, h, m)
    log.info("%s set_time OK -> %02d:%02d", user_tag(tg_id), h, m)
    await update.message.reply_text(
        f"⏰ Đã đổi giờ nhắc thành *{h:02d}:{m:02d}*.",
        parse_mode="Markdown",
        reply_markup=kb_main(True),
    )


# ================== TEXT HANDLER ==================
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    text = (update.message.text or "").strip()

    waiter = OTP_WAITERS.get(tg_id)
    if waiter:
        if text.isdigit() and len(text) in (6, 8):
            waiter["value"] = text
            waiter["event"].set()
            log.info("%s Nhận OTP từ text handler", user_tag(tg_id))
            await update.message.reply_text("✅ Đã nhận OTP, đang xác thực...")
        else:
            await update.message.reply_text("⚠️ OTP phải là 6-8 chữ số. Thử lại.")
        return

    state = PENDING.get(tg_id)
    if state:
        action = state.get("action")
        if action == "login_user":
            await handle_login_user(update, tg_id, text); return
        if action == "login_pass":
            await handle_login_pass(update, context, tg_id, text); return
        if action == "set_time":
            await handle_set_time(update, context, tg_id, text); return

    log.info("%s on_text (không có state): %r", user_tag(tg_id), text[:50])
    await update.message.reply_text("ℹ️ Nhấn /start để mở menu.",
                                    reply_markup=kb_main(db_get(tg_id) is not None))


# ================== CALLBACK HANDLER ==================
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tg_id = q.from_user.id
    data = q.data or ""
    log.info("%s callback data=%s", user_tag(tg_id), data)

    try:
        if data == "m:home":
            PENDING.pop(tg_id, None)
            await show_home(q, context, tg_id); return
        if data == "m:login":
            await start_login_flow(q, tg_id); return
        if data == "m:logout":
            db_delete(tg_id)
            PENDING.pop(tg_id, None)
            log.info("%s logout qua nút", user_tag(tg_id))
            await q.edit_message_text("🚪 Đã xoá liên kết Telegram ↔ HRM.",
                                      reply_markup=kb_main(False))
            return
        if data == "m:list":
            await action_list(q, context, tg_id); return
        if data == "m:draft":
            await action_draft(q, context, tg_id); return
        if data == "m:submit_today":
            await action_submit_today(q, context, tg_id); return
        if data == "m:me":
            await action_me(q, context, tg_id); return
        if data == "m:settings":
            await action_settings(q, context, tg_id); return
        if data == "m:cutoff":
            await action_cutoff(q, context, tg_id); return
        if data == "m:workday":
            await action_workday_select(q, context, tg_id); return

        if data == "s:time":
            await start_settime_flow(q, tg_id); return

        if data.startswith("ds:"):
            await action_submit_one(q, context, tg_id, data[3:]); return

        if data.startswith("co:"):
            await action_cutoff_detail(q, context, tg_id, data[3:]); return

        if data.startswith("wd:"):
            await action_workday_detail(q, context, tg_id, data[3:]); return

        if data == "ot:yes":
            await action_submit_today_cb(q, context, tg_id); return
        if data == "ot:no":
            log.info("%s reminder: user chọn KHÔNG gửi", user_tag(tg_id))
            await q.edit_message_text("👌 OK, không gửi tăng ca lúc này.")
            return

        log.warning("%s callback không hợp lệ: %s", user_tag(tg_id), data)
        await q.edit_message_text("⚠️ Hành động không hợp lệ.", reply_markup=kb_main(True))
    except Exception as e:
        log.exception("%s Callback error data=%s", user_tag(tg_id), data)
        try:
            await q.edit_message_text(f"❌ Lỗi: {e}", reply_markup=kb_main(True))
        except Exception:
            pass


async def action_submit_today_cb(query, context, tg_id):
    """Submit từ luồng nhắc nhở hằng ngày — gửi các nháp TRƯỚC HÔM NAY."""
    log.info("%s action=submit_from_reminder", user_tag(tg_id))
    await query.edit_message_text("⏳ Đang gửi duyệt bản nháp...")
    client, _ = await ensure_logged_in(context, tg_id)
    if not client:
        await query.edit_message_text("❌ Không đăng nhập được.")
        return
    try:
        items = await asyncio.to_thread(client.list_overtime)
        drafts = [x for x in items if is_draft(x) and is_before_today(x)]
        log.info("%s submit_from_reminder — %d nháp cần gửi", user_tag(tg_id), len(drafts))
        if not drafts:
            await query.edit_message_text("📭 Không có bản nháp nào trước hôm nay.")
            return
        ids = [x["ID"] for x in drafts]
        res = await asyncio.to_thread(client.submit_overtime, ids)
        log.info("%s submit_from_reminder THÀNH CÔNG — %d bản, status=%s",
                 user_tag(tg_id), len(drafts), res.get("Status"))
        await query.edit_message_text(
            f"✅ Đã gửi *{len(drafts)}* bản nháp.\nServer: `{res.get('Status')}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        log.exception("%s submit_from_reminder THẤT BẠI", user_tag(tg_id))
        await query.edit_message_text(f"❌ Lỗi: {e}")


# ================== ERROR HANDLER ==================
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Exception khi xử lý update:", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(
                update.effective_chat.id,
                f"⚠️ Có lỗi xảy ra: {context.error}",
            )
    except Exception:
        pass