"""Core Engine — boot sequence, module registry, critical-fail policy, error dispatch."""
import os
import time
import json
import signal
import threading
import traceback

from .loader import ModuleLoader
from .sandbox import Sandbox
from .router import Router
from .server import HttpWsServer
from .project_manager import ProjectManager
from .runner import ProcessRunner
from .settings import SettingsManager
from .diagnostics import DiagnosticsManager


class CoreEngine:
    def __init__(self, base_dir, config):
        self.base_dir = base_dir
        self.config = config
        self.modules = {}
        self.router = Router()
        self.sandbox = Sandbox(base_dir)
        self.projects = ProjectManager(base_dir)
        self.logs_dir = os.path.join(base_dir, "core", "data", "logs")
        self.runner = ProcessRunner(self, self.logs_dir)
        self.loader = ModuleLoader(self)
        self.settings = SettingsManager(base_dir, self)
        self.diagnostics = DiagnosticsManager(self)
        self.server = None
        self.running = False
        self.critical_fail = False
        self._diag_cache = {}

    def boot(self):
        print("=" * 60)
        print(f"  ACDV-Teams Coder · v{self.config.get('version')}")
        print("=" * 60)
        print("[1/5] main.py anchor — OK")
        print("[2/5] starting network layer …")
        self._start_network()
        print("[3/5] initialising core, sandbox, router …")
        self._init_core()
        self._apply_overrides()
        print("[4/5] scanning & loading modules …")
        self._load_modules()
        print("[5/5] session recovery …")
        self._recover_sessions()
        try:
            self.runner.reap_orphans()
        except Exception as e:
            print(f"[Runner] reap error: {e}")
        print("=" * 60)
        print("  ✓ SYSTEM READY")
        print("=" * 60)

    def _start_network(self):
        host = self.config.get("host", "0.0.0.0")
        port = int(self.config.get("port", 8765))
        self.server = HttpWsServer(host, port, self)
        self.server.start()

    def _init_core(self):
        self.sandbox.initialize()
        os.makedirs(os.path.join(self.base_dir, "core", "data"), exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "projects"), exist_ok=True)
        self.settings.initialize()

        # ⭐ v1.3.0: ALL core routes registered with `add_core` — protected
        # from module override. Modules attempting to override get rejected.
        A = self.router.add_core

        A("GET",  "/api/status",                self._api_status)
        A("GET",  "/api/modules",               self._api_modules)
        A("POST", "/api/modules/install",       self._api_install)
        A("POST", "/api/modules/uninstall",     self._api_uninstall)
        A("POST", "/api/modules/reload",        self._api_reload)

        A("GET",  "/api/projects",              self._api_projects_list)
        A("POST", "/api/projects/create",       self._api_projects_create)
        A("POST", "/api/projects/upload",       self._api_projects_upload)
        A("POST", "/api/projects/delete",       self._api_projects_delete)
        A("POST", "/api/projects/tree",         self._api_projects_tree)
        A("POST", "/api/projects/file/read",    self._api_projects_file_read)
        A("POST", "/api/projects/file/write",   self._api_projects_file_write)
        A("POST", "/api/projects/file/create",  self._api_projects_file_create)
        A("POST", "/api/projects/file/delete",  self._api_projects_file_delete)
        A("POST", "/api/projects/file/rename",  self._api_projects_file_rename)
        A("POST", "/api/projects/folder/create", self._api_projects_folder_create)

        A("POST", "/api/projects/run",          self._api_projects_run)
        A("POST", "/api/projects/run/stop",     self._api_projects_run_stop)
        A("GET",  "/api/projects/run/status",   self._api_projects_run_status)

        A("POST", "/api/projects/logs/list",    self._api_logs_list)
        A("POST", "/api/projects/logs/read",    self._api_logs_read)
        A("POST", "/api/projects/logs/delete",  self._api_logs_delete)

        # ⭐ v1.2.2: Settings
        A("GET",  "/api/settings",              self._api_settings_get)
        A("POST", "/api/settings",              self._api_settings_update)
        A("POST", "/api/settings/modules",      self._api_settings_modules)
        A("POST", "/api/settings/module/get",   self._api_settings_module_get)
        A("POST", "/api/settings/module/set",   self._api_settings_module_set)
        A("GET",  "/api/overlay",               self._api_overlay_get)

        # ⭐ v1.2.2: Diagnostics
        A("POST", "/api/diagnostics/check",     self._api_diagnostics_check)
        A("POST", "/api/diagnostics/file",      self._api_diagnostics_file)
        A("GET",  "/api/diagnostics/all",       self._api_diagnostics_all)
        A("POST", "/api/diagnostics/clear",     self._api_diagnostics_clear)

    def _apply_overrides(self):
        od = os.path.join(self.base_dir, "overrides")
        if not os.path.isdir(od):
            return
        for fname in sorted(os.listdir(od)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            path = os.path.join(od, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    code = f.read()
                ns = {"engine": self, "sandbox": self.sandbox,
                      "config": self.config, "router": self.router}
                exec(compile(code, path, "exec"), ns)
                print(f"[Overrides] ✓ {fname}")
            except Exception as e:
                print(f"[Overrides] ✗ {fname}: {e}")

    def _load_modules(self):
        self.loader.scan_and_load_all()

    def _recover_sessions(self):
        for name, mod in list(self.modules.items()):
            try:
                mod.on_recovery()
            except Exception as e:
                print(f"[Recovery] ✗ {name}: {e}")
                traceback.print_exc()
                if mod.metadata.get("critical"):
                    self.fail_critical(f"recovery failed for critical module '{name}'")

    def register_module(self, module):
        name = module.metadata["name"]
        self.modules[name] = module
        for route in module.metadata.get("routes", []):
            method = route.get("method", "GET")
            path = route.get("path")
            handler = route.get("handler")
            if not path or not handler:
                print(f"[Loader] ⚠ '{name}': invalid route {route}")
                continue
            # ⭐ v1.3.0: reject module routes that collide with protected core routes
            if self.router.is_protected(method, path):
                print(f"[Loader] ⚠ '{name}': route {method} {path} rejected "
                      f"(core-protected)")
                continue
            try:
                self.router.add(
                    method, path,
                    lambda req, m=module, r=route: m.handle_route(r["handler"], req),
                )
            except Exception as e:
                print(f"[Loader] ⚠ '{name}': route {method} {path} rejected: {e}")

    def fail_critical(self, reason):
        print(f"\n[FATAL] {reason}")
        self.critical_fail = True
        self.shutdown()
        os._exit(1)

    def _broadcast(self, msg):
        try:
            if self.server:
                self.server.broadcast(msg)
        except Exception:
            pass

    # ================================================================ #
    #  ⭐ v1.3.0: ERROR DISPATCH CHAIN (VS Code-like)
    # ================================================================ #
    def dispatch_error(self, ctx):
        """Dispatch an error through module interceptors.

        ctx = {
            "source": "http" | "ws_route" | "ws_action",
            "method", "path", "request",       # http / ws_route
            "module", "button_id", "params",   # ws_action
            "error", "traceback"
        }

        Returns:
            None  -> not handled, caller should return 500/error
            dict  -> handled, use as response body
        """
        # --- Pass 1: on_any_error (global log) ---
        for name, mod in list(self.modules.items()):
            fn = getattr(mod, "on_any_error", None)
            if not callable(fn):
                continue
            try:
                result = fn(ctx)
                normalized = self._normalize_error_result(result)
                if normalized is not None:
                    print(f"[ErrorDispatch] {name}.on_any_error handled")
                    return normalized
            except Exception as e:
                print(f"[ErrorDispatch] {name}.on_any_error failed: {e}")

        # --- Pass 2: source-specific ---
        source = ctx.get("source", "")
        handler_name = {
            "http":       "on_http_error",
            "ws_route":   "on_ws_route_error",
            "ws_action":  "on_ws_action_error",
        }.get(source)

        if handler_name:
            for name, mod in list(self.modules.items()):
                fn = getattr(mod, handler_name, None)
                if not callable(fn):
                    continue
                try:
                    result = fn(ctx)
                    normalized = self._normalize_error_result(result)
                    if normalized is not None:
                        print(f"[ErrorDispatch] {name}.{handler_name} handled")
                        return normalized
                except Exception as e:
                    print(f"[ErrorDispatch] {name}.{handler_name} failed: {e}")

        return None

    def _normalize_error_result(self, result):
        """Module returns can be:
        - None                    -> not handled
        - {"handled": False, ...} -> not handled
        - {"handled": True, "response": {...}} -> handled, use response
        - {...}                   -> handled, use as-is
        """
        if not isinstance(result, dict):
            return result
        if "handled" in result:
            if not result["handled"]:
                return None
            return result.get("response") or result
        return result

    # ================================================================ #
    #  ⭐ v1.3.0: get module settings (used by server.py WS handlers)
    # ================================================================ #
    def get_module_settings(self, name):
        if name not in self.modules:
            return {}
        try:
            return self.settings.get_module(name)
        except Exception:
            return {}

    # ============================ Status ============================
    def _api_status(self, req):
        return {
            "status": "critical" if self.critical_fail else "ok",
            "version": self.config.get("version"),
            "uptime_modules": list(self.modules.keys()),
        }

    def _api_modules(self, req):
        return {n: m.metadata for n, m in self.modules.items()}

    def _api_install(self, req):
        try:
            if "zip_base64" in req:
                import base64, tempfile
                data = base64.b64decode(req["zip_base64"])
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
                    f.write(data)
                    tmp = f.name
                try:
                    meta = self.loader.install_from_zip(tmp)
                finally:
                    os.unlink(tmp)
            else:
                meta = self.loader.install_from_zip(req.get("file_path"))
            return {"ok": True, "module": meta}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_uninstall(self, req):
        name = req.get("name")
        if not name:
            return {"ok": False, "error": "missing name"}
        try:
            self.loader.uninstall(name)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_reload(self, req):
        name = req.get("name")
        if not name:
            return {"ok": False, "error": "missing name"}
        try:
            if name in self.modules:
                self.modules[name].on_shutdown()
                del self.modules[name]
            self.diagnostics.unregister_provider(name)
            self.settings.unregister_module(name)
            self.loader.load_module(name)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ============================ Projects ============================
    def _api_projects_list(self, req):
        return self.projects.list_projects()

    def _api_projects_create(self, req):
        try:
            meta = self.projects.create(req.get("name"), req.get("language", "plaintext"))
            return {"ok": True, "project": meta}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_projects_upload(self, req):
        try:
            meta = self.projects.create_from_zip(req.get("name"), req.get("zip_base64"))
            return {"ok": True, "project": meta}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_projects_delete(self, req):
        try:
            name = req.get("name")
            self.projects.delete(name)
            for k in list(self._diag_cache.keys()):
                if k[0] == name:
                    del self._diag_cache[k]
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_projects_tree(self, req):
        try:
            return {"ok": True, "tree": self.projects.tree(req.get("project"))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_projects_file_read(self, req):
        project = req.get("project")
        path = req.get("path")
        try:
            content = self.projects.read_file(project, path)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        try:
            gs = self.settings.get_global()
            if (gs.get("diagnostics") or {}).get("auto_run_on_open"):
                self._schedule_diagnostics(project, path, content)
        except Exception:
            pass
        return {"ok": True, "content": content}

    def _api_projects_file_write(self, req):
        project = req.get("project")
        path = req.get("path")
        content = req.get("content", "")
        try:
            self.projects.write_file(project, path, content)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        try:
            gs = self.settings.get_global()
            if (gs.get("diagnostics") or {}).get("auto_run_on_save"):
                self._schedule_diagnostics(project, path, content)
        except Exception:
            pass
        return {"ok": True}

    def _api_projects_file_create(self, req):
        try:
            self.projects.create_file(req.get("project"), req.get("path"))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_projects_file_delete(self, req):
        try:
            project = req.get("project")
            path = req.get("path")
            self.projects.delete_file(project, path)
            self._diag_cache.pop((project, path), None)
            self._broadcast({
                "type": "diagnostics_update",
                "project": project, "path": path, "diagnostics": [],
            })
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_projects_file_rename(self, req):
        try:
            self.projects.rename(req.get("project"), req.get("old_path"),
                                 req.get("new_path"))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_projects_folder_create(self, req):
        try:
            self.projects.create_folder(req.get("project"), req.get("path"))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ============== Run ==============
    def _api_projects_run(self, req):
        try:
            project = req.get("project")
            path = req.get("path")
            if not project or not path:
                return {"ok": False, "error": "missing project or path"}
            proj_dir = self.projects._safe_path(project)
            if not os.path.isdir(proj_dir):
                return {"ok": False, "error": "project not found"}
            info = self.runner.run(proj_dir, project, path)
            return {"ok": True, "run": info}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_projects_run_stop(self, req):
        try:
            force = bool(req.get("force"))
            stopped = self.runner.stop(force=force)
            return {"ok": True, "stopped": stopped, "status": self.runner.status()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_projects_run_status(self, req):
        try:
            return {"ok": True, "status": self.runner.status()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ============== Logs ==============
    def _api_logs_list(self, req):
        try:
            project = req.get("project") or ""
            entries = []
            if os.path.isdir(self.logs_dir):
                for fn in sorted(os.listdir(self.logs_dir)):
                    if fn.startswith("."):
                        continue
                    if project and not fn.startswith(project + "__"):
                        continue
                    full = os.path.join(self.logs_dir, fn)
                    if not os.path.isfile(full):
                        continue
                    try:
                        st = os.stat(full)
                        entries.append({"name": fn, "size": st.st_size, "mtime": st.st_mtime})
                    except Exception:
                        pass
            return {"ok": True, "logs": entries}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_logs_read(self, req):
        try:
            name = req.get("name")
            if not name or "/" in name or "\\" in name or ".." in name:
                return {"ok": False, "error": "invalid log name"}
            path = os.path.join(self.logs_dir, name)
            if not os.path.isfile(path):
                return {"ok": False, "error": "log not found"}
            if os.path.getsize(path) > 5 * 1024 * 1024:
                return {"ok": False, "error": "log too large (> 5MB)"}
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return {"ok": True, "content": f.read()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_logs_delete(self, req):
        try:
            name = req.get("name")
            if not name or "/" in name or "\\" in name or ".." in name:
                return {"ok": False, "error": "invalid log name"}
            path = os.path.join(self.logs_dir, name)
            if os.path.isfile(path):
                os.remove(path)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ============== ⭐ Settings ==============
    def _api_settings_get(self, req):
        return {"ok": True, "settings": self.settings.get_global()}

    def _api_settings_update(self, req):
        patch = req.get("patch") or {k: v for k, v in req.items() if not k.startswith("_")}
        try:
            result = self.settings.update_global(patch)
            self._broadcast({"type": "settings_changed", "settings": result})
            return {"ok": True, "settings": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_settings_modules(self, req):
        out = []
        for name, mod in self.modules.items():
            schema = self.settings.get_module_schema(name)
            if not schema:
                continue
            values = self.settings.get_module(name)
            out.append({
                "name": name,
                "display_name": mod.metadata.get("display_name") or name,
                "description": mod.metadata.get("description", ""),
                "version": mod.metadata.get("version"),
                "schema": schema,
                "values": values,
                "overlay": mod.metadata.get("overlay") or {},
            })
        return {"ok": True, "modules": out}

    def _api_settings_module_get(self, req):
        name = req.get("name")
        if not name:
            return {"ok": False, "error": "missing name"}
        if name not in self.modules:
            return {"ok": False, "error": "module not found"}
        return {
            "ok": True,
            "schema": self.settings.get_module_schema(name),
            "values": self.settings.get_module(name),
        }

    def _api_settings_module_set(self, req):
        name = req.get("name")
        if not name:
            return {"ok": False, "error": "missing name"}
        if name not in self.modules:
            return {"ok": False, "error": "module not found"}
        values = req.get("values") or {}
        if not isinstance(values, dict):
            return {"ok": False, "error": "values must be object"}
        result = self.settings.update_module(name, values)
        if result.get("ok"):
            self._broadcast({"type": "module_settings_changed",
                             "module": name, "values": result["values"]})
        return result

    def _api_overlay_get(self, req):
        overlays = []
        gs = self.settings.get_global()
        safe_mode = bool((gs.get("overlays") or {}).get("safe_mode", False))
        per = (gs.get("overlays") or {}).get("per_module") or {}
        for name, mod in self.modules.items():
            ov = mod.metadata.get("overlay") or {}
            css = ov.get("css")
            js = ov.get("js")
            if not css and not js:
                continue
            m_conf = per.get(name) or {}
            css_enabled = bool(m_conf.get("css", True)) and not safe_mode
            js_enabled = bool(m_conf.get("js", True)) and not safe_mode
            overlays.append({
                "name": name,
                "css": f"/module/{name}/{css}" if css else None,
                "js": f"/module/{name}/{js}" if js else None,
                "css_enabled": css_enabled,
                "js_enabled": js_enabled,
            })
        return {"ok": True, "safe_mode": safe_mode, "overlays": overlays}

    # ============== ⭐ Diagnostics ==============
    def _schedule_diagnostics(self, project, path, content):
        def _run():
            try:
                diags = self.diagnostics.run_for_file(project, path, content)
                self._diag_cache[(project, path)] = diags
                self._broadcast({
                    "type": "diagnostics_update",
                    "project": project,
                    "path": path,
                    "diagnostics": diags,
                })
            except Exception as e:
                print(f"[Diagnostics] run error: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def _api_diagnostics_check(self, req):
        project = req.get("project")
        path = req.get("path")
        if not project or not path:
            return {"ok": False, "error": "missing project or path"}
        try:
            content = self.projects.read_file(project, path)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        diags = self.diagnostics.run_for_file(project, path, content)
        self._diag_cache[(project, path)] = diags
        self._broadcast({
            "type": "diagnostics_update",
            "project": project,
            "path": path,
            "diagnostics": diags,
        })
        return {"ok": True, "diagnostics": diags}

    def _api_diagnostics_file(self, req):
        project = req.get("project")
        path = req.get("path")
        if not project or not path:
            return {"ok": False, "error": "missing project or path"}
        return {"ok": True, "diagnostics": self._diag_cache.get((project, path), [])}

    def _api_diagnostics_all(self, req):
        out = []
        for diags in self._diag_cache.values():
            out.extend(diags)
        return {"ok": True, "diagnostics": out}

    def _api_diagnostics_clear(self, req):
        project = req.get("project")
        path = req.get("path")
        if project and path:
            self._diag_cache.pop((project, path), None)
            self._broadcast({
                "type": "diagnostics_update",
                "project": project, "path": path, "diagnostics": [],
            })
        else:
            self._diag_cache.clear()
            self._broadcast({"type": "diagnostics_cleared"})
        return {"ok": True}

    # ============== Lifecycle ==============
    def shutdown(self):
        print("[Core] shutting down …")
        self.running = False
        try:
            self.runner.stop(force=True)
        except Exception:
            pass
        for mod in list(self.modules.values()):
            try:
                mod.on_shutdown()
            except Exception:
                pass
        if self.server:
            self.server.stop()

    def run_forever(self):
        self.running = True
        try:
            while self.running and not self.critical_fail:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.shutdown()