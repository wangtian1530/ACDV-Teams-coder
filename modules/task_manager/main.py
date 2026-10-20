import json
import time
import uuid
import os
import sys

# Ensure core package is importable
_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from core.loader import ModuleBase


class Module(ModuleBase):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.tasks = []

    # --- lifecycle ---
    def on_load(self):
        print(f"[task_manager] loaded (data dir: {self.sandbox.get_module_data_dir(self.name)})")

    def on_recovery(self):
        try:
            self.tasks = json.loads(self.sandbox.read(self.name, "tasks.json"))
            print(f"[task_manager] recovered {len(self.tasks)} tasks")
        except FileNotFoundError:
            self.tasks = []
        except Exception as e:
            print(f"[task_manager] recovery failed: {e}")
            self.tasks = []

    def on_shutdown(self):
        self._save()

    # --- helpers ---
    def _save(self):
        self.sandbox.write(
            self.name, "tasks.json",
            json.dumps(self.tasks, ensure_ascii=False, indent=2)
        )

    # --- routes ---
    def handle_list(self, req):
        return {"tasks": self.tasks}

    def handle_add(self, req):
        text = (req.get("text") or "").strip()
        if not text:
            return {"ok": False, "error": "empty text"}
        task = {
            "id": uuid.uuid4().hex[:8],
            "text": text,
            "done": False,
            "created": time.time(),
        }
        self.tasks.append(task)
        self._save()
        return {"ok": True, "task": task}

    def handle_done(self, req):
        tid = req.get("id")
        for t in self.tasks:
            if t["id"] == tid:
                t["done"] = not t["done"]
                self._save()
                return {"ok": True, "task": t}
        return {"ok": False, "error": "not found"}

    def handle_delete(self, req):
        tid = req.get("id")
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["id"] != tid]
        if len(self.tasks) == before:
            return {"ok": False, "error": "not found"}
        self._save()
        return {"ok": True}