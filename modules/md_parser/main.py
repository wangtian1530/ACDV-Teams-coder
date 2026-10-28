import base64
import io
import json
import re
import zipfile
from datetime import datetime

from core.loader import ModuleBase

# Tên file / path trong 1 dòng. Có hỗ trợ dotfile.
FILE_PATTERN = re.compile(r"[A-Za-z0-9_\-./\\]+\.[A-Za-z0-9]{1,10}")
# Dotfile thuần: .env, .gitignore, .dockerignore, ...
DOTFILE_PATTERN = re.compile(r"^\.[A-Za-z0-9_\-.]{1,32}$")

# Fence ```lang\n ... ``` — MULTILINE để nhận fence có indent đầu dòng,
# và cho phép space giữa ``` và lang (ví dụ: ``` python).
FENCE_PATTERN = re.compile(
    r"^[ \t]*```[ \t]*([A-Za-z0-9_+\-.#]*)[ \t]*\r?\n(.*?)(?:^[ \t]*```|\Z)",
    re.DOTALL | re.MULTILINE,
)

# Prefix nhận diện tên file. Alternation sắp dài-trước-ngắn để tránh
# "file name" bị match nhầm thành "file". Dấu ':' là optional.
PREFIX_PATTERN = re.compile(
    r"^(?:filename|file[ _]name|tên[ _]file|ten[ _]file|"
    r"đường[ _]dẫn|duong[ _]dan|path|file)\b\s*[:：]?\s*",
    re.IGNORECASE,
)

# Chặn domain bị bắt nhầm thành tên file (example.com, foo.io, ...).
_TLD_BLACKLIST = {
    "com", "net", "org", "edu", "gov", "mil", "int",
    "io", "dev", "app", "co", "info", "biz", "xyz",
    "vn", "us", "uk", "jp", "cn", "kr", "sg", "th",
}

LANG_EXT = {
    "python": "py", "py": "py",
    "javascript": "js", "js": "js", "jsx": "jsx", "node": "js",
    "typescript": "ts", "ts": "ts", "tsx": "tsx",
    "html": "html", "htm": "html", "xml": "xml", "svg": "svg",
    "css": "css", "scss": "scss", "sass": "scss", "less": "less",
    "json": "json", "yaml": "yml", "yml": "yml", "toml": "toml",
    "java": "java", "kotlin": "kt", "kt": "kt",
    "c": "c", "h": "h", "cpp": "cpp", "c++": "cpp", "hpp": "hpp",
    "csharp": "cs", "cs": "cs", "dotnet": "cs",
    "php": "php", "ruby": "rb", "rb": "rb", "go": "go", "golang": "go",
    "rust": "rs", "rs": "rs", "swift": "swift", "dart": "dart",
    "sh": "sh", "bash": "sh", "shell": "sh", "zsh": "sh",
    "sql": "sql", "md": "md", "markdown": "md",
    "vue": "vue", "svelte": "svelte",
}


