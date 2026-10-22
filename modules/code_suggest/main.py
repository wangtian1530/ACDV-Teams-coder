from core.loader import ModuleBase
import json
import os
import re


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
        print(f"[{self.name}] loaded — data dir: {self._data_dir}")

    def on_settings_changed(self, new_settings):
        # Nothing to invalidate — cache is per language DB, not settings
        pass

    # ─── Routes ───────────────────────────────────────────
    def languages(self, req):
        langs = []
        if os.path.isdir(self._data_dir):
            for n in sorted(os.listdir(self._data_dir)):
                if n.endswith(".json"):
                    langs.append(n[:-5])
        return {"ok": True, "languages": langs}

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
                trig = sn.get("trigger", "")
                if trig.lower().startswith(pl):
                    add({
                        "label":  trig,
                        "type":   "snippet",
                        "detail": sn.get("description", "snippet"),
                        "insert": sn.get("insert", trig),
                        "priority": 10 if trig.lower() == pl else 5,
                    })

        # ── local symbols (từ chính file đang mở) ─────────
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

        # sort by priority desc, rồi alpha
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
            "bash": [
                r"^\s*(?:function\s+)?([A-Za-z_]\w*)\s*\(\)",
                r"^\s*(?:local\s+|export\s+|readonly\s+|declare\s+)?([A-Za-z_]\w*)\s*=",
            ],
        }
        found = set()
        for pat in patterns.get(lang, []):
            for m in re.finditer(pat, content, re.MULTILINE):
                found.add(m.group(1))
        return sorted(found)