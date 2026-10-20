"""Settings manager — global + per-module settings, schema validation."""
import os
import copy
import json
import threading


DEFAULT_GLOBAL = {
    "theme": "dracula",
    "editor": {
        "font_size": 14,
        "tab_size": 4,
        "line_wrap": False,
        "auto_save": False,
    },
    "diagnostics": {
        "auto_run_on_open": False,
        "auto_run_on_save": True,
        "show_inline": True,
    },
    "overlays": {
        "safe_mode": False,
        "per_module": {},
    },
}


class SettingsManager:
    def __init__(self, base_dir, engine):
        self.base_dir = base_dir
        self.engine = engine
        self.path = os.path.join(base_dir, "core", "data", "settings.json")
        self.lock = threading.Lock()
        self.global_settings = copy.deepcopy(DEFAULT_GLOBAL)
        self.module_schemas = {}
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def initialize(self):
        self._load_global()

    # ---------- helpers ----------
    def _deep_merge(self, base, override):
        out = copy.deepcopy(base)
        if not isinstance(override, dict):
            return out
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = self._deep_merge(out[k], v)
            else:
                out[k] = v
        return out

    # ---------- global ----------
    def _load_global(self):
        if os.path.isfile(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.global_settings = self._deep_merge(DEFAULT_GLOBAL, loaded)
                return
            except Exception as e:
                print(f"[Settings] load error: {e}")
        self.global_settings = copy.deepcopy(DEFAULT_GLOBAL)
        self._save_global()

    def _save_global(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.global_settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Settings] save error: {e}")

    def get_global(self):
        return copy.deepcopy(self.global_settings)

    def update_global(self, patch):
        with self.lock:
            self.global_settings = self._deep_merge(self.global_settings, patch or {})
            self._save_global()
            return copy.deepcopy(self.global_settings)

    # ---------- per module ----------
    def register_module_schema(self, module_name, schema):
        self.module_schemas[module_name] = schema or {}

    def get_module_schema(self, module_name):
        return copy.deepcopy(self.module_schemas.get(module_name) or {})

    def unregister_module(self, module_name):
        self.module_schemas.pop(module_name, None)

    def _module_path(self, module_name):
        return os.path.join(self.base_dir, "modules", module_name, "data", "settings.json")

    def _defaults_from_schema(self, schema):
        out = {}
        for key, spec in (schema or {}).items():
            if isinstance(spec, dict) and "default" in spec:
                out[key] = spec["default"]
        return out

    def get_module(self, module_name):
        schema = self.module_schemas.get(module_name) or {}
        defaults = self._defaults_from_schema(schema)
        path = self._module_path(module_name)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                return self._deep_merge(defaults, loaded)
            except Exception:
                return defaults
        return defaults

    def _validate(self, schema, values):
        errors = []
        if not isinstance(values, dict):
            return ["values must be an object"]
        for key, spec in (schema or {}).items():
            if key not in values:
                if isinstance(spec, dict) and spec.get("required"):
                    errors.append(f"{key}: required")
                continue
            val = values[key]
            if not isinstance(spec, dict):
                continue
            t = spec.get("type")
            if t == "string" and not isinstance(val, str):
                errors.append(f"{key}: must be string")
            elif t == "number":
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    errors.append(f"{key}: must be number")
                else:
                    if "min" in spec and val < spec["min"]:
                        errors.append(f"{key}: must be >= {spec['min']}")
                    if "max" in spec and val > spec["max"]:
                        errors.append(f"{key}: must be <= {spec['max']}")
            elif t == "boolean" and not isinstance(val, bool):
                errors.append(f"{key}: must be boolean")
            elif t == "select":
                opts = spec.get("options") or []
                if opts and val not in opts:
                    errors.append(f"{key}: must be one of {opts}")
        return errors

    def update_module(self, module_name, patch):
        schema = self.module_schemas.get(module_name) or {}
        errors = self._validate(schema, patch or {})
        if errors:
            return {"ok": False, "errors": errors}
        with self.lock:
            current = self.get_module(module_name)
            updated = self._deep_merge(current, patch or {})
            path = self._module_path(module_name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(updated, f, indent=2, ensure_ascii=False)
            except Exception as e:
                return {"ok": False, "errors": [f"save failed: {e}"]}
        mod = self.engine.modules.get(module_name)
        if mod and hasattr(mod, "on_settings_changed"):
            try:
                mod.on_settings_changed(updated)
            except Exception as e:
                print(f"[Settings] {module_name}.on_settings_changed error: {e}")
        return {"ok": True, "values": updated}