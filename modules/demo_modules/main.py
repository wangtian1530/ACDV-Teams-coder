"""Demo module — full ModuleBase contract example.

Shows:
  - Lifecycle hooks (on_load / on_recovery / on_shutdown / on_settings_changed)
  - Custom routes (ping / sys_info / echo)
  - UI button handlers (on_button_show_info / on_button_check_health)
  - Diagnostics provider (warns on TODO comments & breakpoint())
  - Error interceptor (on_http_error)
"""
import os
import time
import platform

from core.loader import ModuleBase


class Module(ModuleBase):

    # ============== lifecycle ==============
    def on_load(self):
        self.start_time = time.time()
        self._log(f"loaded v{self.metadata.get('version', '?')}")
        self._log(f"settings = {self.get_settings()}")

    def on_recovery(self):
        self._log("recovery hook called")

    def on_shutdown(self):
        self._log("shutdown hook called")

    def on_settings_changed(self, new_settings):
        self._log(f"settings changed: {new_settings}")

    # ============== routes ==============
    def ping(self, req):
        return {
            "ok": True,
            "pong": True,
            "module": self.name,
            "timestamp": time.time(),
        }

    def sys_info(self, req):
        gs = self.get_settings()
        return {
            "ok": True,
            "module": self.name,
            "version": self.metadata.get("version"),
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cwd": os.getcwd(),
            "settings": gs,
        }

    def echo(self, req):
        return {
            "ok": True,
            "echo": req.get("message", ""),
            "received_keys": sorted(k for k in req.keys() if not k.startswith("_")),
        }

    # ============== UI button handlers ==============
    def on_button_show_info(self, params):
        """Called from web UI via WS: {type:'module_action', button_id:'show_info'}"""
        return self.sys_info({})

    def on_button_check_health(self, params):
        """This one is declared with action='route' in init.txt, but we still
        support direct WS invocation for demo purposes."""
        return self.ping({})

    # ============== diagnostics ==============
    def diagnose(self, project, path, content):
        """Return list of diagnostic dicts (VS Code style)."""
        if not path.endswith(".py"):
            return []
        out = []
        for i, line in enumerate(content.split("\n"), start=1):
            stripped = line.strip()
            if stripped.startswith("#") and "TODO" in stripped.upper():
                out.append({
                    "severity": "warning",
                    "line": i, "column": 1,
                    "end_line": i, "end_column": max(1, len(line)),
                    "message": "TODO comment found",
                    "code": "DEMO001",
                })
            if stripped == "breakpoint()":
                out.append({
                    "severity": "warning",
                    "line": i, "column": 1,
                    "end_line": i, "end_column": len(line),
                    "message": "breakpoint() left in code",
                    "code": "DEMO002",
                })
        return out

    # ============== error interceptor ==============
    def on_http_error(self, ctx):
        """Demo: intercept errors on /api/demo_module/* and return custom response."""
        path = ctx.get("path", "")
        if not path.startswith("/api/demo_module/"):
            return None
        return {
            "ok": False,
            "error": f"[demo_module intercepted] {ctx.get('error', 'unknown')}",
            "intercepted": True,
            "path": path,
        }

    # ============== helpers ==============
    def _log(self, msg):
        if not self.get_settings().get("verbose", False):
            # verbose off → always print important messages only
            pass
        print(f"[{self.name}] {msg}", flush=True)