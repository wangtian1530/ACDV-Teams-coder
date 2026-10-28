"""Diagnostics manager — collect problems from modules (VS Code style).

v2.0.1 (hotfix):
  - L15: timeout 5s cho provider.diagnose() — tránh module treo thread diagnostics.
"""
import threading


SEVERITY = ("error", "warning", "info", "hint")
DIAGNOSE_TIMEOUT = 5.0  # giây


class DiagnosticsManager:
    def __init__(self, engine):
        self.engine = engine
        self.providers = {}
        self.lock = threading.Lock()

    def register_provider(self, module_name, files=None):
        with self.lock:
            self.providers[module_name] = {
                "files": files or ["*"],
                "enabled": True,
            }

    def unregister_provider(self, module_name):
        with self.lock:
            self.providers.pop(module_name, None)

    def _matches(self, provider, path):
        patterns = provider.get("files") or ["*"]
        if not patterns:
            return True
        path_norm = (path or "").replace("\\", "/")
        for pat in patterns:
            if pat == "*":
                return True
            p = pat.lstrip("*").replace("\\", "/")
            if p and path_norm.endswith(p):
                return True
        return False

    def _call_diagnose_with_timeout(self, fn, *args, timeout=DIAGNOSE_TIMEOUT):
        """⭐ L15: chạy fn trong thread riêng, timeout nếu quá lâu."""
        result = {"done": False, "value": None, "error": None}

        def _runner():
            try:
                result["value"] = fn(*args)
            except Exception as e:
                result["error"] = e
            finally:
                result["done"] = True

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join(timeout)

        if not result["done"]:
            raise TimeoutError(f"diagnose() vượt quá {timeout}s")
        if result["error"]:
            raise result["error"]
        return result["value"]

    def run_for_file(self, project, path, content):
        with self.lock:
            providers = dict(self.providers)
        out = []
        for mod_name, provider in providers.items():
            if not provider.get("enabled"):
                continue
            if not self._matches(provider, path):
                continue
            module = self.engine.modules.get(mod_name)
            if not module:
                continue
            fn = getattr(module, "diagnose", None)
            if not callable(fn):
                continue
            try:
                diags = self._call_diagnose_with_timeout(
                    fn, project, path, content
                ) or []
            except TimeoutError:
                print(f"[Diagnostics] {mod_name} timeout ({DIAGNOSE_TIMEOUT}s) — skip")
                continue
            except Exception as e:
                print(f"[Diagnostics] {mod_name} error: {e}")
                continue
            if not isinstance(diags, list):
                continue
            for d in diags:
                if not isinstance(d, dict):
                    continue
                sev = d.get("severity", "info")
                if sev not in SEVERITY:
                    sev = "info"
                try:
                    line = max(1, int(d.get("line", 1) or 1))
                except Exception:
                    line = 1
                try:
                    column = max(1, int(d.get("column", 1) or 1))
                except Exception:
                    column = 1
                try:
                    end_line = max(line, int(d.get("end_line", line) or line))
                except Exception:
                    end_line = line
                try:
                    end_column = max(1, int(d.get("end_column", column) or column))
                except Exception:
                    end_column = column
                out.append({
                    "project": project,
                    "path": path,
                    "source": mod_name,
                    "severity": sev,
                    "line": line,
                    "column": column,
                    "end_line": end_line,
                    "end_column": end_column,
                    "message": str(d.get("message", "")),
                    "code": d.get("code"),
                })
        return out