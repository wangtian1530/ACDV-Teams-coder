"""Module loader + ZIP installer + ModuleBase interface.

v1.3.1:
  - ModuleBase gains error-interceptor hooks.
  - Overlay detection: ưu tiên data/ (cho file lớn) trước web/.
    Đường dẫn data/ dùng prefix `_data_/` để server.py phân biệt.
  - register_module rejects routes collision với core (protected).
"""
import os
import io
import json
import zipfile
import shutil
import importlib.util


class ModuleBase:
    """Contract every module must honour (Golden Rule 2)."""

    def __init__(self, name, base_dir, sandbox, engine):
        self.name = name
        self.base_dir = base_dir
        self.sandbox = sandbox
        self.engine = engine
        self.metadata = {}

    # --- lifecycle ---
    def on_load(self):
        pass

    def on_recovery(self):
        pass

    def on_shutdown(self):
        pass

    # --- settings ---
    def on_settings_changed(self, new_settings):
        pass

    def get_settings(self):
        try:
            return self.engine.settings.get_module(self.name)
        except Exception:
            return {}

    # --- diagnostics ---
    def diagnose(self, project, path, content):
        return []

    # --- error interception hooks ---
    def on_any_error(self, ctx):
        return None

    def on_http_error(self, ctx):
        return None

    def on_ws_route_error(self, ctx):
        return None

    def on_ws_action_error(self, ctx):
        return None

    def handle_route(self, handler_name, request):
        handler = getattr(self, handler_name, None)
        if not handler:
            raise Exception(f"Handler '{handler_name}' not found in module '{self.name}'")
        return handler(request)


