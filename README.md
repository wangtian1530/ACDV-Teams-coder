📘 README.md — Viết lại cho phát triển

Dưới đây là bản README gọn, tập trung vào dev workflow (không phải marketing). Copy đè lên README.md hiện tại.

---

```markdown
# ACDV-Teams Coder

Local web IDE — Python stdlib backend, CodeMirror frontend, module extension system.

**Version:** `1.3.0` · **Platform:** Python 3.8+ · **Deps:** none (stdlib only)

---

## 1. Status

| Layer | State |
|---|---|
| Core engine + router + server | ✅ Ổn định |
| Project manager + ZIP upload | ✅ Ổn định |
| Process runner (`.py`/`.js`/`.sh`) | ✅ Ổn định (process-group kill) |
| Module loader + ZIP install | ✅ Ổn định |
| Diagnostics (VS Code style) | ✅ Ổn định |
| Settings (global + per-module) | ✅ Ổn định |
| Overlay CSS/JS (safe mode) | ✅ Ổn định |
| Error dispatch chain | ⚠️ Mới — cần test thêm |
| Frontend editor + explorer | ✅ Ổn định |
| Frontend settings UI | ⚠️ Mới — cần test thêm |
| Frontend diagnostics UI | ⚠️ Mới — cần test thêm |

**Known bug đang chờ fix:** `main.py` ở root có thể bị đè bởi module `main.py`. Verify:
```bash
head -1 main.py
# Phải là: #!/usr/bin/env python3
# Nếu là:   from core.loader import ModuleBase  → bị đè, xem §3
```

---

2. Cấu trúc thư mục

```
acdv-coder/
├── main.py                    # Entry point — KHÔNG được đè
├── config.json                # host/port/version
├── README.md
│
├── core/                      # Backend (Python stdlib)
│   ├── engine.py              # CoreEngine: boot, routes, error dispatch
│   ├── server.py              # HTTP + WS server (raw socket)
│   ├── router.py              # (method, path) → handler, core-protected
│   ├── loader.py              # ModuleBase + ModuleLoader (ZIP install)
│   ├── sandbox.py             # Per-module fs jail
│   ├── project_manager.py     # Project CRUD + file ops + ZIP upload
│   ├── runner.py              # ProcessRunner (subprocess + kill group)
│   ├── settings.py            # Global + per-module settings
│   ├── diagnostics.py         # DiagnosticsManager (collect from modules)
│   └── data/                  # Auto-created: logs/, settings.json, .run_pids.json
│
├── frontend/                  # Client
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js             # REST wrapper
│       ├── ws.js              # WS client + auto reconnect
│       ├── explorer.js        # Project tree + file list
│       ├── editor.js          # CodeMirror manager (tabs, getCm, openFileAtLine)
│       ├── app.js             # Glue: bindings, run, logs, modules, WS routing
│       ├── diagnostics.js     # Problems panel + inline markers
│       ├── settings.js        # Settings modal UI
│       └── overlay.js         # Inject module CSS/JS with safe mode
│
├── modules/                   # User modules (per-module sandbox)
│   └── <name>/
│       ├── init.txt           # Metadata (JSON)
│       ├── main.py            # class Module(ModuleBase)
│       ├── data/              # Sandbox (auto-created)
│       └── web/               # Optional web UI
│           ├── index.html
│           ├── overlay.css    # Optional — injected vào UI chính
│           └── overlay.js     # Optional — injected vào UI chính
│
├── projects/                  # User projects
│   └── <name>/
│       ├── .project.json
│       └── ...
│
└── overrides/                 # Optional .py patches (dev only)
    └── *.py                   # exec() với ns = {engine, sandbox, config, router}
```

---

3. Quick start

Chạy lần đầu

```bash
cd /path/to/acdv-coder
python3 main.py
```

Mở: http://localhost:8765

Nếu không có output

```bash
# 1. Verify main.py là entry point đúng
head -1 main.py
# Kỳ vọng: #!/usr/bin/env python3

