📘 README.md — ACDV-Teams Coder v1.3.6

```markdown
# ACDV-Teams Coder

Local web IDE — Python stdlib backend, CodeMirror frontend, module extension system, terminal over WebSocket, per-tab undo/redo, export/import ZIP.

**Version:** `1.3.6` · **Platform:** Python 3.8+ · **Deps:** none (stdlib only) · **Terminal:** xterm.js (CDN)

> 📖 **Dev guide:** Đọc mục [§5 Module Contract](#5-module-contract) và [§6 Tạo module từ A→Z](#6-tạo-module-từ-az) trước khi viết module mới.

---

## Mục lục

1. [Status](#1-status)
2. [Quick start](#2-quick-start)
3. [Cấu trúc thư mục](#3-cấu-trúc-thư-mục)
4. [Architecture](#4-architecture)
5. [Module Contract](#5-module-contract) ⭐
6. [Tạo module từ A→Z](#6-tạo-module-từ-az) ⭐
7. [API Reference](#7-api-reference)
8. [WebSocket Protocol](#8-websocket-protocol)
9. [Frontend / Editor](#9-frontend--editor)
10. [Undo / Redo](#10-undo--redo) ⭐ v1.3.3
11. [Terminal](#11-terminal) ⭐ v1.3.2
12. [Export / Import ZIP](#12-export--import-zip) ⭐ v1.3.6
13. [Dev workflow](#13-dev-workflow)
14. [Testing cheat-sheet](#14-testing-cheat-sheet)
15. [Troubleshooting](#15-troubleshooting)
16. [Known issues / Roadmap](#16-known-issues--roadmap)
17. [Legal](#17-legal)

---

## 1. Status

| Layer | State |
|---|---|
| Core engine + router + server | ✅ Ổn định |
| Project manager + ZIP upload | ✅ Ổn định |
| Process runner (`.py`/`.js`/`.sh`) | ✅ Ổn định (process-group kill) |
| Module loader + ZIP install | ✅ Ổn định |
| Diagnostics (VS Code style) | ✅ Ổn định |
| Settings (global + per-module) | ✅ v1.3.2 — WS broadcast + apply ngay |
| Overlay CSS/JS (`web/` + `data/`) | ✅ v1.3.1 — file lớn đọc từ `data/` |
| Error dispatch chain | ⚠️ Mới — cần test thêm |
| Frontend editor + explorer | ✅ Ổn định |
| Frontend settings UI + About tab | ✅ Ổn định |
| Frontend diagnostics UI | ✅ Ổn định |
| Code folding | ✅ v1.3.1 — gutter + nút ⇕ + hotkey |
| Android editor | ✅ v1.3.2 — fix backspace xoá dòng cuối |
| Settings hot apply | ✅ v1.3.2 — không cần reload trang |
| Theme switcher | ✅ v1.3.2 — dracula / default / material / monokai / solarized / eclipse |
| **Undo / Redo per-tab** | ✅ **v1.3.3** — giống VS Code, history bảo toàn khi đổi tab |
| **Dirty flag chính xác** | ✅ **v1.3.3** — undo về trạng thái đã lưu → dấu ● biến mất |
| Editor line wrap | ✅ v1.3.1 — mặc định **tắt**, đọc từ settings |
| Terminal (xterm.js + PTY) | ✅ v1.3.2 — Ctrl+`, gắn với WS client |
| Module watcher (auto-detect) | ✅ v1.3.5 — tự load/unload module khi filesystem thay đổi |
| System controls (restart/shutdown) | ✅ v1.3.5 — `/api/system/*` |
| **Export Project / Module ZIP** | ✅ **v1.3.6** — download ZIP round-trip, tương thích upload |
| Demo module | ✅ `modules/demo_module/` |
| Code reminder module | ✅ `modules/code_reminder/` |

---

## 2. Quick start

```bash
cd /path/to/acdv-coder
python3 main.py
```

Mở: http://localhost:8765

Troubleshoot nhanh

```bash
# 1. Verify main.py là entry point đúng
head -1 main.py
# Kỳ vọng: #!/usr/bin/env python3

# 2. Verify import chain OK
python3 -c "from core.engine import CoreEngine; print('OK')"

# 3. Port bị chiếm
python3 main.py --port 9000
# hoặc
fuser -k 8765/tcp

# 4. Reset trạng thái
pkill -f "python main.py"
rm core/data/.run_pids.json
rm core/data/settings.json
```

---

3. Cấu trúc thư mục

```
acdv-coder/
├── main.py                    # Entry point — KHÔNG được đè
├── config.json                # host/port/version/terminal
├── README.md
│
├── core/                      # Backend (Python stdlib)
│   ├── engine.py              # CoreEngine: boot, routes, error dispatch
│   ├── server.py              # HTTP + WS server (raw socket)
│   ├── router.py              # (method, path) → handler, core-protected
│   ├── loader.py              # ModuleBase + ModuleLoader (ZIP install + export)
│   ├── sandbox.py             # Per-module fs jail
│   ├── project_manager.py     # Project CRUD + file ops + ZIP upload/export
│   ├── runner.py              # ProcessRunner (subprocess + kill group)
│   ├── settings.py            # Global + per-module settings
│   ├── diagnostics.py         # DiagnosticsManager
│   ├── terminal.py            # ⭐ v1.3.2 TerminalManager (PTY + WS)
│   └── data/                  # Auto-created: logs/, settings.json, .run_pids.json
│
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js             # ⭐ v1.3.6: exportProject / exportModule
│       ├── ws.js
│       ├── explorer.js        # ⭐ v1.3.6: nút ⬇ trong project list
│       ├── editor.js          # ⭐ v1.3.3: per-tab Doc + undo/redo + dirty chính xác
│       ├── app.js             # ⭐ v1.3.6: exportProject/exportModule + nút ⬇ module list
│       ├── diagnostics.js
│       ├── settings.js        # ⭐ v1.3.2: theme options + hot apply
│       ├── terminal.js        # ⭐ v1.3.2: xterm.js wrapper
│       └── overlay.js
│
├── modules/
│   ├── demo_module/           # Template đầy đủ contract
│   ├── code_reminder/         # Ví dụ: diagnostics module thực tế
│   └── <your_module>/
│       ├── init.txt           # Metadata (JSON)
│       ├── main.py            # Class Module
│       ├── data/              # Sandbox + overlay file lớn
│       │   ├── overlay.css    # ⭐ v1.3.1: ưu tiên cao nhất
│       │   ├── overlay.js
│       │   └── settings.json  # Auto-created per-module settings
│       └── web/
│           ├── index.html     # (optional) custom UI page
│           ├── overlay.css    # fallback (file nhỏ)
│           └── overlay.js
│
├── projects/                  # User projects
└── overrides/                 # Optional .py patches (dev only)
```

