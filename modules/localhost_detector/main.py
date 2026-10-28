"""
localhost_detector
──────────────────
Phát hiện localhost server trong Python code (static scan).
Overlay JS hiển thị nút "🌐 localhost:PORT" — mở tab mới, KHÔNG đổi tab editor.
"""

import json
import os
import re
from core.loader import ModuleBase


# ─────────────────────────────────────────────────────
# Regex pattern theo framework
# ─────────────────────────────────────────────────────
_FRAMEWORK_PATTERNS = {
    "flask": [
        re.compile(r"\bport\s*=\s*(\d{2,5})\b"),
        re.compile(r"\.run\s*\(\s*(\d{2,5})\s*[,)]"),
    ],
    "uvicorn": [
        re.compile(r"\bport\s*=\s*(\d{2,5})\b"),
    ],
    "fastapi": [
        re.compile(r"\bport\s*=\s*(\d{2,5})\b"),
    ],
    "http.server": [
        re.compile(
            r"HTTPServer\s*\(\s*\(\s*['\"]?[^'\"]*?['\"]?\s*,\s*(\d{2,5})"
        ),
        re.compile(r"\.server_address\s*=\s*\([^,]*,\s*(\d{2,5})"),
    ],
    "aiohttp": [
        re.compile(r"\bport\s*=\s*(\d{2,5})\b"),
    ],
    "bottle": [
        re.compile(r"\bport\s*=\s*(\d{2,5})\b"),
    ],
    "gradio": [
        re.compile(r"server_port\s*=\s*(\d{2,5})"),
    ],
}

_DEFAULT_PORTS = {
    "flask": 5000,
    "uvicorn": 8000,
    "fastapi": 8000,
    "http.server": 8000,
    "aiohttp": 8080,
    "bottle": 8080,
    "gradio": 7860,
    "streamlit": 8501,
}


def _detect_frameworks(content):
    lc = content.lower()
    found = set()
    if "from flask" in lc or "import flask" in lc:
        found.add("flask")
    if "uvicorn" in lc:
        found.add("uvicorn")
    if "fastapi" in lc:
        found.add("fastapi")
    if "http.server" in lc or "httpserver" in lc:
        found.add("http.server")
    if "aiohttp" in lc:
        found.add("aiohttp")
    if "bottle" in lc:
        found.add("bottle")
    if "gradio" in lc:
        found.add("gradio")
    if "streamlit" in lc:
        found.add("streamlit")
    return found


def _scan_source(content):
    """Trả về list server detect được từ source."""
    if not content:
        return []
    frameworks = _detect_frameworks(content)
    if not frameworks:
        return []

    results = {}
    for fw in frameworks:
        patterns = _FRAMEWORK_PATTERNS.get(fw, [])
        found_port = None
        for pat in patterns:
            for m in pat.finditer(content):
                try:
                    p = int(m.group(1))
                except (IndexError, ValueError, TypeError):
                    continue
                if 1 <= p <= 65535:
                    found_port = p
                    break
            if found_port:
                break
        if found_port is None:
            found_port = _DEFAULT_PORTS.get(fw)
        if found_port and found_port not in results:
            results[found_port] = {
                "framework": fw,
                "port": found_port,
                "url": f"http://127.0.0.1:{found_port}",
                "confidence": "high" if found_port != _DEFAULT_PORTS.get(fw) else "medium",
            }
    return list(results.values())


def _extract_body(req):
    """Trích JSON body từ req — defensive."""
    if not isinstance(req, dict):
        return {}
    for key in ("json", "body_json", "parsed_body"):
        v = req.get(key)
        if isinstance(v, dict):
            return v
    body = req.get("body")
    if isinstance(body, dict):
        return body
    if isinstance(body, str) and body.strip():
        try:
            return json.loads(body)
        except Exception:
            return {}
    return {}


class Module(ModuleBase):
    def on_load(self):
        print(f"[{self.name}] localhost_detector loaded")

    # ─── POST /api/localhost_detector/scan ─────────────
    def scan(self, req):
        body = _extract_body(req)
        project = body.get("project")
        path = body.get("path")
        if not project or not path:
            return {"ok": False, "error": "Missing project/path"}

        if not path.endswith(".py"):
            return {"ok": True, "servers": [], "reason": "not_python"}

        try:
            content = self._read_project_file(project, path)
        except Exception as e:
            return {"ok": False, "error": f"Read failed: {e}"}

        servers = _scan_source(content)
        return {
            "ok": True,
            "servers": servers,
            "project": project,
            "path": path,
        }

    # ─── Helpers ───────────────────────────────────────
    def _read_project_file(self, project, path):
        # Basic traversal guard
        if ".." in project.split("/") or ".." in project.split("\\"):
            raise ValueError("Invalid project name")
        parts = re.split(r"[\\/]+", path)
        if any(p == ".." for p in parts):
            raise ValueError("Path traversal blocked")

        proj_dir = os.path.realpath(
            os.path.join(self.engine.base_dir, "projects", project)
        )
        full = os.path.realpath(os.path.join(proj_dir, path))
        if not (full == proj_dir or full.startswith(proj_dir + os.sep)):
            raise ValueError("Path outside project")
        if not os.path.isfile(full):
            raise FileNotFoundError(path)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return f.read()