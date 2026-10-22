"""
function_suggester — Quét toàn bộ projects/, index hàm theo (ngôn ngữ, project),
đề xuất hàm cùng ngôn ngữ kèm chữ ký + tham số mẫu + vị trí file.

Route chính:
  POST /api/function_suggester/suggest
    body: { "project": "my_proj", "path": "src/app.py", "prefix": "get_"(optional) }
    resp: { ok, lang, count, suggestions: [ { name, signature, params,
                                               sample_call, line, project,
                                               file, language } ] }
"""

from core.loader import ModuleBase
import os
import re
import ast
import threading


# ─── Language detection ─────────────────────────────────
LANG_MAP = {
    ".py":   "python",
    ".js":   "javascript",
    ".jsx":  "javascript",
    ".mjs":  "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".java": "java",
    ".go":   "go",
    ".rb":   "ruby",
    ".php":  "php",
    ".c":    "c",
    ".h":    "c",
    ".cpp":  "cpp",
    ".cc":   "cpp",
    ".hpp":  "cpp",
    ".cs":   "csharp",
    ".rs":   "rust",
    ".kt":   "kotlin",
    ".swift":"swift",
}

SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", ".venv", "venv",
    "dist", "build", "target", "out", ".idea", ".vscode",
}


class Module(ModuleBase):

    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except (TypeError, AttributeError):
            pass
        self._index = {}                       # { project: { lang: [func, ...] } }
        self._lock  = threading.RLock()

    # ─── Lifecycle ──────────────────────────────────────
    def on_load(self):
        print(f"[{self.name}] loaded — project root: {self._projects_root()}")
        if self.get_settings().get("auto_scan_on_start", True):
            self._safe_scan()

    def on_recovery(self):
        if self.get_settings().get("auto_scan_on_start", True):
            self._safe_scan()

    # ─── Routes ─────────────────────────────────────────
    def scan_project(self, req):
        project = (req.get("body") or {}).get("project")
        if not project:
            return self._scan_all_projects()
        return self._scan_one(project)

    def refresh_index(self, req):
        return self._scan_all_projects()

    def get_index(self, req):
        self._ensure_index()
        with self._lock:
            summary = {
                proj: {lang: len(fs) for lang, fs in langmap.items()}
                for proj, langmap in self._index.items()
            }
        return {"ok": True, "summary": summary}

    def suggest_for_file(self, req):
        body = req.get("body") or {}
        project = body.get("project")
        path    = body.get("path", "")
        prefix  = body.get("prefix", "")

        if not project or not path:
            return {"ok": False, "error": "project + path required"}

        lang = self._detect_lang(path)
        if not lang:
            return {"ok": False, "error": f"unknown language for '{path}'"}

        self._ensure_index()
        max_n           = int(self.get_settings().get("max_suggestions", 20))
        include_private = bool(self.get_settings().get("include_private", False))
        excl_current    = bool(self.get_settings().get("exclude_current_file", False))
        current_rel     = f"{project}/{path}".replace("\\", "/")

        candidates = []
        with self._lock:
            for proj, langmap in self._index.items():
                for f in langmap.get(lang, []):
                    if not include_private and f["name"].startswith("_"):
                        continue
                    if excl_current and f["file"] == current_rel:
                        continue
                    if prefix and not f["name"].lower().startswith(prefix.lower()):
                        continue
                    candidates.append(f)

        # Sort: same project first, same file last, rồi theo tên
        candidates.sort(key=lambda f: (
            f["project"] != project,
            f["file"] == current_rel,
            f["name"].lower(),
        ))

        return {
            "ok": True,
            "lang": lang,
            "count": len(candidates[:max_n]),
            "suggestions": candidates[:max_n],
        }

    # ─── UI Buttons ─────────────────────────────────────
    def on_button_rescan(self, params):
        return self._scan_all_projects()

    def on_button_show_index(self, params):
        return self.get_index({"body": {}})

    # ─── Empty diagnose (contract yêu cầu nếu khai) ─────
    def diagnose(self, project, path, content):
        return []

    # ─── Internal: paths ────────────────────────────────
    def _projects_root(self):
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(here))       # modules/<name>/.. → project root
        return os.path.join(root, "projects")

    def _detect_lang(self, path):
        return LANG_MAP.get(os.path.splitext(path)[1].lower())

    # ─── Internal: scan ─────────────────────────────────
    def _safe_scan(self):
        try:
            self._scan_all_projects()
        except Exception as e:
            print(f"[{self.name}] auto scan failed: {e}")

    def _scan_all_projects(self):
        root = self._projects_root()
        if not os.path.isdir(root):
            return {"ok": False, "error": f"projects dir not found: {root}"}

        new_index = {}
        n_proj = 0
        n_fn   = 0
        for proj in sorted(os.listdir(root)):
            pdir = os.path.join(root, proj)
            if not os.path.isdir(pdir) or proj.startswith("."):
                continue
            langmap = self._scan_dir(pdir)
            new_index[proj] = langmap
            n_proj += 1
            n_fn   += sum(len(v) for v in langmap.values())

        with self._lock:
            self._index = new_index
        return {"ok": True, "projects_scanned": n_proj, "functions_found": n_fn}

    def _scan_one(self, project):
        root = os.path.join(self._projects_root(), project)
        if not os.path.isdir(root):
            return {"ok": False, "error": f"project not found: {project}"}
        langmap = self._scan_dir(root)
        with self._lock:
            self._index[project] = langmap
        return {
            "ok": True, "project": project,
            "functions_found": sum(len(v) for v in langmap.values())
        }

    def _scan_dir(self, root_abs):
        """Trả về {lang: [func_dict, ...]} — quét đệ quy 1 project."""
        langmap = {}
        projects_root = self._projects_root()
        for dirpath, dirnames, filenames in os.walk(root_abs):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                lang = self._detect_lang(fn)
                if not lang:
                    continue
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                except Exception:
                    continue
                rel = os.path.relpath(full, projects_root).replace("\\", "/")
                try:
                    if lang == "python":
                        found = self._parse_python(content, rel)
                    elif lang in ("javascript", "typescript"):
                        found = self._parse_js(content, rel, lang)
                    elif lang == "go":
                        found = self._parse_go(content, rel)
                    elif lang in ("java", "csharp", "kotlin"):
                        found = self._parse_braced(content, rel, lang,
                            r'(?:public|private|protected|static|final|synchronized|abstract|override|\s)+'
                            r'[\w<>\[\],\.\s]+\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\{')
                    elif lang in ("c", "cpp"):
                        found = self._parse_braced(content, rel, lang,
                            r'(?:^|\n)[ \t]*(?:static\s+|inline\s+|virtual\s+|extern\s+)?'
                            r'[\w<>:,\[\]\*\s&]+\s+(\w+)\s*\(([^)]*)\)\s*\{')
                    else:
                        continue
                except Exception as e:
                    print(f"[{self.name}] parse fail {rel}: {e}")
                    continue
                if found:
                    langmap.setdefault(lang, []).extend(found)
        return langmap

    # ─── Parsers ────────────────────────────────────────
    def _parse_python(self, content, rel):
        funcs = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._parse_python_regex(content, rel)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info = self._extract_py_args(node.args)
                qual = self._python_qualname(tree, node)
                funcs.append({
                    "name":       node.name,
                    "signature":  f"def {qual}({info['signature']}):",
                    "params":     info["params"],
                    "sample_call":f"{node.name}({info['sample_args']})",
                    "line":       node.lineno,
                    "file":       rel,
                    "language":   "python",
                })
        return funcs

    def _python_qualname(self, tree, target):
        """Ghép Class.method nếu có."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if sub is target:
                        return f"{node.name}.{target.name}"
        return target.name

    def _extract_py_args(self, args):
        parts, params = [], []
        posonly  = list(getattr(args, "posonlyargs", []) or [])
        regular  = list(args.args or [])
        defaults = list(args.defaults or [])
        all_pos  = posonly + regular
        offset   = len(all_pos) - len(defaults)

        for i, a in enumerate(all_pos):
            p = {"name": a.arg, "kind": "positional"}
            if i >= offset:
                dv = defaults[i - offset]
                try:
                    p["default"] = repr(ast.literal_eval(dv))
                except Exception:
                    p["default"] = "<expr>"
            params.append(p)
            parts.append(f"{a.arg}={p['default']}" if "default" in p else a.arg)

        if args.vararg:
            params.append({"name": args.vararg.arg, "kind": "vararg"})
            parts.append(f"*{args.vararg.arg}")

        if args.kwonlyargs:
            parts.append("*")
            for i, a in enumerate(args.kwonlyargs):
                p = {"name": a.arg, "kind": "kwonly"}
                kwd = (args.kw_defaults or [None])[i] if i < len(args.kw_defaults or []) else None
                if kwd is not None:
                    try:
                        p["default"] = repr(ast.literal_eval(kwd))
                    except Exception:
                        p["default"] = "<expr>"
                    parts.append(f"{a.arg}={p['default']}")
                else:
                    parts.append(a.arg)
                params.append(p)

        if args.kwarg:
            params.append({"name": args.kwarg.arg, "kind": "kwarg"})
            parts.append(f"**{args.kwarg.arg}")

        sample_args = ", ".join(
            self._sample_value(p) for p in params
            if p["kind"] in ("positional", "kwonly") and "default" not in p
        )
        return {"signature": ", ".join(parts), "params": params, "sample_args": sample_args}

    def _parse_python_regex(self, content, rel):
        """Fallback khi ast.parse fail (vd. syntax Python mới hơn, mixed)."""
        funcs = []
        pat = re.compile(r'^\s*(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)', re.MULTILINE)
        for m in pat.finditer(content):
            name, raw = m.group(1), m.group(2).strip()
            line = content[:m.start()].count("\n") + 1
            params, sample_parts = [], []
            for p in self._split_args(raw):
                p = p.strip()
                if not p or p in ("self", "cls"):
                    continue
                if "=" in p:
                    pname, pdef = p.split("=", 1)
                    pname = pname.split(":")[0].strip()
                    params.append({"name": pname, "default": pdef.strip(), "kind": "positional"})
                else:
                    raw_p = p.lstrip("*")
                    pname = raw_p.split(":")[0].strip()
                    kind = "vararg" if p.startswith("*") else "positional"
                    params.append({"name": pname, "kind": kind})
                    if kind == "positional":
                        sample_parts.append(self._sample_value({"name": pname, "kind": "positional"}))
            funcs.append({
                "name": name,
                "signature": f"def {name}({raw}):",
                "params": params,
                "sample_call": f"{name}({', '.join(sample_parts)})",
                "line": line, "file": rel, "language": "python",
            })
        return funcs

    def _parse_js(self, content, rel, lang):
        found = []
        # function foo(...)
        for m in re.finditer(r'function\s+(\w+)\s*\(([^)]*)\)', content):
            found.append(self._mk_func(m.group(1), m.group(2), content, m.start(),
                                       rel, lang, kind="js_fn"))
        # const/let/var foo = (...) =>
        arrow = r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function\s*)?\(([^)]*)\)\s*(?:=>|{)'
        for m in re.finditer(arrow, content):
            found.append(self._mk_func(m.group(1), m.group(2), content, m.start(),
                                       rel, lang, kind="js_arrow"))
        # method trong class: 2+ spaces, name(...)
        method = r'^\s{2,}(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?(\w+)\s*\(([^)]*)\)\s*\{'
        for m in re.finditer(method, content, re.MULTILINE):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "catch", "function", "return"):
                continue
            found.append(self._mk_func(name, m.group(2), content, m.start(),
                                       rel, lang, kind="js_method"))
        # dedupe by (name, line)
        seen, out = set(), []
        for f in found:
            key = (f["name"], f["line"])
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
        return out

    def _mk_func(self, name, raw_args, content, pos, rel, lang, kind):
        line = content[:pos].count("\n") + 1
        params, sample_parts = [], []
        for p in self._split_args(raw_args):
            p = p.strip()
            if not p:
                continue
            if "=" in p:
                pname, pdef = p.split("=", 1)
                pname = pname.split(":")[0].strip()
                params.append({"name": pname, "default": pdef.strip(), "kind": "positional"})
            else:
                raw_p = p.lstrip("*")
                pname = raw_p.split(":")[0].strip()
                params.append({"name": pname, "kind": "positional"})
                sample_parts.append(self._sample_value({"name": pname, "kind": "positional"}))

        if kind == "js_fn":
            sig = f"function {name}({raw_args})"
        elif kind == "js_method":
            sig = f"{name}({raw_args}) {{…}}"
        else:
            sig = f"const {name} = ({raw_args}) => …"
        return {
            "name": name, "signature": sig, "params": params,
            "sample_call": f"{name}({', '.join(sample_parts)})",
            "line": line, "file": rel, "language": lang,
        }

    def _parse_go(self, content, rel):
        funcs = []
        pat = re.compile(r'func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(([^)]*)\)')
        for m in pat.finditer(content):
            line = content[:m.start()].count("\n") + 1
            raw = m.group(2).strip()
            params, sample_parts = [], []
            for p in self._split_args(raw):
                p = p.strip()
                if not p:
                    continue
                toks = p.split()
                if len(toks) >= 2:
                    pname = toks[0]
                    params.append({"name": pname, "kind": "positional"})
                    sample_parts.append(self._sample_value({"name": pname, "kind": "positional"}))
            funcs.append({
                "name": m.group(1),
                "signature": f"func {m.group(1)}({raw})",
                "params": params,
                "sample_call": f"{m.group(1)}({', '.join(sample_parts)})",
                "line": line, "file": rel, "language": "go",
            })
        return funcs

    def _parse_braced(self, content, rel, lang, pattern):
        funcs = []
        for m in re.finditer(pattern, content, re.MULTILINE):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "catch", "return", "new"):
                continue
            line = content[:m.start()].count("\n") + 1
            raw  = m.group(2).strip()
            params, sample_parts = [], []
            for p in self._split_args(raw):
                p = p.strip()
                if not p or p == "void":
                    continue
                # strip annotation, keep tên biến cuối
                toks = p.replace("*", " * ").replace("&", " & ").split()
                if not toks:
                    continue
                pname = toks[-1].lstrip("*&")
                if not pname or not re.match(r'^\w+$', pname):
                    continue
                params.append({"name": pname, "kind": "positional"})
                sample_parts.append(self._sample_value({"name": pname, "kind": "positional"}))
            funcs.append({
                "name": name,
                "signature": f"{name}({raw})",
                "params": params,
                "sample_call": f"{name}({', '.join(sample_parts)})",
                "line": line, "file": rel, "language": lang,
            })
        return funcs

    # ─── Helpers ────────────────────────────────────────
    def _split_args(self, s):
        """Split top-level commas — bỏ qua nested (), [], {}, string."""
        parts, cur, depth, in_str = [], "", 0, None
        for ch in s:
            if in_str:
                cur += ch
                if ch == in_str:
                    in_str = None
                continue
            if ch in "\"'`":
                in_str = ch; cur += ch
            elif ch in "([{":
                depth += 1; cur += ch
            elif ch in ")]}":
                depth -= 1; cur += ch
            elif ch == "," and depth == 0:
                parts.append(cur); cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur)
        return parts

    def _sample_value(self, p):
        """Sinh giá trị mẫu dựa trên tên tham số + kind."""
        name = (p.get("name") or "").lower()
        if p.get("kind") not in ("positional", "kwonly"):
            return "..."
        if any(k in name for k in ("path", "filename", "filepath")):
            return '"/path/to/file"'
        if any(k in name for k in ("url", "endpoint", "uri")):
            return '"https://example.com"'
        if any(k in name for k in ("email",)):
            return '"user@example.com"'
        if any(k in name for k in ("id", "index", "idx", "count", "num", "size", "age", "port", "length", "len")):
            return "0"
        if any(k in name for k in ("name", "title", "label", "msg", "message",
                                   "text", "str", "desc", "description", "user", "username")):
            return '"example"'
        if any(k in name for k in ("flag", "is_", "has_", "enabled", "visible", "ok")):
            return "True"
        if any(k in name for k in ("list", "items", "arr", "array", "values")):
            return "[]"
        if any(k in name for k in ("dict", "data", "obj", "config", "opts", "options", "kwargs")):
            return "{}"
        return "None"

    def _ensure_index(self):
        with self._lock:
            is_empty = not self._index
        if is_empty:
            try:
                self._scan_all_projects()
            except Exception as e:
                print(f"[{self.name}] ensure_index failed: {e}")