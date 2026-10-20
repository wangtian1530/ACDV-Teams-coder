"""Filesystem sandbox: every module is confined to modules/<name>/data/."""
import os
import shutil


class SandboxViolation(Exception):
    pass


class Sandbox:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.modules_dir = os.path.join(base_dir, "modules")

    def initialize(self):
        os.makedirs(self.modules_dir, exist_ok=True)

    def get_module_data_dir(self, module_name):
        return os.path.join(self.modules_dir, module_name, "data")

    def resolve(self, module_name, path):
        """Resolve a path inside the module's sandbox, reject escapes."""
        data_dir = os.path.abspath(self.get_module_data_dir(module_name))
        os.makedirs(data_dir, exist_ok=True)

        rel = (path or "").lstrip("/")
        target = os.path.abspath(os.path.join(data_dir, rel))

        # Anti-escape: must be strictly inside data_dir
        if target != data_dir and not target.startswith(data_dir + os.sep):
            raise SandboxViolation(f"Path escape attempt: {path!r}")
        return target

    def open(self, module_name, path, mode="r", **kwargs):
        target = self.resolve(module_name, path)
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        return open(target, mode, **kwargs)

    def read(self, module_name, path):
        with self.open(module_name, path, "r", encoding="utf-8") as f:
            return f.read()

    def write(self, module_name, path, content):
        with self.open(module_name, path, "w", encoding="utf-8") as f:
            f.write(content)

    def delete(self, module_name, path):
        target = self.resolve(module_name, path)
        if os.path.isfile(target):
            os.remove(target)
        elif os.path.isdir(target):
            shutil.rmtree(target)

    def list_dir(self, module_name, path=""):
        target = self.resolve(module_name, path)
        if not os.path.exists(target):
            return []
        return sorted(os.listdir(target))