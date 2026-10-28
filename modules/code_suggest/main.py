from core.loader import ModuleBase
import json
import os
import re


MODULE_VERSION = "1.1.0"
MODULE_AUTHOR  = "ACDV-Teams"
MODULE_TITLE   = "ACDV-Teams Code Suggest"


class Module(ModuleBase):
    """Suggestion engine: merge keywords + builtins + snippets + local symbols."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}
        self._data_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data"
        )

    # ─── Lifecycle ────────────────────────────────────────
    def on_load(self):
        print(f"[{self.name}] v{MODULE_VERSION} loaded — data dir: {self._data_dir}")

    def on_settings_changed(self, new_settings):
        # cache theo language DB, không theo settings
        pass

    # ─── Routes ───────────────────────────────────────────
    def languages(self, req):
        langs = []
        if os.path.isdir(self._data_dir):
            for n in sorted(os.listdir(self._data_dir)):
                if n.endswith(".json") and n != "settings.json":
                    langs.append(n[:-5])
        return {"ok": True, "languages": langs}

    def about(self, req):
        langs = self.languages(req).get("languages", [])
        s = self.get_settings() or {}
        return {
            "ok":          True,
            "name":        MODULE_TITLE,
            "version":     MODULE_VERSION,
            "author":      MODULE_AUTHOR,
            "copyright":   f"© 2026 {MODULE_AUTHOR} Module",
            "description": "VS Code-style autocomplete + function call templates "
                           "cho 18 ngôn ngữ. String mẫu luôn là 'ACDV-Teams'.",
            "intro_url":   "/module/code_suggest/",
            "languages":   langs,
            "language_count": len(langs),
            "features": [
                "Autocomplete từ khóa, builtins, snippets, local symbols",
                "Function templates: gõ setTimeout → full call với {}, 1000",
                "String mẫu chuẩn 'ACDV-Teams' trên mọi ngôn ngữ",
                "Hỗ trợ 18 ngôn ngữ (Python / JS / TS / C / C++ / C# / Go / Rust / Java / Kotlin / Dart / Swift / Ruby / PHP / Bash / Lua / PowerShell / SQL)",
                "Local symbol extraction (đọc hàm/biến trong file đang mở)",
                "Ctrl-Space để trigger thủ công",
                "Settings hot-apply, không cần reload trang",
            ],
            "settings": s,
        }

    def complete(self, req):
        body   = self._body(req)
        lang   = (body.get("language") or "").lower()
        prefix = body.get("prefix") or ""
        content= body.get("content") or ""

        if not lang or not prefix:
            return {"ok": True, "suggestions": []}

        s = self.get_settings() or {}
        if not s.get("enabled", True):
            return {"ok": True, "suggestions": []}

        min_prefix = int(s.get("min_prefix", 1))
        max_items  = int(s.get("max_items", 20))
        show_kw    = s.get("show_keywords", True)
        show_bi    = s.get("show_builtins", True)
        show_sn    = s.get("show_snippets", True)
        show_lo    = s.get("show_locals", True)
        show_tpl   = s.get("show_function_templates", True)

        if len(prefix) < min_prefix:
            return {"ok": True, "suggestions": []}

        data = self._load_lang(lang)
        pl   = prefix.lower()
        out, seen = [], set()

        def add(item):
            key = (item["label"], item["type"])
            if key in seen:
                return
            seen.add(key)
            out.append(item)

        # ── snippets (ưu tiên cao nhất) ───────────────────
        if show_sn:
            for sn in data.get("snippets", []):
                if sn.get("template") and not show_tpl:
                    continue
                trig = sn.get("trigger", "")
                if trig.lower().startswith(pl):
                    add({
                        "label":  trig,
                        "type":   "snippet",
                        "detail": sn.get("description", "snippet"),
                        "insert": sn.get("insert", trig),
                        "priority": 10 if trig.lower() == pl else 5,
                    })

        # ── local symbols ─────────────────────────────────
        if show_lo and content:
            for sym in self._extract_locals(lang, content):
                if sym.lower() != pl and sym.lower().startswith(pl):
                    add({
                        "label": sym,
                        "type":  "local",
                        "detail":"in this file",
                        "insert": sym,
                        "priority": 4,
                    })

        # ── keywords ──────────────────────────────────────
        if show_kw:
            for kw in data.get("keywords", []):
                if kw.lower().startswith(pl):
                    add({
                        "label": kw,
                        "type":  "keyword",
                        "detail":"keyword",
                        "insert": kw,
                        "priority": 3 if kw.lower() == pl else 1,
                    })

        # ── builtins ──────────────────────────────────────
        if show_bi:
            for b in data.get("builtins", []):
                if b.lower().startswith(pl):
                    add({
                        "label": b,
                        "type":  "builtin",
                        "detail":"builtin",
                        "insert": b,
                        "priority": 2 if b.lower() == pl else 1,
                    })

        out.sort(key=lambda x: (-x.get("priority", 0), x["label"].lower()))
        out = out[:max_items]
        for r in out:
            r.pop("priority", None)

        return {"ok": True, "suggestions": out}

    # ─── Helpers ──────────────────────────────────────────
    def _body(self, req):
        if isinstance(req, dict):
            if "body" in req:
                b = req["body"]
                if isinstance(b, str):
                    try:
                        return json.loads(b)
                    except Exception:
                        return {}
                return b or {}
            return req
        return {}

    def _load_lang(self, lang):
        if lang in self._cache:
            return self._cache[lang]
        path = os.path.join(self._data_dir, f"{lang}.json")
        if not os.path.exists(path):
            self._cache[lang] = {"keywords": [], "builtins": [], "snippets": []}
            return self._cache[lang]
        with open(path, "r", encoding="utf-8") as f:
            self._cache[lang] = json.load(f)
        return self._cache[lang]

    def _extract_locals(self, lang, content):
        patterns = {
            "python": [
                r"^\s*def\s+([A-Za-z_]\w*)",
                r"^\s*class\s+([A-Za-z_]\w*)",
                r"^\s*([A-Za-z_]\w*)\s*=",
            ],
            "javascript": [
                r"\bfunction\s+([A-Za-z_$][\w$]*)",
                r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)",
                r"\bclass\s+([A-Za-z_$][\w$]*)",
                r"\b([A-Za-z_$][\w$]*)\s*=\s*(?:function|\([^)]*\)\s*=>)",
            ],
            "typescript": [
                r"\b(?:function|class|interface|type|enum|namespace|module)\s+([A-Za-z_$][\w$]*)",
                r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)",
                r"\b([A-Za-z_$][\w$]*)\s*[:=]\s*(?:function|\([^)]*\)\s*=>|async\s*\()",
            ],
            "bash": [
                r"^\s*(?:function\s+)?([A-Za-z_]\w*)\s*\(\)",
                r"^\s*(?:local\s+|export\s+|readonly\s+|declare\s+)?([A-Za-z_]\w*)\s*=",
            ],
            "c": [
                r"#\s*define\s+([A-Za-z_]\w*)",
                r"\b(?:struct|enum|union)\s+([A-Za-z_]\w*)",
                r"\btypedef\b[^;]*\b([A-Za-z_]\w*)\s*;",
                r"^\s*(?:static\s+|extern\s+|inline\s+)*"
                r"(?:int|char|float|double|void|long|short|unsigned|signed|"
                r"size_t|ssize_t|int8_t|int16_t|int32_t|int64_t|"
                r"uint8_t|uint16_t|uint32_t|uint64_t|bool)\s+\**\s*"
                r"([A-Za-z_]\w*)\s*\(",
            ],
            "cpp": [
                r"\b(?:class|struct|enum|namespace|union)\s+([A-Za-z_]\w*)",
                r"\b(?:template\s*<[^>]*>\s*)?"
                r"(?:inline\s+|static\s+|virtual\s+|constexpr\s+|explicit\s+)*"
                r"(?:auto|void|bool|int|char|float|double|long|short|unsigned|signed|"
                r"size_t|std::\w+(?:::\w+)*)\s+[*&]*\s*"
                r"([A-Za-z_]\w*)\s*\(",
                r"\busing\s+([A-Za-z_]\w*)\s*=",
            ],
            "csharp": [
                r"\b(?:class|interface|struct|enum|record|namespace)\s+([A-Za-z_]\w*)",
                r"\b(?:public|private|protected|internal|static|async|virtual|override)\s+"
                r"[\w<>\[\],?\s]+\s+([A-Za-z_]\w*)\s*\(",
                r"\b(?:var|int|string|bool|double|float|long|decimal)\s+([A-Za-z_]\w*)\s*=",
            ],
            "dart": [
                r"\b(?:class|mixin|enum|extension|typedef)\s+([A-Za-z_]\w*)",
                r"\b(?:Future<[^>]*>|Stream<[^>]*>|void|int|double|String|bool|dynamic|var)\s+"
                r"([A-Za-z_]\w*)\s*\(",
                r"\b(?:final|const|var)\s+([A-Za-z_]\w*)\s*=",
            ],
            "go": [
                r"\bfunc\s+([A-Za-z_]\w*)",
                r"\btype\s+([A-Za-z_]\w*)",
                r"\b([A-Za-z_]\w*)\s*:=",
                r"\b(?:var|const)\s+([A-Za-z_]\w*)",
            ],
            "java": [
                r"\b(?:class|interface|enum|record|@interface)\s+([A-Za-z_]\w*)",
                r"\b(?:public|private|protected|static|final|abstract|synchronized)\s+"
                r"[\w<>\[\],?\s.]+\s+([A-Za-z_]\w*)\s*\(",
                r"\b(?:var|int|long|double|float|boolean|char|String)\s+([A-Za-z_]\w*)\s*=",
            ],
            "kotlin": [
                r"\bfun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?([A-Za-z_]\w*)",
                r"\b(?:val|var)\s+([A-Za-z_]\w*)",
                r"\b(?:class|object|interface|data\s+class|sealed\s+class|enum\s+class)\s+([A-Za-z_]\w*)",
            ],
            "lua": [
                r"\bfunction\s+(?:[\w.:]+\.)?([A-Za-z_]\w*)",
                r"\blocal\s+(?:function\s+)?([A-Za-z_]\w*)",
                r"^\s*([A-Za-z_]\w*)\s*=",
            ],
            "php": [
                r"\bfunction\s+([A-Za-z_]\w*)",
                r"\b(?:class|interface|trait|enum)\s+([A-Za-z_]\w*)",
                r"\$([A-Za-z_]\w*)\s*=",
                r"\bdefine\s*\(\s*['\"]([A-Za-z_]\w*)['\"]",
            ],
            "powershell": [
                r"^\s*function\s+([A-Za-z_][\w-]*)",
                r"^\s*\$([A-Za-z_]\w*)\s*=",
                r"^\s*class\s+([A-Za-z_]\w*)",
            ],
            "ruby": [
                r"^\s*def\s+(?:self\.)?([A-Za-z_]\w*[?!=]?)",
                r"^\s*(?:class|module)\s+([A-Za-z_]\w*(?:::\w+)*)",
                r"^\s*([A-Za-z_]\w*)\s*=",
            ],
            "rust": [
                r"\bfn\s+([A-Za-z_]\w*)",
                r"\b(?:struct|enum|trait|mod|union)\s+([A-Za-z_]\w*)",
                r"\b(?:let|const|static)\s+(?:mut\s+)?([A-Za-z_]\w*)",
                r"\bmacro_rules!\s*([A-Za-z_]\w*)",
            ],
            "sql": [
                r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|INDEX|FUNCTION|PROCEDURE)\s+"
                r"(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?([A-Za-z_]\w*)",
                r"\bAS\s+([A-Za-z_]\w*)\s*\(",
                r"\bWITH\s+([A-Za-z_]\w*)\s+AS\s*\(",
            ],
            "swift": [
                r"\bfunc\s+([A-Za-z_]\w*)",
                r"\b(?:class|struct|enum|protocol|extension|actor)\s+([A-Za-z_]\w*)",
                r"\b(?:let|var)\s+([A-Za-z_]\w*)",
            ],
        }
        found = set()
        for pat in patterns.get(lang, []):
            try:
                for m in re.finditer(pat, content, re.MULTILINE):
                    name = m.group(1)
                    if name:
                        found.add(name)
            except re.error:
                continue
        return sorted(found)