---

4. Architecture

```
┌──────────────────────────────────────────────────────┐
│  Browser (CodeMirror + xterm.js + vanilla JS)        │
│  api.js → REST    ws.js → live updates + terminal    │
│  overlay.js injects module CSS/JS                    │
└──────────────────┬───────────────────────────────────┘
                   │ HTTP + WS (raw socket, no framework)
┌──────────────────▼───────────────────────────────────┐
│  CoreEngine (core/engine.py)                         │
│  ├─ Router       (core-protected vs module routes)   │
│  ├─ HttpWsServer (raw socket, WS frames)             │
│  ├─ ModuleLoader (scan modules/, ZIP install/export) │
│  ├─ Sandbox      (per-module fs jail)                │
│  ├─ ProcessRunner(subprocess + process-group kill)   │
│  ├─ SettingsMgr  (global + per-module schema)        │
│  ├─ Diagnostics  (collect problems from modules)     │
│  ├─ TerminalMgr  (PTY per WS, resize, kill)          │
│  └─ ErrorDispatch(chain: module interceptors)        │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│  Disk: projects/, modules/, core/data/, frontend/    │
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

Luồng serve module asset

```
GET /module/<name>/overlay.css
  → loader.py detect: web/overlay.css
  → server serve web/overlay.css

GET /module/<name>/_data_/overlay.css    ⭐ file lớn
  → loader.py detect: data/overlay.css
  → server strip `_data_/` prefix
  → serve data/overlay.css
```

Luồng Undo/Redo (⭐ v1.3.3)

```
Mỗi tab giữ một CodeMirror.Doc riêng (tab.doc)
  ↓
Khi activate tab
  → cm.swapDoc(tab.doc)
  → toàn bộ undo history của tab được bảo toàn
  ↓
Ctrl+Z (focus trong editor)
  → CodeMirror keymap tự xử lý (không qua App)
  ↓
Ctrl+Z (focus ngoài editor)
  → App._isEditableTarget() = false
  → App.editor.undo() → cm.undo()
  ↓
Nút ↶ / ↷ trên toolbar
  → disable khi historySize().undo/redo === 0
  ↓
Dirty flag = (cm.getValue() !== tab.content)
  → undo về trạng thái đã lưu → ● tự biến mất
```

Luồng Terminal (⭐ v1.3.2)

```
browser (xterm.js)
  → ws.send({type:"terminal_open", id, cols, rows, cwd})
    → server._handle_ws_message
    → TerminalManager.open(id, ws, cols, rows, cwd_hint)
    → pty.openpty() + Popen(shell, start_new_session=True)
    → reader thread đọc master_fd
    → ws.send({type:"terminal_output", id, data})

keyboard input
  → term.onData → ws.send({type:"terminal_input", id, data})
  → TerminalManager.write(id, data) → os.write(master_fd, data)

resize
  → term.onResize → ws.send({type:"terminal_resize", id, cols, rows})
  → TIOCSWINSZ + SIGWINCH

WS disconnect
  → server close_by_ws(ws) → kill toàn bộ session của client đó
```

Luồng Export ZIP (⭐ v1.3.6)

```
UI click ⬇ (project item hoặc module item)
  → App.exportProject(name) / App.exportModule(name)
  → API.exportProject(name) / API.exportModule(name)
    → POST /api/projects/export   |  POST /api/modules/export
      → ProjectManager.export_zip(name)         (walk thư mục → zipfile)
      |  ModuleLoader.export_module_zip(name)   (walk thư mục → zipfile)
      → trả {ok, filename, size, files, zip_base64}
    → App._downloadBase64(b64, filename)
      → atob → Uint8Array → Blob → <a download> click
    → Browser tự động tải xuống
```

Luồng Import ZIP (existing)

```
UI file picker (📤)
  → FileReader.readAsDataURL → base64
  → API.uploadProject(name, b64)  |  API.installModule(b64)
    → create_from_zip(name, b64)  |  install_from_zip(tmpfile)
    → validate zip-slip + strip root folder
    → extract → load_module / metadata
```

---

5. Module Contract

5.1. init.txt — Metadata (JSON)

```json
{
  "name": "my_module",
  "version": "1.0.0",
  "description": "Mô tả ngắn",
  "critical": false,

  "routes": [
    { "method": "GET",  "path": "/api/my_module/hello", "handler": "hello" },
    { "method": "POST", "path": "/api/my_module/check", "handler": "check" }
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
    },
    {
      "id": "ping",
      "label": "Ping",
      "icon": "📡",
      "color": "info",
      "action": "route",
      "params": { "method": "GET", "path": "/api/my_module/hello" }
    }
  ],

  "settings_schema": {
    "enabled":   { "type": "boolean", "default": true, "label": "Enable" },
    "threshold": { "type": "number",  "default": 10, "min": 1, "max": 100, "label": "Threshold" },
    "mode":      { "type": "select",  "default": "auto", "options": ["auto","strict","loose"] }
  },

  "diagnostics": {
    "files": ["*.py", "*.js"]
  }
}
```

Các field quan trọng:

Field Bắt buộc Ý nghĩa
name ✅ Tên module (unique, không có /, ..)
version ✅ Semver
routes[] — Endpoint module tự khai báo
ui_buttons[] — Nút hiển thị trong tab Modules
settings_schema — Schema để render UI settings
diagnostics.files — Glob file cần chạy diagnose()

5.2. main.py — Class Module

```python
from core.loader import ModuleBase