class Module(ModuleBase):
    def on_load(self):
        print(f"[{self.name}] ACDV-Teams Module loaded. 📂")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_valid_filename(name: str) -> bool:
        if not name or "://" in name:
            return False

        basename = name.replace("\\", "/").rsplit("/", 1)[-1]

        # ✅ Dotfile: .env, .gitignore, .dockerignore, .env.local, ...
        if DOTFILE_PATTERN.match(basename):
            return True

        if not re.search(r"\.[A-Za-z0-9]{1,10}$", basename):
            return False
        ext = basename.rsplit(".", 1)[-1]
        if ext.isdigit():
            return False
        if ext.lower() in _TLD_BLACKLIST:
            return False
        return True

    def _sanitize_path(self, raw_path: str):
        if not raw_path:
            return None
        path = raw_path.replace("\\", "/").strip()
        path = re.sub(r"^[A-Za-z]:/", "", path)          # bỏ ổ đĩa Windows
        path = re.sub(r"^(\.{1,2}/)+", "", path).lstrip("/")  # bỏ ./ ../ /

        segments = []
        for seg in path.split("/"):
            seg = seg.strip()
            if not seg or seg in (".", ".."):
                continue
            # ❌ BỎ lstrip(".") — giữ nguyên dotfile: .github, .env, .vscode
            seg = re.sub(r'[<>:"|?*\x00-\x1f]', "_", seg)
            seg = seg.rstrip(" .")   # chỉ strip đuôi
            if not seg:
                continue
            segments.append(seg[:80])

        if not segments:
            return None

        # ✅ Cap an toàn theo tổng độ dài, KHÔNG cắt mất segment gốc
        result, total = [], 0
        for seg in reversed(segments):
            need = len(seg) + (1 if result else 0)
            if total + need > 200:
                break
            result.insert(0, seg)
            total += need
        if not result:
            result = [segments[-1][:200]]
        return "/".join(result)

    def _extract_filename(self, header_part: str, lang: str, index: int) -> str:
        lines = header_part.strip().split("\n")

        for line in reversed(lines):
            raw = line.strip()
            if not raw or len(raw) > 200:
                continue

            # ---- Bóc các trang trí markdown ----
            clean = raw.replace("`", "").replace("📁", "").replace("📄", "").strip()
            # Bullet / heading ở đầu dòng
            clean = re.sub(r"^(?:[-*+•>]+[ \t]+|#{1,6}[ \t]+)", "", clean).strip()
            # Bold **...**
            clean = re.sub(r"^\*\*|\*\*$", "", clean).strip()

            # Bóc prefix "File:", "Path:", "tên file:", ...
            stripped = PREFIX_PATTERN.sub("", clean).strip()

            # ✅ Chiến lược 1: cả dòng (sau khi bóc prefix) là 1 filename duy nhất
            if re.fullmatch(r"[^\s]+", stripped) and self._is_valid_filename(stripped):
                safe = self._sanitize_path(stripped)
                if safe and self._is_valid_filename(safe):
                    return safe

            # ✅ Chiến lược 2: chỉ chấp nhận token khi nó chiếm TRỌN dòng
            # (tránh câu văn xuôi chứa "config/x.json" bị bắt nhầm)
            for cand in reversed(FILE_PATTERN.findall(stripped)):
                if not self._is_valid_filename(cand):
                    continue
                if cand.strip() != stripped.strip():
                    continue
                safe = self._sanitize_path(cand)
                if safe and self._is_valid_filename(safe):
                    return safe

        # ---- Fallback ----
        ext = LANG_EXT.get((lang or "").lower())
        if ext:
            return f"snippets/snippet_{index}.{ext}"
        return f"snippets/file_snippet_{index}.txt"

    # ------------------------------------------------------------------
    # Request parsing (giữ nguyên — đã ổn định)
    # ------------------------------------------------------------------
    def _read_body_dict(self, req) -> dict:
        if not isinstance(req, dict):
            return {}

        body = req.get("body")
        if isinstance(body, dict):
            if body or not ("files" in req or "content" in req):
                return body

        if isinstance(body, (str, bytes)):
            if isinstance(body, bytes):
                try:
                    body = body.decode("utf-8")
                except Exception:
                    body = body.decode("utf-8", errors="replace")
            if body.strip():
                try:
                    parsed = json.loads(body)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception as e:
                    print(f"[md_parser] body JSON parse failed: {e}; preview={body[:200]!r}")

        for key in ("raw_body", "raw", "_body", "_raw_body"):
            if key in req and req[key]:
                raw = req[key]
                if isinstance(raw, bytes):
                    try:
                        raw = raw.decode("utf-8")
                    except Exception:
                        raw = raw.decode("utf-8", errors="replace")
                if isinstance(raw, str) and raw.strip():
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception as e:
                        print(f"[md_parser] {key} JSON parse failed: {e}")

        if "files" in req or "content" in req:
            return req

        return {}

    def _read_content(self, req) -> str:
        if not isinstance(req, dict):
            return ""

        body = req.get("body")

        if isinstance(body, dict):
            content = body.get("content", "")
            if content:
                return content

        if isinstance(body, (str, bytes)):
            if isinstance(body, bytes):
                try:
                    body = body.decode("utf-8")
                except Exception:
                    body = body.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    content = parsed.get("content", "")
                    if content:
                        return content
            except Exception:
                if body:
                    return body

        for key in ("raw_body", "raw", "_body"):
            if key in req and req[key]:
                raw = req[key]
                if isinstance(raw, bytes):
                    try:
                        raw = raw.decode("utf-8")
                    except Exception:
                        raw = raw.decode("utf-8", errors="replace")
                if isinstance(raw, str):
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            content = parsed.get("content", "")
                            if content:
                                return content
                    except Exception:
                        if raw:
                            return raw

        if "content" in req and isinstance(req["content"], str):
            return req["content"]

        return ""

    def _debug_info(self, req) -> dict:
        info = {"req_type": type(req).__name__}
        if isinstance(req, dict):
            info["req_keys"] = list(req.keys())
            info["body_type"] = type(req.get("body")).__name__
            raw = req.get("body")
            if isinstance(raw, str):
                info["body_preview"] = raw[:200]
            elif isinstance(raw, dict):
                info["body_keys"] = list(raw.keys())
        return info

    # ------------------------------------------------------------------
    # Handler: parse_markdown
    # ------------------------------------------------------------------
    def parse_markdown(self, req):
        content = self._read_content(req)

        if not content:
            return {
                "ok": False,
                "error": "Server không đọc được nội dung gửi lên từ client!",
                "debug": self._debug_info(req),
            }

        parsed_files = []
        last_end = 0
        for index, match in enumerate(FENCE_PATTERN.finditer(content), start=1):
            header_part = content[last_end:match.start()]
            lang = match.group(1) or ""
            code_content = match.group(2)
            last_end = match.end()
            filename = self._extract_filename(header_part, lang, index)
            parsed_files.append({"filename": filename, "code": code_content.strip()})

        return {"ok": True, "files": parsed_files, "total": len(parsed_files)}

    # ------------------------------------------------------------------
    # Handler: download_zip
    # ------------------------------------------------------------------
    def download_zip(self, req):
        body = self._read_body_dict(req)

        if not body:
            return {
                "ok": False,
                "error": "Server không đọc được JSON body từ client!",
                "debug": self._debug_info(req),
            }

        raw_files = body.get("files")
        files = []

        if isinstance(raw_files, list) and raw_files:
            for i, f in enumerate(raw_files):
                if not isinstance(f, dict):
                    continue
                name = self._sanitize_path(f.get("filename") or "")
                if not name or not self._is_valid_filename(name):
                    name = f"snippets/file_{i + 1}.txt"
                files.append({"filename": name, "code": f.get("code") or ""})
        else:
            parsed = self.parse_markdown(req)
            if not parsed.get("ok"):
                return {
                    "ok": False,
                    "error": "Body không có 'files' và cũng không có 'content' để parse!",
                    "debug": {
                        **self._debug_info(req),
                        "body_keys": list(body.keys()),
                    },
                }
            files = parsed["files"]

        if not files:
            return {"ok": False, "error": "Không có file nào để nén!"}

        # ✅ Tránh trùng README.md với file user
        existing = {(f["filename"] or "").strip().lower() for f in files}
        readme_name = "README.md"
        if readme_name.lower() in existing:
            readme_name = "_ACDV_README.md"

        buf = io.BytesIO()
        used = {readme_name}
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            readme = (
                "# ACDV-Teams Module — MD Code Extractor\n\n"
                f"- Thời gian tạo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"- Tổng số file: {len(files)}\n"
                "- Bản quyền: **ACDV-Teams Module**\n\n"
                "> Toàn bộ cấu trúc thư mục cha → con đã được tái tạo tự động.\n"
            )
            zf.writestr(readme_name, readme)

            for f in files:
                name = f["filename"]
                if name in used:
                    base = name
                    counter = 1
                    if "/" in base:
                        d, fn = base.rsplit("/", 1)
                        while name in used:
                            name = f"{d}/dup{counter}_{fn}"
                            counter += 1
                    else:
                        while name in used:
                            name = f"dup{counter}_{base}"
                            counter += 1
                used.add(name)
                zf.writestr(name, f["code"])

        zip_bytes = buf.getvalue()

        return {
            "ok": True,
            "zip_base64": base64.b64encode(zip_bytes).decode("ascii"),
            "filename": f"acdv-teams-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip",
            "total": len(files),
            "size": len(zip_bytes),
            "branding": "ACDV-Teams Module",
        }