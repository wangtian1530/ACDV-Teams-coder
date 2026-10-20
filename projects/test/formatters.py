"""Các hàm format / phân loại item tăng ca + bảng công chi tiết."""
import logging
from datetime import datetime, timedelta

from config import TZ

log = logging.getLogger("hrm-bot")


# ---------- escape ----------
def md_escape(s) -> str:
    return (str(s)
            .replace("_", "\\_")
            .replace("*", "\\*")
            .replace("`", "\\`")
            .replace("[", "\\["))


# ---------- phân loại trạng thái ----------
def is_draft(item) -> bool:
    return item.get("Status") in ("E_SUBMIT_TEMP",)


def _item_date(item):
    wd = item.get("WorkDate")
    if not wd:
        return None
    try:
        dt = datetime.fromisoformat(wd.replace("Z", "+00:00"))
        return dt.astimezone(TZ).date()
    except Exception:
        return None


def is_today(item) -> bool:
    d = _item_date(item)
    return d is not None and d == datetime.now(TZ).date()


def is_tomorrow(item) -> bool:
    """True nếu item có WorkDate là ngày mai (theo giờ VN)."""
    d = _item_date(item)
    if d is None:
        return False
    return d == (datetime.now(TZ).date() + timedelta(days=1))


def is_before_today(item) -> bool:
    d = _item_date(item)
    return d is not None and d < datetime.now(TZ).date()


# ---------- format ----------
def fmt_hours(h) -> str:
    try:
        return f"{float(h):.1f}h"
    except Exception:
        return str(h)


def short_item(item) -> str:
    wd = item.get("WorkDate", "")
    try:
        d = datetime.fromisoformat(wd.replace("Z", "+00:00")).astimezone(TZ)
        dt = d.strftime("%d/%m %H:%M")
    except Exception:
        dt = wd
    status = md_escape(item.get("StatusView", "?"))
    return (f"• `{item.get('ID','')[:8]}` {dt}  "
            f"{fmt_hours(item.get('RegisterHours'))}  "
            f"[{status}]")