class Module(ModuleBase):
    # ─── Lifecycle ──────────────────────────────────────
    def on_load(self):              pass   # sau khi init
    def on_recovery(self):          pass   # sau khi boot engine xong
    def on_shutdown(self):          pass   # khi engine shutdown

    # ─── Settings ───────────────────────────────────────
    def on_settings_changed(self, new_settings):   pass
    def get_settings(self) -> dict:                ...
    # (base class đã override get_settings — merge schema defaults)

    # ─── Diagnostics ────────────────────────────────────
    def diagnose(self, project, path, content) -> list[dict]:
        return []

    # ─── Error interceptors ─────────────────────────────
    def on_any_error(self, ctx) -> dict | None:      return None
    def on_http_error(self, ctx) -> dict | None:     return None
    def on_ws_route_error(self, ctx) -> dict | None: return None
    def on_ws_action_error(self, ctx) -> dict | None:return None

    # ─── Routes (declared in init.txt) ──────────────────
    def hello(self, req) -> dict:
        return { "ok": True, "msg": "Hello" }

    # ─── UI button handlers ─────────────────────────────
    # Convention: on_button_<id> khớp với ui_buttons[].id
    def on_button_run_main(self, params) -> dict:
        return { "ok": True }
```

5.3. Diagnostic shape

Module trả về list dict, mỗi dict:

```python
{
    "severity":   "error" | "warning" | "info" | "hint",
    "line":       1,          # bắt buộc (1-indexed)
    "column":     1,
    "end_line":   1,
    "end_column": 5,
    "message":    "Mô tả lỗi",
    "code":       "MY001",
}
```

5.4. Error interceptor return shape

```python
return None                                            # pass through
return { "handled": False }                            # pass through
return { "handled": True, "response": { ... } }        # handled
return { "ok": False, "error": "..." }                 # handled (dùng luôn)
```

ctx dict truyền vào interceptor:

```python
# HTTP error
{
    "source":     "http",
    "method":     "POST",
    "path":       "/api/projects/run",
    "request":    { ... },        # req dict
    "error":      "...",
    "traceback":  "...",
}

# WS route error
{ "source": "ws_route", "method", "path", "request", "error", "traceback" }

# WS action error
{ "source": "ws_action", "module", "button_id", "params", "error", "traceback" }
```

5.5. Overlay CSS/JS — web/ vs data/

Module có thể chèn CSS/JS vào frontend. Hai vị trí (loader tự detect):

Vị trí Dùng khi URL
web/overlay.css File nhỏ (< 50KB) /module/<name>/overlay.css
web/overlay.js  /module/<name>/overlay.js
data/overlay.css ⭐ File lớn (bundle, vendor) /module/<name>/data/overlay.css
data/overlay.js ⭐  /module/<name>/data/overlay.js

Thứ tự ưu tiên: data/ TRƯỚC, rồi mới fallback web/.

Không cần khai báo gì trong init.txt — loader tự detect và expose qua /api/overlay.

Test safe mode (không inject overlay): http://localhost:8765/?safe=1

5.6. Sandbox

Mỗi module có jail riêng tại modules/<name>/data/:

```python
def my_handler(self, req):
    # ✅ OK
    self.sandbox.write("my_module", "cache.json", '{"x":1}')
    data = self.sandbox.read("my_module", "cache.json")

    # ❌ Raise SandboxViolation
    self.sandbox.read("my_module", "../../etc/passwd")
```

API Sandbox: resolve, open, read, write, delete, list_dir.

5.7. Ví dụ module đầy đủ

Xem 2 module mẫu:

· modules/demo_module/ — template đơn giản, đủ contract
· modules/code_reminder/ — ví dụ thực tế: regex scan TODO/FIXME, dedup pattern, custom diagnostics

---

6. Tạo module từ A→Z

Bước 1 — Khung thư mục

```bash
mkdir -p modules/my_mod/web modules/my_mod/data
cd modules/my_mod
```

Bước 2 — init.txt

```json
{
  "name": "my_mod",
  "version": "1.0.0",
  "description": "Module ví dụ",
  "critical": false,

  "routes": [
    { "method": "GET",  "path": "/api/my_mod/ping", "handler": "ping" }
  ],

  "ui_buttons": [
    { "id": "show_info", "label": "Info", "icon": "ℹ", "color": "info", "action": "run", "params": {} }
  ],

  "settings_schema": {
    "enabled": { "type": "boolean", "default": true, "label": "Enable" }
  },

  "diagnostics": { "files": ["*.py"] }
}
```

Bước 3 — main.py

```python
from core.loader import ModuleBase


class Module(ModuleBase):
    def on_load(self):
        print(f"[{self.name}] loaded")

    def ping(self, req):
        return { "ok": True, "pong": True }

    def on_button_show_info(self, params):
        return { "ok": True, "settings": self.get_settings() }

    def diagnose(self, project, path, content):
        if not path.endswith(".py"):
            return []
        diags = []
        for i, line in enumerate(content.split("\n"), 1):
            if "TODO" in line:
                diags.append({
                    "severity": "warning",
                    "line": i, "column": 1,
                    "end_line": i, "end_column": len(line) + 1,
                    "message": "TODO còn tồn đọng",
                    "code": "MY001",
                })
        return diags
```

Bước 4 — Overlay (optional)

CSS nhỏ:

```bash
echo '.my-mod-banner { color: #4af; }' > web/overlay.css
```

JS lớn (đọc từ data/):

```bash
cp ~/vendor/bundle.js data/overlay.js   # ⭐ file lớn
```

Bước 5 — Load & test

```bash
# Từ project root
curl -X POST http://localhost:8765/api/modules/reload \
  -H 'Content-Type: application/json' -d '{"name":"my_mod"}'

curl http://localhost:8765/api/my_mod/ping

