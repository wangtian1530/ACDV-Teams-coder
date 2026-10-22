"""Inline keyboard builders cho bot Telegram."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from formatters import fmt_hours


def kb_main(logged_in: bool) -> InlineKeyboardMarkup:
    if not logged_in:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 Đăng nhập HRM", callback_data="m:login")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Danh sách tăng ca", callback_data="m:list")],
        [InlineKeyboardButton("📝 Bản nháp",  callback_data="m:draft")],
        [InlineKeyboardButton("✅ Gửi duyệt (trước hôm nay)", callback_data="m:submit_today")],
        [InlineKeyboardButton("📊 Bảng công chi tiết", callback_data="m:workday")],
        [InlineKeyboardButton("📅 Kỳ chốt công",     callback_data="m:cutoff")],
        [InlineKeyboardButton("👤 Tài khoản", callback_data="m:me"),
         InlineKeyboardButton("⚙️ Cài đặt",   callback_data="m:settings")],
        [InlineKeyboardButton("🚪 Đăng xuất", callback_data="m:logout")],
    ])


def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Quay lại", callback_data="m:home")]])


def kb_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Huỷ", callback_data="m:home")]])


def kb_settings(row) -> InlineKeyboardMarkup:
    h, m = row["notify_hour"], row["notify_min"]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏰ Đổi giờ nhắc ({h:02d}:{m:02d})", callback_data="s:time")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="m:home")],
    ])


def kb_drafts(drafts) -> InlineKeyboardMarkup:
    rows = []
    for it in drafts[:10]:
        short = str(it.get("ID", ""))[:8]
        rows.append([InlineKeyboardButton(
            f"✅ Gửi {short} ({fmt_hours(it.get('RegisterHours'))})",
            callback_data=f"ds:{it['ID']}"
        )])
    rows.append([InlineKeyboardButton("📤 Gửi TẤT CẢ nháp (trước hôm nay)",
                                      callback_data="m:submit_today")])
    rows.append([InlineKeyboardButton("🔙 Quay lại", callback_data="m:home")])
    return InlineKeyboardMarkup(rows)


def kb_reminder() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Có, gửi duyệt", callback_data="ot:yes"),
        InlineKeyboardButton("❌ Không",         callback_data="ot:no"),
    ]])


def kb_cutoff(periods, current_idx) -> InlineKeyboardMarkup:
    rows = []
    for i, p in enumerate(periods[:4]):
        mark = "✅ " if i == current_idx else ""
        name = p.get("CutOffDurationName", "?")
        rows.append([InlineKeyboardButton(f"{mark}{name}",
                                          callback_data=f"co:{i}")])
    if len(periods) > 4:
        rows.append([InlineKeyboardButton("📜 Xem tất cả kỳ",
                                          callback_data="co:all")])
    rows.append([InlineKeyboardButton("🔙 Quay lại", callback_data="m:home")])
    return InlineKeyboardMarkup(rows)


def kb_workday_cutoffs(periods, current_idx=-1) -> InlineKeyboardMarkup:
    """Chọn kỳ chốt công để xem bảng công chi tiết."""
    rows = []
    for i, p in enumerate(periods[:6]):
        mark = "🟢 " if i == current_idx else ""
        name = p.get("CutOffDurationName", "?")
        rows.append([InlineKeyboardButton(f"{mark}{name}",
                                          callback_data=f"wd:{i}")])
    rows.append([InlineKeyboardButton("🔙 Quay lại", callback_data="m:home")])
    return InlineKeyboardMarkup(rows)