def parse_utc(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def fmt_remain(delta_seconds: float) -> str:
    if delta_seconds <= 0:
        return "đã kết thúc"
    days = int(delta_seconds // 86400)
    hours = int((delta_seconds % 86400) // 3600)
    minutes = int((delta_seconds % 3600) // 60)
    if days >= 1:
        return f"còn {days} ngày {hours} giờ"
    if hours >= 1:
        return f"còn {hours} giờ {minutes} phút"
    return f"còn {minutes} phút"


# ================= BẢNG CÔNG CHI TIẾT =================
_VN_DAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]

# Hệ số tăng ca theo quy định công ty
OT_RATE_WEEKDAY  = 1.5   # T2–T6
OT_RATE_SATURDAY = 1.5   # Thứ 7
OT_RATE_SUNDAY   = 2.0   # Chủ nhật


def _parse_day_iso(day):
    for k in ("BeginShift", "Start", "EndShift"):
        iso = day.get(k)
        if not iso:
            continue
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)
        except Exception:
            continue
    return None


def _find_last_two_saturdays(days):
    sat_dates = []
    for d in days:
        dt = _parse_day_iso(d)
        if dt is None:
            continue
        if dt.weekday() == 5:
            sat_dates.append(dt.date())
    sat_dates = sorted(set(sat_dates), reverse=True)
    return set(sat_dates[:2])


def _classify_day(dt, last_two_sats):
    if dt is None:
        return "weekday"
    wd = dt.weekday()
    if wd == 6:
        return "sunday"
    if wd == 5 and dt.date() in last_two_sats:
        return "saturday"
    return "weekday"


def _ot_rate_for(category: str) -> float:
    if category == "sunday":
        return OT_RATE_SUNDAY
    if category == "saturday":
        return OT_RATE_SATURDAY
    return OT_RATE_WEEKDAY


def _day_status_icon(day) -> str:
    """Icon + label ngắn mô tả trạng thái ngày công."""
    day_type  = day.get("DayType") or ""
    type_view = (day.get("TypeView") or "").strip()
    is_leave  = day.get("IsLeaveday")
    is_lack   = day.get("IsLackWorkday")
    is_off    = day.get("IsWorkingDay") is False and day_type == "OFF"
    is_holiday = day_type == "E_HOLIDAY"
    is_work    = day.get("IsWorkingDay") or day_type == "Working"

    try:
        ot_h = float(day.get("OvertimeConfirmMasterByDate") or 0.0)
    except Exception:
        ot_h = 0.0

    if is_holiday:
        return "🎉", "Ngày lễ"
    if is_leave:
        return "📝", "Nghỉ phép"
    if is_lack:
        return "⚠️", "Thiếu chấm công"
    if is_off and ot_h > 0:
        return "🕐", "Nghỉ + OT"
    if is_off:
        return "🏖", "Nghỉ"
    if is_work and ot_h > 0:
        return "🕐", "Đi làm + OT"
    if is_work:
        return "✅", "Đi làm"
    if type_view:
        return "▫️", type_view
    return "▫️", "—"


def _extract_day_info(day, last_two_sats):
    """Bóc tách 1 item ListWorkdayByDate thành dict gọn để hiển thị."""
    dt = _parse_day_iso(day)
    if dt is None:
        return None

    cat = _classify_day(dt, last_two_sats)

    # --- Giờ OT ---
    # OvertimeConfirmMasterByDate = giờ đã XÁC NHẬN (đã tự = 0 nếu bị từ chối/hủy)
    try:
        ot_confirmed = float(day.get("OvertimeConfirmMasterByDate") or 0.0)
    except Exception:
        ot_confirmed = 0.0

    # OvertimeByDate = giờ ĐĂNG KÝ (chỉ tham khảo)
    try:
        ot_registered = float(day.get("OvertimeByDate") or 0.0)
    except Exception:
        ot_registered = 0.0

    ot_status = day.get("OvertimeStatus") or ""

    try:
        work_h = float(day.get("WorkPaidHours") or 0.0)
    except Exception:
        work_h = 0.0

    # Nghỉ không lương
    try:
        lm = float(day.get("LeavedayMasterByDate") or 0.0)
        pl = float(day.get("PaidLeavedayByDate") or 0.0)
        unpaid = max(0.0, lm - pl)
    except Exception:
        unpaid = 0.0

    icon, label = _day_status_icon(day)
    rate = _ot_rate_for(cat)

    return {
        "date":          dt.date(),
        "weekday":       _VN_DAYS[dt.weekday()],
        "icon":          icon,
        "label":         label,
        "ot_registered": ot_registered,
        "ot_confirmed":  ot_confirmed,
        "ot_rate":       rate,
        "ot_pay_hours":  ot_confirmed * rate,
        "ot_hours":      ot_confirmed,     # alias
        "ot_category":   cat,
        "ot_status":     ot_status,
        "work_hours":    work_h,
        "unpaid":        unpaid,
        "shift_view":    (f"{day.get('StartShiftView','?')}-{day.get('EndShiftView','?')}"
                          if day.get("StartShiftView") else ""),
        "checkin":       day.get("InTimeView") or "",
        "checkout":      day.get("OuttimeView") or "",
        "raw_day":       day,
    }


def calc_workday_stats(profile: dict) -> dict:
    """Tính toán thống kê công + tăng ca theo CÔNG THỨC CHUẨN công ty.

    • T2–T6 : giờ đã xác nhận × 1.5
    • Thứ 7 : giờ đã xác nhận × 1.5
    • CN    : giờ đã xác nhận × 2.0

    Chỉ tính OT có `OvertimeStatus = E_APPROVED`.
    """
    days = profile.get("ListWorkdayByDate") or []
    last_two_sats = _find_last_two_saturdays(days)
    tg = profile.get("CodeEmp", "?")

    wd_h = sat_h = sun_h = 0.0        # giờ OT đã xác nhận
    wd_reg = sat_reg = sun_reg = 0.0  # giờ OT đăng ký
    unpaid_leave = 0.0

    day_infos = []

    for d in days:
        info = _extract_day_info(d, last_two_sats)
        if info is None:
            continue
        day_infos.append(info)

        h   = info["ot_confirmed"]
        hr  = info["ot_registered"]
        cat = info["ot_category"]

        if cat == "sunday":
            sun_h   += h
            sun_reg += hr
        elif cat == "saturday":
            sat_h   += h
            sat_reg += hr
        else:
            wd_h   += h
            wd_reg += hr

        unpaid_leave += info["unpaid"]

    day_infos.sort(key=lambda x: x["date"])

    # --- Quy đổi giờ hưởng lương ---
    wd_pay    = wd_h  * OT_RATE_WEEKDAY
    sat_pay   = sat_h * OT_RATE_SATURDAY
    sun_pay   = sun_h * OT_RATE_SUNDAY
    total_pay = wd_pay + sat_pay + sun_pay

    total_raw = wd_h + sat_h + sun_h
    total_reg = wd_reg + sat_reg + sun_reg

    # --- Đối chiếu với HRM ---
    hrm_reported = float(profile.get("TotalOvertimeHours") or 0.0)
    reconcile_note = ""
    diff_hrm = hrm_reported - total_reg
    if abs(diff_hrm) > 0.01:
        reconcile_note = (
            f"ℹ️ HRM báo `{hrm_reported:.2f}h` OT đăng ký "
            f"(chênh `{diff_hrm:+.2f}h` so với OT đã duyệt "
            f"`{total_reg:.2f}h` — có thể do OT bị hủy/từ chối)"
        )

    log.info(
        "[workday] %s: wd=%.3f sat=%.3f sun=%.3f | raw=%.3f pay=%.3f (HRM=%.2f)",
        tg, wd_h, sat_h, sun_h, total_raw, total_pay, hrm_reported,
    )

    return {
        "employee_id":       profile.get("CodeEmp"),
        "profile_name":      profile.get("ProfileName"),
        "org":               profile.get("OrgStructureName"),
        "position":          profile.get("PositionName"),
        "job_title":         profile.get("JobTitleName"),
        "standard_workdays": float(profile.get("StandardWorkdayCount") or 0.0),
        "actual_workdays":   float(profile.get("TotalWorkingDaysForPayroll")
                                   or profile.get("TotalPaidWorkDays") or 0.0),
        "unpaid_leave_days": unpaid_leave,
        "day_off":           float(profile.get("TotalDayOff") or 0.0),
        "lack_work_count":   int(profile.get("LackWorkCount") or 0),
        "late_early_count":  int(profile.get("TotalLateEarlyCount") or 0),
        "total_leave_days":  float(profile.get("TotalLeaveDays") or 0.0),
        "overtime": {
            # Giờ OT thô đã xác nhận
            "weekday_hours":   wd_h,
            "saturday_hours":  sat_h,
            "sunday_hours":    sun_h,
            "total_hours":     total_raw,
            # Hệ số
            "weekday_rate":    OT_RATE_WEEKDAY,
            "saturday_rate":   OT_RATE_SATURDAY,
            "sunday_rate":     OT_RATE_SUNDAY,
            # Giờ quy đổi hưởng lương
            "weekday_pay_hours":  wd_pay,
            "saturday_pay_hours": sat_pay,
            "sunday_pay_hours":   sun_pay,
            "total_pay_hours":    total_pay,
            # Đăng ký (tham khảo)
            "weekday_registered":  wd_reg,
            "saturday_registered": sat_reg,
            "sunday_registered":   sun_reg,
            "total_registered":    total_reg,
            "hrm_reported":        hrm_reported,
        },
        "last_two_saturdays": sorted(last_two_sats),
        "status_view":        profile.get("StatusView"),
        "reconcile_note":     reconcile_note,
        "day_infos":          day_infos,
    }


def fmt_workday_stats(stats: dict, cutoff_name: str = "") -> str:
    """Format dict thống kê -> text Markdown cho Telegram."""
    ot = stats.get("overtime") or {}

    lines = ["📊 *Bảng công chi tiết*"]
    if cutoff_name:
        lines.append(f"_Kỳ chốt: {md_escape(cutoff_name)}_")

    lines.append("")
    lines.append(
        f"👤 *{md_escape(stats.get('profile_name') or '?')}* "
        f"(`{md_escape(stats.get('employee_id') or '?')}`)"
    )
    if stats.get("org"):
        lines.append(f"🏢 {md_escape(stats['org'])}")
    if stats.get("position"):
        lines.append(f"💼 {md_escape(stats['position'])}")
    if stats.get("status_view"):
        lines.append(f"📌 Trạng thái: {md_escape(stats['status_view'])}")

    lines += [
        "",
        "📅 *Công*",
        f"  • Chuẩn: `{stats['standard_workdays']:.2f}` ngày",
        f"  • Thực tế (hưởng lương): `{stats['actual_workdays']:.2f}` ngày",
        f"  • Nghỉ không lương: `{stats['unpaid_leave_days']:.2f}` ngày",
        f"  • Ngày nghỉ cố định: `{stats['day_off']:.2f}` ngày",
        f"  • Thiếu chấm công: `{stats['lack_work_count']}` lần",
    ]
    if stats.get("late_early_count"):
        lines.append(f"  • Đi muộn / về sớm: `{stats['late_early_count']}` lần")

    wd_h  = ot.get("weekday_hours", 0.0)
    sat_h = ot.get("saturday_hours", 0.0)
    sun_h = ot.get("sunday_hours", 0.0)
    total = ot.get("total_hours", wd_h + sat_h + sun_h)

    wd_pay    = ot.get("weekday_pay_hours",  wd_h  * OT_RATE_WEEKDAY)
    sat_pay   = ot.get("saturday_pay_hours", sat_h * OT_RATE_SATURDAY)
    sun_pay   = ot.get("sunday_pay_hours",   sun_h * OT_RATE_SUNDAY)
    total_pay = ot.get("total_pay_hours", wd_pay + sat_pay + sun_pay)

    lines += [
        "",
        "⏰ *Tăng ca* (giờ đã xác nhận × hệ số)",
        f"  • Ngày thường: `{wd_h:.2f}h` × `1.5` = `{wd_pay:.2f}h`",
        f"  • Thứ Bảy:      `{sat_h:.2f}h` × `1.5` = `{sat_pay:.2f}h`",
        f"  • Chủ nhật:     `{sun_h:.2f}h` × `2.0` = `{sun_pay:.2f}h`",
        f"  • *Tổng thô:* `{total:.2f}h`  →  *Tổng hưởng lương:* `{total_pay:.2f}h`",
    ]

    sat_list = stats.get("last_two_saturdays") or []
    if sat_list:
        sat_str = ", ".join(d.strftime("%d/%m") for d in sat_list)
        lines.append(f"  _↳ 2 Thứ Bảy cuối kỳ: {sat_str}_")

    # ---------- CHI TIẾT TỪNG NGÀY ----------
    day_infos = stats.get("day_infos") or []
    if day_infos:
        lines.append("")
        lines.append("🗓 *Chi tiết từng ngày:*")
        lines.append("```")
        lines.append("Ngày       Trạng thái          Ca           OT")
        lines.append("────────────────────────────────────────────────")
        for info in day_infos:
            d_str = f"{info['date'].strftime('%d/%m')} {info['weekday']}"
            icon  = info["icon"]
            label = (info["label"] or "")[:16].ljust(16)
            shift = (info["shift_view"] or "—")[:12].ljust(12)

            if info["ot_confirmed"] > 0:
                ot_str = f"+{info['ot_confirmed']:.2f}h"
            elif info["ot_registered"] > 0:
                ot_str = f"✗{info['ot_registered']:.1f}h"  # bị hủy/từ chối
            else:
                ot_str = ""

            lines.append(f"{d_str:<9} {icon} {label} {shift} {ot_str}")
        lines.append("```")

    note = stats.get("reconcile_note")
    if note:
        lines.append("")
        lines.append(f"_{note}_")

    return "\n".join(lines)