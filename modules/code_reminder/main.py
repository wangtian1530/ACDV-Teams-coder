"""
code_reminder — nhắc nhở chất lượng code.

Contract tham chiếu: README §5 (Module contract).
Không override core, không dùng API ngoài document.
"""

import re
from core.loader import ModuleBase


# --- Patterns -----------------------------------------------------------
TAG_RE     = re.compile(r'\b(TODO|FIXME|HACK|XXX|BUG|NOTE|OPTIMIZE)\b[:\s]*(.*)', re.IGNORECASE)
PRINT_RE   = re.compile(r'\bprint\s*\(')
CONSOLE_RE = re.compile(r'\bconsole\.(log|debug|info|warn|error)\s*\(')
DEBUG_RE   = re.compile(r'\b(breakpoint\s*\(|pdb\.set_trace\s*\(|debugger\b)')

# Dòng có mấy cái này thì bỏ qua check_debug (tránh báo khi test cố ý)
SKIP_DEBUG_LINE = re.compile(r'(#\s*noqa|#\s*remind|//\s*remind)', re.IGNORECASE)

# Defaults fallback — trùng với settings_schema để module tự chạy
# kể cả khi get_settings() lỗi.
DEFAULTS = {
    "enabled": True,
    "check_todo": True,
    "check_debug": True,
    "check_style": False,
    "max_line_length": 120,
    "default_severity": "warning",
}


class Module(ModuleBase):
    # ---------- Lifecycle ----------
    def on_load(self):
        print(f"[{self.name}] loaded v1.0.0")

    def on_recovery(self):
        print(f"[{self.name}] recovered after error")

    def on_shutdown(self):
        print(f"[{self.name}] shutdown")

    def on_settings_changed(self, new_settings):
        print(f"[{self.name}] settings changed: {new_settings}")

    # ---------- Routes ----------
    def ping(self, req):
        return {
            "ok": True,
            "module": self.name,
            "version": "1.0.0",
            "msg": "code_reminder alive",
        }

    def check(self, req):
        """
        POST /api/code_reminder/check
        Body: { "project": str?, "path": str?, "content": str }
        """
        body = self._body(req)
        content = body.get("content")
        if content is None:
            return {"ok": False, "error": "missing 'content' in body"}

        diags = self.diagnose(
            body.get("project"),
            body.get("path", "<inline>"),
            content,
        )
        return {"ok": True, "count": len(diags), "diagnostics": diags}

    # ---------- UI button handlers ----------
    def on_button_show_info(self, params):
        s = self._settings()
        return {
            "ok": True,
            "message": "Code reminder settings summary",
            "settings": s,
            "usage": "Save a file to auto-run. Or POST /api/code_reminder/check với {content}.",
            "supported": ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.sh"],
        }

    # ---------- Diagnostics ----------
    def diagnose(self, project, path, content):
        if not content:
            return []
        s = self._settings()
        if not s["enabled"]:
            return []

        diags = []
        lines = content.split("\n")
        default_sev = s["default_severity"]
        max_len = int(s["max_line_length"])

        for i, line in enumerate(lines, start=1):
            # TODO/FIXME/HACK...
            if s["check_todo"]:
                m = TAG_RE.search(line)
                if m:
                    tag = m.group(1).upper()
                    desc = m.group(2).strip() or "(no description)"
                    sev = "error" if tag in ("FIXME", "BUG") else "warning"
                    diags.append(self._d(
                        i, m.start() + 1, i, m.end() + 1,
                        f"[{tag}] {desc}",
                        f"REMIND-{tag}", sev,
                    ))

            # Debug leftovers
            if s["check_debug"] and not SKIP_DEBUG_LINE.search(line):
                for regex, code, msg in (
                    (PRINT_RE,   "REMIND-PRINT",   "print() — debug output, remove before commit"),
                    (CONSOLE_RE, "REMIND-CONSOLE", "console.* — debug logging, remove before commit"),
                    (DEBUG_RE,   "REMIND-DEBUG",   "breakpoint()/debugger — remove before commit"),
                ):
                    m = regex.search(line)
                    if m:
                        diags.append(self._d(
                            i, m.start() + 1, i, m.end() + 1,
                            msg, code, default_sev,
                        ))

            # Long line
            if s["check_style"] and len(line) > max_len:
                diags.append(self._d(
                    i, max_len + 1, i, len(line) + 1,
                    f"Line too long ({len(line)} > {max_len})",
                    "REMIND-LONG", "info",
                ))

        return diags

    # ---------- Error interceptor ----------
    def on_http_error(self, ctx):
        path = (ctx or {}).get("path", "")
        if "/api/code_reminder/" not in path:
            return None  # pass through
        return {
            "handled": True,
            "response": {
                "ok": False,
                "module": self.name,
                "error": f"[code_reminder] {ctx.get('error', 'unknown')}",
            },
        }

    # ---------- Helpers ----------
    def _settings(self):
        """Merge settings_schema defaults + giá trị hiện tại (nếu có)."""
        current = {}
        try:
            current = self.get_settings() or {}
        except Exception as e:
            print(f"[{self.name}] get_settings() failed: {e}")
        merged = dict(DEFAULTS)
        merged.update(current)
        return merged

    def _body(self, req):
        """Chấp nhận dict / object / None — dự phòng cho các bản core khác nhau."""
        if req is None:
            return {}
        if isinstance(req, dict):
            return req.get("body") or req.get("data") or {}
        getter = getattr(req, "get", None)
        if callable(getter):
            try:
                return getter("body") or {}
            except Exception:
                pass
        body = getattr(req, "body", None)
        return body or {}

    def _d(self, sl, sc, el, ec, msg, code, severity):
        return {
            "severity": severity,
            "line": sl, "column": sc,
            "end_line": el, "end_column": ec,
            "message": msg, "code": code,
        }