# Verify overlay
curl http://localhost:8765/api/overlay
```

Xem UI: tab Modules → nút Info → tab Settings → Modules (render settings).

Bước 6 — Package thành ZIP

Có 2 cách:

Cách A — Export từ UI (⭐ v1.3.6):

· Vào tab Modules → click nút ⬇ cạnh module → file <name>.zip tự tải về.

Cách B — zip thủ công:

```bash
cd modules && zip -r my_mod.zip my_mod/
# Upload qua UI: tab Modules → 📤
```

Loader tự:

1. Validate init.txt có name
2. Chặn path traversal (..)
3. Extract vào modules/<name>/
4. Auto-load module

💡 ZIP export từ UI có thể upload lại qua 📤 (round-trip hoàn hảo).

---

7. API Reference

Core

Endpoint Method Body Response
/api/status GET — {status, version, uptime_modules}
/api/modules GET — {<name>: metadata}
/api/modules/install POST {zip_base64} {ok, module}
/api/modules/uninstall POST {name} {ok}
/api/modules/reload POST {name} {ok}
/api/modules/export POST {name} {ok, filename, size, files, zip_base64} ⭐ v1.3.6
/api/terminal/sessions GET — {ok, sessions: [{id, pid, cwd, cols, rows}]}

Projects

Endpoint Method Body
/api/projects GET —
/api/projects/create POST {name, language}
/api/projects/upload POST {name, zip_base64}
/api/projects/delete POST {name}
/api/projects/export POST {name} → {ok, filename, size, files, zip_base64} ⭐ v1.3.6
/api/projects/tree POST {project}
/api/projects/file/read POST {project, path}
/api/projects/file/write POST {project, path, content}
/api/projects/file/create POST {project, path}
/api/projects/file/delete POST {project, path}
/api/projects/file/rename POST {project, old_path, new_path}
/api/projects/folder/create POST {project, path}

Run / Logs

Endpoint Method Body
/api/projects/run POST {project, path}
/api/projects/run/stop POST {force?: bool}
/api/projects/run/status GET —
/api/projects/logs/list POST {project?}
/api/projects/logs/read POST {name}
/api/projects/logs/delete POST {name}

Settings / Diagnostics / Overlay

Endpoint Method Body
/api/settings GET —
/api/settings POST {<patch>} → broadcast settings_changed qua WS
/api/settings/modules POST {}
/api/settings/module/get POST {name}
/api/settings/module/set POST {name, values}
/api/diagnostics/check POST {project, path}
/api/diagnostics/file POST {project, path}
/api/diagnostics/all GET —
/api/diagnostics/clear POST {project?, path?}
/api/overlay GET —

System (⭐ v1.3.5)

Endpoint Method Body
/api/system/restart POST {} → broadcast system_restarting, restart process
/api/system/shutdown POST {} → broadcast system_shutdown, exit process

Gated bởi config.json → enable_system_controls (mặc định true).

Module static

```
GET /module/<name>/                  → web/index.html
GET /module/<name>/overlay.css       → web/overlay.css
GET /module/<name>/overlay.js        → web/overlay.js
GET /module/<name>/*                 → web/*
GET /module/<name>/_data_/*          → data/*    ⭐ v1.3.1
```

---

8. WebSocket Protocol

Client → Server

```jsonc
{ "type": "ping", "time": 1234567890 }
{ "type": "status" }
{ "type": "modules" }
{ "type": "settings" }
{ "type": "module_settings", "module": "my_module" }
{ "type": "route", "id": "req-1", "method": "POST", "path": "/api/status", "body": {} }
{ "type": "module_action", "module": "my_module", "button_id": "custom_do", "params": {"x": 1} }

// ⭐ v1.3.2: terminal
{ "type": "terminal_open",   "id": "t_abc", "cols": 80, "rows": 24, "cwd": "projects/demo" }
{ "type": "terminal_input",  "id": "t_abc", "data": "ls\r" }
{ "type": "terminal_resize", "id": "t_abc", "cols": 100, "rows": 30 }
{ "type": "terminal_close",  "id": "t_abc" }
```

Server → Client

```jsonc
{ "type": "pong", "time": 1234567890 }
{ "type": "status", "data": {modules, running, clients, runner, settings, terminals} }
{ "type": "modules", "data": {...} }
{ "type": "settings", "data": {...} }
{ "type": "route_result", "id": "req-1", "ok": true, "data": {...} }
{ "type": "module_action_result", "module": "x", "button_id": "y", "ok": true, "result": {...} }

// Run events
{ "type": "run_started",  "project", "path", "log_name", "pid" }
{ "type": "run_output",   "project", "path", "lines": ["...", "..."] }
{ "type": "run_finished", "project", "path", "exit_code", "log_name" }

// Diagnostics
{ "type": "diagnostics_update",  "project", "path", "diagnostics": [...] }
{ "type": "diagnostics_cleared" }

// Settings (⭐ v1.3.2: broadcast tới MỌI client để hot-apply)
{ "type": "settings_changed",        "settings": {...} }
{ "type": "module_settings_changed", "module", "values": {...} }

// ⭐ v1.3.5: module auto-detect
{ "type": "modules_changed", "action": "added|removed|reloaded", "module": "..." }

// ⭐ v1.3.5: system controls
{ "type": "system_restarting" }
{ "type": "system_shutdown" }

// ⭐ v1.3.2: terminal
{ "type": "terminal_opened", "id": "t_abc" }
{ "type": "terminal_output", "id": "t_abc", "data": "..." }
{ "type": "terminal_exit",   "id": "t_abc", "code": 0 }
{ "type": "terminal_error",  "id": "t_abc", "error": "..." }
```

---

9. Frontend / Editor

9.1. Editor options mặc định

Option Giá trị Ghi chú
lineWrapping false Đọc lại từ settings.editor.line_wrap
tabSize 4 Đọc từ settings.editor.tab_size
indentUnit 4 
inputStyle "contenteditable" trên Android Fix thụt lề + double-input
electricChars false trên Android 
foldGutter true 
gutters ["CodeMirror-linenumbers", "CodeMirror-foldgutter"]

9.2. Code folding

Thao tác Cách
Fold tại cursor Ctrl-Q
Fold tất cả Ctrl-Shift-[ hoặc nút ⇕ trên toolbar
Unfold tất cả Ctrl-Shift-] hoặc bấm ⇕ lần nữa
Fold riêng 1 block Click ▾ ở gutter bên trái

Hỗ trợ mode Python (indent), JS/CSS/HTML (brace), comment-fold.

9.3. Android keyboard fix (v1.3.2)

Triệu chứng: Trên Android (Chrome/WebView), khi đã xoá hết một dòng, nhấn Backspace không merge với dòng trên (đặc biệt với inputStyle: "contenteditable").

Nguyên nhân: CM5 với contenteditable không tự kích hoạt delCharBefore khi cursor ở ch === 0 trên soft keyboard.

Fix (trong editor.js → _fixAndroidLineMerge):

· Lắng nghe beforeinput (deleteContentBackward / deleteContentForward) — path chính của WebView hiện đại
· Fallback keydown (Backspace/Delete) cho bàn phím cứng
· Khi cursor ở ch === 0 và line > 0 → cm.execCommand("delCharBefore")
· Khi cursor ở cuối dòng và line < lineCount-1 → replaceRange merge thủ công
· Debounce 100ms để tránh fire đôi khi cả beforeinput và keydown cùng bắn

Ngoài ra _applyInputAttributes() set đúng DOM attributes (autocorrect, autocapitalize, spellcheck, autocomplete, font-size: 16px để tránh zoom) — trước đây các option này bị bỏ qua vì không phải option hợp lệ của CodeMirror 5.

9.4. Settings hot apply (v1.3.2)

Triệu chứng trước: Save settings xong nhưng editor không thay đổi cho đến khi F5.

Fix:

1. Server broadcast settings_changed qua WS mỗi lần POST /api/settings thành công
2. app.js lắng nghe settings_changed → editor.onSettingsChanged(newSettings)
3. settings.js chủ động gọi editor.onSettingsChanged() ngay sau saveSettings() (không đợi WS) — idempotent với WS handler
4. editor.onSettingsChanged() → applySettings() → cập nhật font_size, tab_size, line_wrap, theme

Theme options hợp lệ (CM5): dracula, default, material, monokai, solarized, eclipse — CSS được lazy-load từ CDN khi chọn lần đầu. (Các option cũ light/dark không tồn tại trong CodeMirror 5 nên trước đây trông như "không hoạt động".)

9.5. Settings structure

```jsonc
{
  "theme": "dracula",            // dracula|default|material|monokai|solarized|eclipse
  "editor": {
    "font_size": 14,
    "tab_size": 4,
    "line_wrap": false,          // v1.3.1: default OFF
    "auto_save": false
  },
  "diagnostics": {
    "auto_run_on_open": false,
    "auto_run_on_save": true,
    "show_inline": true
  },
  "overlays": {
    "safe_mode": false,
    "per_module": {
      "my_mod": { "css": true, "js": true }
    }
  }
}
```

9.6. Overlay loader (overlay.js)

· Fetch /api/overlay → inject <link> + <script> với ?t=<timestamp>
· Skip nếu ?safe=1 trên URL hoặc settings.overlays.safe_mode = true
· Hiển thị banner "🎨 N overlays active" — dismiss hoặc chuyển safe mode

---

10. Undo / Redo

⭐ v1.3.3 — Hoàn tác / làm lại giống VS Code, per-tab và bảo toàn history khi đổi tab.

10.1. Thao tác

Thao tác Cách
Undo Ctrl+Z / Cmd+Z (focus trong editor hoặc ngoài)
Redo Ctrl+Y hoặc Ctrl+Shift+Z / Cmd+Shift+Z
Undo (mobile) Nút ↶ trên toolbar
Redo (mobile) Nút ↷ trên toolbar
Nút disable Tự disable khi hết history

10.2. Cơ chế hoạt động

Per-tab history — mỗi tab giữ một CodeMirror.Doc riêng:

```javascript
// Khi mở tab mới
const doc = CodeMirror.Doc(content, mode);
tab.doc = doc;

// Khi chuyển tab
cm.swapDoc(tab.doc);  // ← KHÔNG dùng setValue + clearHistory nữa
```

→ Toàn bộ undo stack (kể cả selection state, cursor position, fold state) được bảo toàn nguyên vẹn khi đổi qua lại giữa các tab. Giống VS Code.

Dirty flag chính xác:

```javascript
// Không còn set dirty = true một lần là xong
this.cm.on("change", () => {
  const current = this.cm.getValue();
  const isDirty = current !== tab.content;  // ← so sánh với "last saved"
  if (tab.dirty !== isDirty) { tab.dirty = isDirty; renderTabs(); }
});
```

→ Undo hết về trạng thái đã lưu → dấu ● trên tab tự biến mất.

Global hotkey (app.js):

```javascript
document.addEventListener("keydown", (e) => {
  // ...các shortcut khác...
  if (!mod) return;
  if (this._isEditableTarget(e.target)) return;       // input/modal → bỏ qua
  const cmInput = this.editor.cm.getInputField();
  if (document.activeElement === cmInput) return;      // editor → CM5 tự xử lý
  
  const k = e.key.toLowerCase();
  if (k === "z" && !e.shiftKey)                 this.editor.undo();
  else if (k === "y" || (k === "z" && e.shiftKey)) this.editor.redo();
});
```

→ Không double-undo: khi focus trong editor, CM5 keymap xử lý Ctrl+Z; khi focus ngoài editor (sidebar, panel output…), App xử lý. Hai path không chồng nhau.

10.3. API (EditorManager)

```javascript
editor.undo()           // undo 1 bước, cập nhật nút
editor.redo()           // redo 1 bước
editor.canUndo()        // → boolean
editor.canRedo()        // → boolean
```

10.4. Lưu ý

· Save không clear history — giống VS Code, save xong vẫn undo được (nhưng nếu undo về sau save, dấu ● xuất hiện lại vì content khác last saved)
· Đóng tab → mất history — tương tự VS Code (không có persistent history)
· KHÔNG dùng cm.setValue() khi chuyển tab — sẽ xoá history. Bắt buộc dùng cm.swapDoc(doc)

---

11. Terminal

⭐ v1.3.2 — Terminal tích hợp sẵn, chạy shell thật trên server qua WebSocket.

11.1. Yêu cầu

· POSIX: dùng PTY (pty.openpty) → hỗ trợ app interactive (vim, top, htop, less…)
· Windows: fallback pipe (không có PTY, hạn chế app fullscreen)
· Frontend: xterm.js 5.3 + addons fit, web-links (load từ CDN trong index.html)

11.2. Thao tác

Thao tác Cách
Mở/đóng terminal panel `Ctrl+\`` hoặc nút ⌨ trên toolbar
Mở session Tự động khi mở tab Terminal lần đầu
Restart session Nút ⟳ trên header terminal
Kill session Nút 🗑 trên header terminal
Resize Tự động theo panel (FitAddon)
Copy / paste Chuột phải / Shift+Insert (native xterm)

11.3. Bảo mật & giới hạn

· Mỗi session gắn với một WS client — disconnect → auto kill session đó
· max_sessions (mặc định 8) — cấu hình trong config.json
· shell (mặc định $SHELL hoặc /bin/bash) — cấu hình trong config.json
· cwd_hint chỉ cho phép nằm trong base_dir (chống escape)
· Không có sandbox OS-level — terminal có quyền user chạy server. Không chạy bằng sudo.

11.4. Config

```json
{
  "terminal": {
    "shell": null,          // null → $SHELL hoặc /bin/bash
    "max_sessions": 8
  }
}
```

11.5. Debug endpoint

```bash
curl http://localhost:8765/api/terminal/sessions
# { "ok": true, "sessions": [{ "id": "t_abc", "pid": 12345, "cwd": "...", "cols": 80, "rows": 24 }] }
```

---

12. Export / Import ZIP

⭐ v1.3.6 — Tự nén ZIP và tải về project / module, round-trip với chức năng upload hiện có.

12.1. Thao tác

Đối tượng Cách
Project Vào tab Projects → click nút ⬇ cạnh tên project → tải <name>.zip
Module Vào tab Modules → click nút ⬇ cạnh tên module → tải <name>.zip

Nút ⬇ nhỏ, tự disable khi đang export; có stopPropagation để không trigger long-press delete trên mobile.

12.2. Nội dung ZIP

Project ZIP (base dir = <name>/):

· ✅ Bao gồm: toàn bộ file trong project
· ❌ Bỏ qua: .project.json (metadata nội bộ), __pycache__/, *.pyc, .git/, .svn/

Module ZIP (base dir = <name>/):

· ✅ Bao gồm: main.py, init.txt, web/*, data/*, và bất kỳ file nào khác
· ❌ Bỏ qua: __pycache__/, *.pyc, .git/, .svn/

Cả 2 đều dùng zipfile.ZIP_DEFLATED (compress).

12.3. Round-trip

```
Export ZIP  →  Uninstall/Delete  →  Upload lại qua 📤  →  Restored 100%
```

· Project ZIP: upload qua tab Projects → 📤 → create_from_zip() strip root folder tự động
· Module ZIP: upload qua tab Modules → 📤 → install_from_zip() strip root folder tự động

→ Đây là cách backup / clone / migrate project & module giữa các instance.

12.4. API response shape

```jsonc
POST /api/projects/export  { "name": "demo" }
POST /api/modules/export   { "name": "demo_module" }

// Response (200):
{
  "ok": true,
  "filename": "demo.zip",
  "size": 12345,
  "files": 7,
  "zip_base64": "UEsDBBQAAAAIA..."   // base64 của ZIP
}
```

Frontend (App._downloadBase64):

```javascript
_downloadBase64(base64, filename) {
  const bin = atob(base64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const blob = new Blob([bytes], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
```

12.5. Bảo mật

· Tên project/module được validate qua _safe_path() / path prefix check → chống ../escape
· Walk bằng os.walk() + os.path.relpath() → arcname luôn nằm dưới <name>/
· Symlinks: follow mặc định của os.walk (không có followlinks=True) — symlink tới ngoài base_dir sẽ không được include nếu trỏ ra ngoài trên một số OS; nếu cần strict, thêm os.path.islink(full) check
· Không có giới hạn size khi export (chỉ giới hạn khi upload: file > 5MB bị từ chối khi đọc)

12.6. Cấu hình

Không cần cấu hình gì — hoạt động ngay sau khi update. Không thêm field vào config.json.

12.7. Test nhanh

```bash
# Export project → lưu vào /tmp/
curl -X POST http://localhost:8765/api/projects/export \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo"}' \
  | python3 -c "import sys,json,base64; d=json.load(sys.stdin); open('/tmp/demo.zip','wb').write(base64.b64decode(d['zip_base64'])); print('files:', d['files'], 'size:', d['size'])"

# Verify ZIP hợp lệ
unzip -l /tmp/demo.zip

# Export module
curl -X POST http://localhost:8765/api/modules/export \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo_module"}' \
  | python3 -c "import sys,json,base64; d=json.load(sys.stdin); open('/tmp/demo_module.zip','wb').write(base64.b64decode(d['zip_base64'])); print('files:', d['files'])"

unzip -l /tmp/demo_module.zip
```

---

13. Dev workflow

Thêm route core (protected)

Trong core/engine.py → _init_core():

```python
A = self.router.add_core          # ← protected route
A("GET", "/api/my_endpoint", self._api_my_endpoint)
```

⚠️ LUÔN dùng add_core — nếu dùng router.add, module có thể override.

Add overlay cho module

```bash
# File nhỏ
touch modules/my_mod/web/overlay.css
touch modules/my_mod/web/overlay.js

# File lớn (> 50KB bundle)
touch modules/my_mod/data/overlay.css
touch modules/my_mod/data/overlay.js
```

Reload module → overlay tự inject. Test safe mode: /?safe=1.

Trigger diagnostics từ module

```python
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

Save file → nếu settings.diagnostics.auto_run_on_save=true → broadcast qua WS → hiện trong Problems panel + inline markers.

Intercept errors

```python
def on_http_error(self, ctx):
    if "/api/projects/" not in ctx.get("path", ""):
        return None
    return {
        "ok": False,
        "error": f"Intercepted: {ctx['error']}",
        "custom": True
    }
```

Override file (dev only)

Đặt .py trong overrides/ → được exec() sau _init_core, trước khi load modules.

```python
# overrides/my_patch.py
def patch(engine, sandbox, config, router):
    print("[patch] applying custom route")
    router.add_core("GET", "/api/dev/debug", lambda req: {"debug": True})
```

Thêm nút toolbar mới

1. Thêm <button class="icon-btn" id="myBtn">…</button> vào .top-actions trong index.html
2. Wire trong app.js → _bind():

```javascript
const myBtn = document.getElementById("myBtn");
if (myBtn) myBtn.onclick = () => { /* action */ };
```

3. Nếu cần disable/enable động → style .icon-btn:disabled { opacity: 0.4 } đã có sẵn trong style.css

Add export cho resource mới (pattern v1.3.6)

Nếu bạn thêm manager mới (vd templates/) và muốn export ZIP tương tự:

Backend:

```python
# my_manager.py
import io, zipfile, os