class ModuleLoader:
    def __init__(self, engine):
        self.engine = engine
        self.base_dir = engine.base_dir
        self.modules_dir = os.path.join(self.base_dir, "modules")
        self.sandbox = engine.sandbox

    def scan_and_load_all(self):
        os.makedirs(self.modules_dir, exist_ok=True)
        for entry in sorted(os.listdir(self.modules_dir)):
            mod_path = os.path.join(self.modules_dir, entry)
            if not os.path.isdir(mod_path):
                continue
            try:
                self.load_module(entry)
            except Exception as e:
                print(f"[Loader] ✗ Failed '{entry}': {e}")
                import traceback
                traceback.print_exc()

    def load_module(self, name):
        mod_path = os.path.join(self.modules_dir, name)
        main_path = os.path.join(mod_path, "main.py")
        init_path = os.path.join(mod_path, "init.txt")

        if not os.path.isfile(main_path):
            raise Exception("missing main.py")

        metadata = {"name": name, "version": "0.0.0", "routes": []}
        if os.path.isfile(init_path):
            with open(init_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                if raw:
                    metadata = json.loads(raw)
        metadata.setdefault("name", name)
        metadata.setdefault("version", "0.0.0")
        metadata.setdefault("description", "")
        metadata.setdefault("routes", [])
        metadata.setdefault("critical", False)
        metadata.setdefault("ui_buttons", [])
        metadata.setdefault("settings_schema", {})
        metadata.setdefault("diagnostics", None)
        metadata.setdefault("overlay", {})

        # web UI detection
        web_dir = os.path.join(mod_path, "web")
        data_dir = os.path.join(mod_path, "data")
        metadata["has_web_ui"] = os.path.isfile(os.path.join(web_dir, "index.html"))
        metadata["web_ui_path"] = f"/module/{name}/" if metadata["has_web_ui"] else None

        # ⭐ v1.3.1: Overlay detection — data/ ưu tiên (file lớn), fallback web/
        # data/ dùng prefix `_data_/` để server.py route đúng thư mục.
        for css_name in ("overlay.css", "override.css"):
            if os.path.isfile(os.path.join(data_dir, css_name)):
                metadata["overlay"]["css"] = f"_data_/{css_name}"
                break
            if os.path.isfile(os.path.join(web_dir, css_name)):
                metadata["overlay"]["css"] = css_name
                break

        for js_name in ("overlay.js", "override.js"):
            if os.path.isfile(os.path.join(data_dir, js_name)):
                metadata["overlay"]["js"] = f"_data_/{js_name}"
                break
            if os.path.isfile(os.path.join(web_dir, js_name)):
                metadata["overlay"]["js"] = js_name
                break

        os.makedirs(os.path.join(mod_path, "data"), exist_ok=True)

        unique_name = f"acdv_mod_{name}"
        spec = importlib.util.spec_from_file_location(unique_name, main_path)
        py_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(py_mod)

        module_class = getattr(py_mod, "Module", None)
        if not module_class:
            for attr in dir(py_mod):
                obj = getattr(py_mod, attr)
                if isinstance(obj, type) and issubclass(obj, ModuleBase) and obj is not ModuleBase:
                    module_class = obj
                    break
        if not module_class:
            raise Exception("no Module class found")

        instance = module_class(metadata["name"], mod_path, self.sandbox, self.engine)
        instance.metadata = metadata
        instance.on_load()

        if metadata["settings_schema"]:
            self.engine.settings.register_module_schema(name, metadata["settings_schema"])

        diag_cfg = metadata.get("diagnostics")
        if diag_cfg:
            if isinstance(diag_cfg, dict):
                files = diag_cfg.get("files") or ["*"]
            else:
                files = ["*"]
            self.engine.diagnostics.register_provider(name, files)

        self.engine.register_module(instance)

        overlay_txt = ""
        if metadata["overlay"].get("css"):
            overlay_txt += ", css"
        if metadata["overlay"].get("js"):
            overlay_txt += ", js"
        err_txt = ""
        for hook in ("on_any_error", "on_http_error",
                     "on_ws_route_error", "on_ws_action_error"):
            fn = getattr(instance, hook, None)
            base = getattr(ModuleBase, hook, None)
            if callable(fn) and fn is not base and getattr(fn, "__func__", None) is not base:
                err_txt += ", err"
                break
        print(f"[Loader] ✓ '{name}' v{metadata['version']} "
              f"({len(metadata['routes'])} routes"
              f"{', ' + str(len(metadata['ui_buttons'])) + ' btns' if metadata['ui_buttons'] else ''}"
              f"{', web UI' if metadata['has_web_ui'] else ''}"
              f"{', settings' if metadata['settings_schema'] else ''}"
              f"{', diagnostics' if diag_cfg else ''}"
              f"{', overlay' + overlay_txt if overlay_txt else ''}"
              f"{err_txt})")
        return instance

    def install_from_zip(self, zip_path):
        if not zip_path or not os.path.isfile(zip_path):
            raise Exception(f"ZIP file not found: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            init_name = next((n for n in names if n.endswith("init.txt")), None)
            if not init_name:
                raise Exception("ZIP must contain init.txt")

            with zf.open(init_name) as f:
                metadata = json.loads(f.read().decode("utf-8"))

            module_name = metadata.get("name")
            if not module_name:
                raise Exception("init.txt must contain 'name'")
            if "/" in module_name or "\\" in module_name or module_name in (".", ".."):
                raise Exception(f"Invalid module name: {module_name!r}")

            target_dir = os.path.join(self.modules_dir, module_name)
            if os.path.exists(target_dir):
                raise Exception(f"Module '{module_name}' already installed")

            root = init_name.rsplit("/", 1)[0] + "/" if "/" in init_name else ""
            os.makedirs(target_dir, exist_ok=True)
            os.makedirs(os.path.join(target_dir, "data"), exist_ok=True)
            target_abs = os.path.abspath(target_dir)

            for n in names:
                if n.endswith("/"):
                    continue
                norm = n.replace("\\", "/")
                if ".." in norm.split("/"):
                    raise Exception(f"Path traversal in ZIP: {n}")
                rel = norm[len(root):] if root and norm.startswith(root) else norm
                if not rel:
                    continue
                if rel.startswith("data/") or rel.startswith("web/") or rel in ("init.txt", "main.py"):
                    dest = os.path.join(target_dir, rel)
                else:
                    dest = os.path.join(target_dir, "data", rel)
                dest_abs = os.path.abspath(dest)
                if dest_abs != target_abs and not dest_abs.startswith(target_abs + os.sep):
                    raise Exception(f"Path escape in ZIP: {rel}")
                os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
                with zf.open(n) as src, open(dest_abs, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        self.load_module(module_name)
        return metadata

    # ---------------------------------------------------------------- #
    #  ⭐ Export module as ZIP
    # ---------------------------------------------------------------- #
    def export_module_zip(self, name):
        """Export module thành ZIP bytes (base dir = <name>/).

        - Bao gồm: main.py, init.txt, web/, data/, và bất kỳ file nào khác.
        - Bỏ: __pycache__, *.pyc.
        - Round-trip: ZIP này có thể cài lại qua install_from_zip()
          (sau khi đã uninstall module hiện tại).
        """
        if not name:
            raise Exception("Missing module name")
        if "/" in name or "\\" in name or name in (".", ".."):
            raise Exception("Invalid module name")

        mod_dir = os.path.abspath(os.path.join(self.modules_dir, name))
        modules_root = os.path.abspath(self.modules_dir)
        if mod_dir != modules_root and not mod_dir.startswith(modules_root + os.sep):
            raise Exception("Path escape")
        if not os.path.isdir(mod_dir):
            raise Exception("Module not found")

        buf = io.BytesIO()
        count = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(mod_dir):
                dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", ".git", ".svn"))
                for fname in sorted(files):
                    if fname.endswith(".pyc"):
                        continue
                    full = os.path.join(root, fname)
                    try:
                        rel = os.path.relpath(full, mod_dir)
                    except Exception:
                        continue
                    arcname = (name + "/" + rel).replace("\\", "/")
                    try:
                        zf.write(full, arcname=arcname)
                        count += 1
                    except (OSError, IOError):
                        continue

        return {
            "data": buf.getvalue(),
            "files": count,
            "size": buf.tell(),
        }

    def uninstall(self, name):
        if name in self.engine.modules:
            try:
                self.engine.modules[name].on_shutdown()
            except Exception:
                pass
            del self.engine.modules[name]
        self.engine.diagnostics.unregister_provider(name)
        self.engine.settings.unregister_module(name)
        target = os.path.join(self.modules_dir, name)
        if os.path.isdir(target):
            shutil.rmtree(target)