# 2. Verify import chain OK
python3 -c "from core.engine import CoreEngine; print('OK')"

# 3. Smoke test backend trực tiếp
python3 - <<'EOF'
import os, json, sys, time
sys.path.insert(0, '.')
from core.engine import CoreEngine
with open('config.json') as f: cfg = json.load(f)
eng = CoreEngine(os.getcwd(), cfg)
eng.boot()
time.sleep(2)
eng.shutdown()
EOF
```

Nếu port bị chiếm

```bash
python3 main.py --port 9000
# hoặc
fuser -k 8765/tcp
```

Fix main.py bị đè

Nếu head -1 main.py không phải #!/usr/bin/env python3 → đã bị đè. Restore:

```python
#!/usr/bin/env python3
"""ACDV-Teams Coder — Entry point."""
import os, sys, json, signal, argparse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from core.engine import CoreEngine

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    args = p.parse_args()

    cfg_path = os.path.join(BASE_DIR, "config.json")
    with open(cfg_path, encoding="utf-8") as f:
        config = json.load(f)
    if args.host: config["host"] = args.host
    if args.port: config["port"] = args.port

    engine = CoreEngine(BASE_DIR, config)
    signal.signal(signal.SIGINT, lambda *_: (engine.shutdown(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda *_: (engine.shutdown(), sys.exit(0)))
    engine.boot()
    engine.run_forever()

if __name__ == "__main__":
    main()
```

---

4. Architecture

```
┌──────────────────────────────────────────────────────┐
│  Browser (CodeMirror + vanilla JS)                   │
│  api.js → REST    ws.js → live updates              │
│  overlay.js injects module CSS/JS                    │
└──────────────────┬───────────────────────────────────┘
                   │ HTTP + WS (raw socket, no framework)
┌──────────────────▼───────────────────────────────────┐
│  CoreEngine (core/engine.py)                         │
│  ├─ Router       (core-protected vs module routes)   │
│  ├─ HttpWsServer (raw socket, WS frames)             │
│  ├─ ModuleLoader (scan modules/, ZIP install)        │
│  ├─ Sandbox      (per-module fs jail)                │
│  ├─ ProcessRunner(subprocess + process-group kill)   │
│  ├─ SettingsMgr  (global + per-module schema)        │
│  ├─ Diagnostics  (collect problems from modules)     │
│  └─ ErrorDispatch(chain: module interceptors)        │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│  Disk                                                │
│  projects/, modules/, core/data/, frontend/          │
└──────────────────────────────────────────────────────┘
```

Luồng 1 request HTTP

```
client → server._handle_http
       → router.match(method, path)
       → handler(req)
       → 200 + JSON
       │
       └─ nếu handler raise:
          → engine.dispatch_error(ctx)
            ├─ module.on_any_error(ctx)       (all modules)
            ├─ module.on_http_error(ctx)      (chain)
            └─ nếu return dict → response body
          → nếu None → 500 Internal Error
```

Luồng module lifecycle

```
boot()
  → scan_and_load_all()
     → load_module(name)
        → đọc init.txt (metadata)
        → detect web/overlay.css|js
        → import main.py
        → tìm class Module(ModuleBase)
        → instance.on_load()
        → register settings_schema
        → register diagnostics provider
        → engine.register_module(instance)
           → router.add route (reject nếu collide core)
  → recover_sessions() → mod.on_recovery()
```

---

5. Module contract

init.txt — metadata (JSON)

```json
{
  "name": "my_module",
  "version": "1.0.0",
  "description": "Demo module",
  "critical": false,

  "routes": [
    { "method": "GET",  "path": "/api/my_module/hello", "handler": "hello" }
  ],

  "ui_buttons": [
    {
      "id": "run_main",
      "label": "Run main.py",
      "icon": "▶",
      "color": "success",
      "action": "run",
      "params": { "project": "demo", "path": "main.py" },
      "confirm": "Chạy main.py?"
    }
  ],

  "settings_schema": {
    "enabled":   { "type": "boolean", "default": true, "label": "Enable" },
    "threshold": { "type": "number",  "default": 10, "min": 1, "max": 100, "label": "Threshold" },
    "mode":      { "type": "select",  "default": "auto", "options": ["auto","strict","loose"] }
  },

  "diagnostics": {
    "files": ["*.py"]
  }
}
```

main.py — class Module

```python
from core.loader import ModuleBase

class Module(ModuleBase):

    # === lifecycle ===
    def on_load(self):              pass
    def on_recovery(self):          pass
    def on_shutdown(self):          pass

    # === settings (v1.2.2+) ===
    def on_settings_changed(self, new_settings):   pass
    def get_settings(self) -> dict:                ...

    # === diagnostics (v1.2.2+) ===
    def diagnose(self, project, path, content) -> list[dict]:
        """Return [{"severity": "error"|"warning"|"info"|"hint",
                    "line", "column", "end_line", "end_column",
                    "message", "code"}]"""
        return []

    # === error interceptors (v1.3.0+) ===
    def on_any_error(self, ctx) -> dict | None:
        """ctx = {source, error, traceback, method?, path?, request?,
                  module?, button_id?, params?}"""
        return None

    def on_http_error(self, ctx) -> dict | None:      return None
    def on_ws_route_error(self, ctx) -> dict | None:  return None
    def on_ws_action_error(self, ctx) -> dict | None: return None

    # === routes (declared in init.txt) ===
    def hello(self, req) -> dict:
        return { "ok": True, "msg": "Hello" }

    # === ui_buttons (custom action) ===
    def on_button_<id>(self, params) -> dict:  # vd: on_button_run_main
        return { "ok": True }
```

Error interceptor return shape

```python
# Không xử lý → cho pass through
return None
# hoặc
return { "handled": False }

# Xử lý, dùng response trực tiếp
return { "handled": True, "response": { "ok": False, "error": "...", "custom": True } }

# Xử lý, dùng chính dict đó làm response
return { "ok": False, "error": "...", "custom": True }
```

---

6. API Reference

Core

Endpoint Method Body Response
/api/status GET — {status, version, uptime_modules}
/api/modules GET — {<name>: metadata}
/api/modules/install POST {zip_base64} {ok, module}
/api/modules/uninstall POST {name} {ok}
/api/modules/reload POST {name} {ok}

Projects

Endpoint Method Body
/api/projects GET —
/api/projects/create POST {name, language}
/api/projects/upload POST {name, zip_base64}
/api/projects/delete POST {name}
/api/projects/tree POST {project}
/api/projects/file/read POST {project, path}
/api/projects/file/write POST {project, path, content}
/api/projects/file/create POST {project, path}
/api/projects/file/delete POST {project, path}
/api/projects/file/rename POST {project, old_path, new_path}
/api/projects/folder/create POST {project, path}

Run

Endpoint Method Body
/api/projects/run POST {project, path}
/api/projects/run/stop POST {force?: bool}
/api/projects/run/status GET —

Logs

Endpoint Method Body
/api/projects/logs/list POST {project?}
/api/projects/logs/read POST {name}
/api/projects/logs/delete POST {name}

Settings

Endpoint Method Body
/api/settings GET —
/api/settings POST {<patch>}
/api/settings/modules POST {}
/api/settings/module/get POST {name}
/api/settings/module/set POST {name, values}

Diagnostics

Endpoint Method Body
/api/diagnostics/check POST {project, path}
/api/diagnostics/file POST {project, path}
/api/diagnostics/all GET —
/api/diagnostics/clear POST {project?, path?}

Overlay

Endpoint Method Response
/api/overlay GET {ok, safe_mode, overlays:[{name,css,js,css_enabled,js_enabled}]}

Module static

```
GET /module/<name>/                  → web/index.html
GET /module/<name>/overlay.css       → web/overlay.css
GET /module/<name>/overlay.js        → web/overlay.js
GET /module/<name>/*                 → web/*
```

---

7. WebSocket protocol

Client → Server

```jsonc
{ "type": "ping", "time": 1234567890 }
{ "type": "status" }
{ "type": "modules" }
{ "type": "settings" }
{ "type": "module_settings", "module": "my_module" }

{ "type": "route", "id": "req-1",
  "method": "POST", "path": "/api/status", "body": {} }

{ "type": "module_action",
  "module": "my_module", "button_id": "custom_do", "params": {"x": 1} }
```

Server → Client

```jsonc
{ "type": "pong", "time": 1234567890 }
{ "type": "status", "data": {modules, running, clients, runner, settings} }
{ "type": "modules", "data": {...} }
{ "type": "settings", "data": {...} }
{ "type": "route_result", "id": "req-1", "ok": true, "data": {...} }
{ "type": "module_action_result", "module": "x", "button_id": "y", "ok": true, "result": {...} }

// Run events (broadcast)
{ "type": "run_started",  "project", "path", "log_name", "pid" }
{ "type": "run_output",   "project", "path", "lines": ["...", "..."] }
{ "type": "run_finished", "project", "path", "exit_code", "log_name" }

// Diagnostics (broadcast)
{ "type": "diagnostics_update",  "project", "path", "diagnostics": [...] }
{ "type": "diagnostics_cleared" }

// Settings (broadcast)
{ "type": "settings_changed",        "settings": {...} }
{ "type": "module_settings_changed", "module", "values": {...} }
```

---

8. Dev workflow

Thêm 1 module mới

```bash
mkdir -p modules/my_mod/web
cd modules/my_mod
```

init.txt:

```json
{
  "name": "my_mod",
  "version": "1.0.0",
  "routes": [
    { "method": "GET", "path": "/api/my_mod/ping", "handler": "ping" }
  ],
  "settings_schema": {
    "enabled": { "type": "boolean", "default": true, "label": "Enable" }
  }
}
```

main.py:

```python
from core.loader import ModuleBase

class Module(ModuleBase):
    def on_load(self):
        print(f"[{self.name}] loaded, settings={self.get_settings()}")

    def ping(self, req):
        return { "ok": True, "pong": True }

    def diagnose(self, project, path, content):
        return []  # hoặc list problems
```

Test:

```bash
# Reload trong UI, hoặc:
curl http://localhost:8765/api/modules/reload \
  -H 'Content-Type: application/json' \
  -d '{"name":"my_mod"}'

curl http://localhost:8765/api/my_mod/ping
```

Thêm 1 route mới (core)

Trong core/engine.py → _init_core():

```python
A = self.router.add_core          # ← protected route
A("GET", "/api/my_endpoint", self._api_my_endpoint)
```

⚠️ LUÔN dùng add_core cho core routes. Nếu dùng router.add, module có thể override.

Thêm 1 overlay (CSS/JS cho UI chính)

```bash
# Trong module
touch modules/my_mod/web/overlay.css
touch modules/my_mod/web/overlay.js
```

Sau đó reload → bật/tắt trong Settings → Overlays. Test safe mode: mở ?safe=1 (skip hết overlay).

Trigger diagnostics

```python
# Trong module
def diagnose(self, project, path, content):
    if not path.endswith(".py"):
        return []
    return [{
        "severity": "warning",
        "line": 1, "column": 1, "end_line": 1, "end_column": 5,
        "message": "Example warning",
        "code": "MY001"
    }]
```

Save file → diagnostics tự chạy (nếu settings.diagnostics.auto_run_on_save = true). Kết quả broadcast qua WS → Problems panel + inline markers.

Intercept errors

```python
# Trong module
def on_http_error(self, ctx):
    if "/api/projects/" not in ctx.get("path", ""):
        return None
    return {
        "ok": False,
        "error": f"Intercepted: {ctx['error']}",
        "custom": True
    }
```

Test: gọi API lỗi → response bị replace.

---

9. Testing cheat-sheet

```bash
# Backend up?
curl http://localhost:8765/api/status

# Module list
curl http://localhost:8765/api/modules

# Create project
curl -X POST http://localhost:8765/api/projects/create \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo","language":"python"}'

# Run file
curl -X POST http://localhost:8765/api/projects/run \
  -H 'Content-Type: application/json' \
  -d '{"project":"demo","path":"main.py"}'

# Stop
curl -X POST http://localhost:8765/api/projects/run/stop \
  -H 'Content-Type: application/json' -d '{"force":false}'

# Diagnostics check
curl -X POST http://localhost:8765/api/diagnostics/check \
  -H 'Content-Type: application/json' \
  -d '{"project":"demo","path":"main.py"}'

# Settings
curl http://localhost:8765/api/settings
curl -X POST http://localhost:8765/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"editor":{"font_size":16}}'

# Overlays
curl http://localhost:8765/api/overlay

# Module static
curl http://localhost:8765/module/my_mod/
curl http://localhost:8765/module/my_mod/overlay.css
```

Reset trạng thái khi kẹt

```bash
# Kill process còn sót
pkill -f "python main.py"
fuser -k 8765/tcp

# Xoá PID tracking
rm core/data/.run_pids.json

# Reset settings
rm core/data/settings.json

# Clear diag cache (server restart là đủ)
```

---

10. Known issues / TODO

🔴 Bug cần fix ngay

☐ main.py bị module đè — verify mỗi lần clone, add CI check
☐ Version mismatch: config.json = 1.2.2, code ghi 1.3.0 — bump đồng bộ

🟡 Cần test kỹ

☐ Error dispatch chain: on_any_error → on_http_error (pass-through + handle)
☐ Settings modal: schema validation, save/load, on_settings_changed callback
☐ Overlay: CSS injection, JS injection, safe mode ?safe=1, per-module toggle
☐ Diagnostics: auto-run on save, inline markers, jump-to-line, WS broadcast
☐ Core route protection: module cố override /api/status phải bị reject

🟢 Nice to have

☐ Project export ZIP
☐ Import from Git URL
☐ Terminal panel (chạy lệnh trực tiếp)
☐ Multi-user auth
☐ Syntax validation trước khi save
☐ Resource limits (CPU/mem per process)

---

11. Roadmap

v1.3.x — polish

· Fix main.py bug + version bump
· Test suite (pytest cho core, jsdom/playwright cho frontend)
· Error dispatch chain: docs + example module
· Diagnostics: severity filter trong UI

v1.4.0 — developer experience

· Hot reload module (watch modules/*/main.py)
· Terminal panel
· Project export
· Preview HTML project (/preview/<project>/)

v2.0.0 — scale

· Multi-user + auth
· Collaborative editing (WS)
· Docker isolation per project
· Resource limits

---

12. Legal

Educational / personal use. Không cài module từ nguồn không tin cậy — module có toàn quyền Python. Không chạy server bằng sudo.

```

---

## 📋 Tóm tắt thay đổi so với README cũ

| Mục | Bản cũ | Bản mới |
|---|---|---|
| Độ dài | ~1000 dòng | ~450 dòng |
| Focus | Marketing + feature | Dev workflow + reference |
| Bug section | ❌ Không có | ✅ Known issues rõ ràng |
| Quick start | Chỉ cần chạy | Có troubleshoot `main.py` bug |
| API ref | Rải rác | ✅ 1 bảng duy nhất |
| WS protocol | Dài dòng | ✅ Compact jsonc |
| Dev workflow | Sơ sài | ✅ Copy-paste recipes |
| Testing | Chỉ curl | ✅ Cheat-sheet + reset |
| Roadmap | Quá chi tiết | ✅ Ngắn, thực tế |