def export_zip(self, name):
    base = self._safe_path(name)
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in ("__pycache__",))
            for fname in sorted(files):
                if fname.endswith(".pyc"):
                    continue
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, base)
                zf.write(full, arcname=(name + "/" + rel).replace("\\", "/"))
                count += 1
    return {"data": buf.getvalue(), "files": count, "size": buf.tell()}
```

Engine:

```python
A("POST", "/api/templates/export", self._api_templates_export)

def _api_templates_export(self, req):
    import base64
    result = self.templates.export_zip(req.get("name"))
    return {
        "ok": True,
        "filename": f"{req.get('name')}.zip",
        "size": result["size"],
        "files": result["files"],
        "zip_base64": base64.b64encode(result["data"]).decode("ascii"),
    }
```

Frontend:

```javascript
// api.js
exportTemplate: (name) => API.request("/api/templates/export", "POST", { name }),

// app.js — dùng lại helper
await App.exportTemplate(name);   // tương tự exportProject
```

---

14. Testing cheat-sheet

```bash
# Backend up?
curl http://localhost:8765/api/status

# Module list
curl http://localhost:8765/api/modules

# Module ping
curl http://localhost:8765/api/demo_module/ping

# Create project
curl -X POST http://localhost:8765/api/projects/create \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo","language":"python"}'

