import json
import re
from core.loader import ModuleBase

# Bắt tên file có phần mở rộng (hỗ trợ cả đường dẫn kiểu Windows)
FILE_PATTERN = re.compile(r"[A-Za-z0-9_\-./\\]+\.[A-Za-z0-9]{1,10}")

# Khối code: ```lang\n ... ```
FENCE_PATTERN = re.compile(r"```([A-Za-z0-9_+\-.#]*)[ \t]*\r?\n(.*?)(?:```|\Z)", re.DOTALL)

# Tiền tố hay gặp trước tên file
PREFIX_PATTERN = re.compile(
    r"^(file|filename|file name|tên file|ten file|path|đường dẫn|duong dan)\s*[:：]\s*",
    re.IGNORECASE
)

# Fallback: đoán phần mở rộng theo ngôn ngữ của code fence
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
        print(f"[{self.name}] MD Parser module loaded.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_valid_filename(name: str) -> bool:
        if not name or "://" in name:
            return False
        if not re.search(r"\.[A-Za-z0-9]{1,10}$", name):
            return False
        ext = name.rsplit(".", 1)[-1]
        if ext.isdigit():          # loại "1.0.0", "3.14"
            return False
        return True

    def _extract_filename(self, header_part: str, lang: str, index: int) -> str:
        """Dò tên file trong phần header ngay trước khối code."""
        lines = header_part.strip().split("\n")

        for line in reversed(lines):
            clean = (
                line.replace("*", "")
                    .replace("#", "")
                    .replace("`", "")
                    .replace("📁", "")
                    .replace("📄", "")
                    .strip()
            )
            clean = PREFIX_PATTERN.sub("", clean)

            candidates = FILE_PATTERN.findall(clean)
            for cand in reversed(candidates):
                if not self._is_valid_filename(cand):
                    continue
                # chỉ giữ basename, bỏ đường dẫn
                basename = cand.replace("\\", "/").split("/")[-1].lstrip(".")
                if self._is_valid_filename(basename):
                    return basename[:120]

        # Fallback 1: theo ngôn ngữ của code fence
        ext = LANG_EXT.get((lang or "").lower())
        if ext:
            return f"snippet_{index}.{ext}"

        # Fallback 2: mặc định
        return f"file_snippet_{index}.txt"

    # ------------------------------------------------------------------
    # Handler
    # ------------------------------------------------------------------
    def parse_markdown(self, req):
        content = ""

        # Tự động dò tìm dữ liệu từ mọi dạng request mà core server truyền vào
        if isinstance(req, dict):
            body = req.get("body")

            if isinstance(body, dict):
                content = body.get("content", "")
            elif isinstance(body, str):
                try:
                    parsed = json.loads(body)
                    if isinstance(parsed, dict):
                        content = parsed.get("content", "")
                except Exception:
                    content = body  # Trường hợp body chính là chuỗi nội dung

            # Kiểm tra raw_body nếu server lưu dạng bytes
            if not content and "raw_body" in req:
                try:
                    raw = req["raw_body"]
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        content = parsed.get("content", "")
                except Exception:
                    pass

            if not content:
                content = req.get("content", "")

        if not content:
            return {"ok": False, "error": "Server không đọc được nội dung gửi lên từ client!"}

        parsed_files = []
        last_end = 0

        for index, match in enumerate(FENCE_PATTERN.finditer(content), start=1):
            header_part = content[last_end:match.start()]
            lang = match.group(1) or ""
            code_content = match.group(2)
            last_end = match.end()

            filename = self._extract_filename(header_part, lang, index)

            parsed_files.append({
                "filename": filename,
                "code": code_content.strip()
            })

        return {
            "ok": True,
            "files": parsed_files,
            "total": len(parsed_files)
        }