# Run file
curl -X POST http://localhost:8765/api/projects/run \
  -H 'Content-Type: application/json' \
  -d '{"project":"demo","path":"main.py"}'

# Stop (SIGTERM → SIGKILL sau 2s)
curl -X POST http://localhost:8765/api/projects/run/stop \
  -H 'Content-Type: application/json' -d '{"force":false}'

# Diagnostics
curl -X POST http://localhost:8765/api/diagnostics/check \
  -H 'Content-Type: application/json' \
  -d '{"project":"demo","path":"main.py"}'

# Settings
curl http://localhost:8765/api/settings
curl -X POST http://localhost:8765/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"editor":{"font_size":16}}'
# → Kiểm tra browser console: WS message `settings_changed` phải tới

# Overlays (xem data/ vs web/)
curl http://localhost:8765/api/overlay

# Module static
curl http://localhost:8765/module/demo_module/
curl http://localhost:8765/module/my_mod/_data_/overlay.css   # v1.3.1

# Terminal (v1.3.2)
curl http://localhost:8765/api/terminal/sessions

# ⭐ v1.3.6: Export project / module
curl -X POST http://localhost:8765/api/projects/export \
  -H 'Content-Type: application/json' -d '{"name":"demo"}' \
  | head -c 200
curl -X POST http://localhost:8765/api/modules/export \
  -H 'Content-Type: application/json' -d '{"name":"demo_module"}' \
  | head -c 200
```

Test Undo/Redo (⭐ v1.3.3)

Thủ công trong browser:

1. Mở file A → gõ vài dòng → mở file B → gõ vài dòng
2. Quay lại tab A → Ctrl+Z → chỉ undo được những gì đã sửa ở A
3. Ctrl+Z liên tục đến khi hết → nút ↶ tự disable
4. Ctrl+Y → redo từng bước → nút ↷ tự disable khi hết
5. Sửa 1 dòng → Ctrl+S → dấu ● biến mất → Ctrl+Z → dấu ● xuất hiện lại
6. Undo tiếp về trước bước save → dấu ● vẫn còn (vì content khác last saved)
7. Redo về đúng trạng thái đã lưu → dấu ● tự biến mất

Test Export/Import ZIP (⭐ v1.3.6)

1. Tạo project "demo" với vài file (vd main.py, src/utils.py)
2. Tab Projects → click ⬇ cạnh "demo" → browser tải demo.zip
3. Verify: unzip -l ~/Downloads/demo.zip → phải thấy demo/main.py, demo/src/utils.py
4. Xoá project "demo" (long-press hoặc chuột phải → Delete)
5. Tab Projects → 📤 → chọn demo.zip vừa tải → nhập tên "demo"
6. Verify: project restored, mở src/utils.py → nội dung y nguyên
7. Lặp lại tương tự với module trong tab Modules

Round-trip integrity:

· Mở rộng: sau khi re-import, chạy md5sum so sánh file gốc vs file import → phải giống
· Nếu module có data/settings.json → export → import → settings vẫn còn
· Nếu module có web/overlay.css → export → import → overlay vẫn inject (F12 → Network → thấy /module/.../overlay.css)

Reset khi kẹt

```bash
pkill -f "python main.py"
fuser -k 8765/tcp
rm core/data/.run_pids.json
rm core/data/settings.json
# Diagnostics cache: restart server
```

---

15. Troubleshooting

Vấn đề Nguyên nhân Fix
Undo/redo không hoạt động Focus trong input/modal Click vào editor rồi thử lại — hotkey chỉ fire khi focus ngoài editor hoặc trong editor
Undo mất history khi đổi tab Code cũ dùng setValue ✅ v1.3.3 đã fix bằng swapDoc — hard-reload để lấy code mới
Dirty ● không biến mất sau undo So sánh string thất bại (line ending?) Kiểm tra file có CRLF không; nếu có, xem xét normalize khi save
Android: Backspace không xoá dòng cuối CM5 + contenteditable không merge dòng ở soft keyboard ✅ v1.3.2 đã fix (_fixAndroidLineMerge) — nếu vẫn lỗi, hard-reload
Settings lưu nhưng không áp dụng Thiếu listener settings_changed ✅ v1.3.2 đã fix — kiểm tra DevTools console có WS settings_changed
Theme chọn "light"/"dark" không đổi Không phải theme CM5 hợp lệ ✅ v1.3.2 đổi sang dracula/default/material/monokai/solarized/eclipse
Auto-wrap bật dù đã tắt Settings cũ còn line_wrap: true Vào Settings → Editor → bỏ tick "Line wrap" (apply ngay)
Overlay CSS không load File đặt sai chỗ data/ hoặc web/, tên overlay.css / override.css
Overlay JS lỗi "not found" init.txt khai overlay field ⚠️ Không khai nữa — loader tự detect
Module route bị reject Trùng core route Đổi path, đừng override /api/status, /api/projects/*
get_settings() trả về {} Chưa có settings_schema Khai báo schema trong init.txt
Fold không hoạt động trên JS Thiếu addon Check index.html có load brace-fold.min.js
Process treo khi disconnect auto_stop_on_disconnect=false Đặt true trong config.json
Terminal không mở được Trình duyệt chặn WS / chưa load xterm.js Kiểm tra console: [Terminal] xterm.js not loaded? CDN bị chặn?
Terminal mở nhưng không có prompt WS chưa kết nối Kiểm tra connDot xanh; nút ⟳ restart session
Terminal bị "Terminal limit reached" Đã đủ max_sessions Tăng terminal.max_sessions trong config.json
Terminal không auto-close khi tab đóng Session gắn với WS, không phải tab Đóng bằng nút 🗑, hoặc refresh trang (WS disconnect → kill session)
Export nút ⬇ không hiện Code frontend cũ (chưa update app.js/explorer.js) Hard-reload (Ctrl+Shift+R) để lấy bundle mới — v1.3.6 mới có nút
Export trả 404 Backend chưa update (không có route /api/*/export) Restart server — route khai báo trong _init_core() v1.3.6
ZIP export rỗng (0 files) Project/module thực sự rỗng, hoặc chỉ có __pycache__/.pyc Tạo ít nhất 1 file user-facing (vd README.md) trước khi export
Import ZIP export bị "already installed" Module/project cùng tên đã tồn tại Uninstall/delete trước, hoặc đổi tên khi upload
ZIP tải về bị hỏng / không mở được Base64 bị truncate (network, proxy) Kiểm tra res.files > 0, download lại; nếu lặp lại → xem Network tab kích thước response
Export module lớn chậm ZIP_DEFLATED compress CPU-bound với file lớn (node_modules, .venv) Bình thường; hoặc exclude những thư mục đó khỏi export bằng cách sửa export_module_zip → thêm dirs[:] = [d for d in dirs if d not in ("node_modules", ".venv")]

---

16. Known issues / Roadmap

🔴 Cần test kỹ

· ☐ Error dispatch chain: on_any_error → on_http_error (pass-through + handle)
· ☐ Settings modal: schema validation, on_settings_changed callback
· ☐ Overlay: data/ bundle load, safe mode ?safe=1, per-module toggle
· ☐ Diagnostics: auto-run on save, inline markers, jump-to-line
· ☐ Core route protection: module cố override /api/status phải bị reject
· ☐ Folding: Python nested functions, JS template strings
· ☐ Android: Samsung Internet, Firefox mobile (fix backspace v1.3.2)
· ☐ Terminal: Windows pipes (không có PTY), copy/paste trên mobile, ZMODEM
· ☐ Undo/Redo: selection state sau swapDoc, fold state per-tab, IME composition
· ☐ Export: symlink handling, project lớn (> 100MB), concurrent export

🟢 Nice to have

· ☐ Import from Git URL
· ☐ Multi-user auth
· ☐ Resource limits (CPU/mem per process)
· ☐ Overlay hot-reload khi save file trong data/
· ☐ Per-file undo history persistence (sessionStorage, giữ khi F5)
· ☐ Per-file fold state persistence (localStorage)
· ☐ Terminal scrollback persistence
· ☐ Terminal split panes
· ☐ Export: chọn subset file (checkbox tree) thay vì export toàn bộ
· ☐ Export: .tar.gz option
· ☐ Export: server-side save to disk (không cần base64 round-trip)

Roadmap

v1.3.x — polish

· Test suite (pytest cho core, playwright cho frontend)
· Docs: error dispatch chain + 3 module examples ✅
· Diagnostics: severity filter trong UI
· Undo/Redo: test edge cases, fold state per-tab ✅
· Export: round-trip test ✅

v1.4.0 — developer experience

· Hot reload module (watch modules//main.py + data/.css|js)
· Project export ✅ (v1.3.6)
· Preview HTML project (/preview/<project>/)
· Terminal: multiple tabs
· Undo history persistence qua sessionStorage
· Multi-cursor editing (giống VS Code Alt+Click)
· Export: stream download (không buffer toàn bộ vào RAM)

v2.0.0 — scale

· Multi-user + auth
· Collaborative editing (WS) — conflict resolution + operation transform
· Docker isolation per project
· Resource limits
· Terminal sandbox (Docker exec)
· Cloud sync / Git integration

---

17. Legal

Educational / personal use. Không cài module từ nguồn không tin cậy — module có toàn quyền Python. Không chạy server bằng sudo. Terminal chạy với quyền user server — cẩn trọng khi expose ra mạng LAN/WAN.

```

---

## 📌 Tóm tắt những gì đã đổi trong README v1.3.6

| Mục | Nội dung mới |
|---|---|
| **Header** | Version `1.3.6`, thêm "export/import ZIP" |
| **§1 Status** | Thêm 3 dòng: Module watcher, System controls, **Export Project/Module ZIP** |
| **§3 Cấu trúc** | Note `api.js`, `explorer.js`, `app.js` v1.3.6; note `loader.py` có export |
| **§4 Architecture** | Thêm **luồng Export ZIP** + **luồng Import ZIP** |
| **§6 Bước 6** | Chia 2 cách package: **Export từ UI** ⭐ v1.3.6 (cách A) + zip thủ công (cách B) |
| **§7 API Reference** | Thêm 2 endpoint: `/api/projects/export`, `/api/modules/export`; thêm subsection **System** (v1.3.5) |
| **§8 WS Protocol** | Thêm `modules_changed`, `system_restarting`, `system_shutdown` |
| **§12 Export / Import ZIP** ⭐ | **Section hoàn toàn mới** — thao tác, nội dung ZIP, round-trip, response shape, bảo mật, test nhanh |
| **§13 Dev workflow** | Đổi số từ §12; thêm pattern mẫu "Add export cho resource mới" |
| **§14 Testing** | Đổi số từ §13; thêm curl export + **test cases round-trip** (7 bước) |
| **§15 Troubleshooting** | Đổi số từ §14; thêm 6 dòng về export (404, empty ZIP, already installed, corrupted ZIP, slow export) |
| **§16 Roadmap** | Đổi số từ §15; thêm nice-to-have export (subset, tar.gz, stream); note `Project export` → ✅ v1.3.6 |
| **§17 Legal** | Đổi số từ §16 (nội dung giữ nguyên) |

**Điểm nhấn quan trọng:**
- ⭐ **Section §12 là trung tâm** — mô tả đầy đủ API, round-trip, bảo mật, test
- **Round-trip hoàn hảo**: ZIP export → upload lại → restored 100% (cả project lẫn module)
- **Pattern tái sử dụng** trong §13 → dễ mở rộng export cho resource mới (templates, snippets…)