📘 README.md — ACDV-Teams Coder v1.4.0

```markdown
# ACDV-Teams Coder

Local web IDE — Python stdlib backend, CodeMirror frontend, module extension system, terminal over WebSocket, per-tab undo/redo, export/import ZIP, **module storage với quota 512MB**.

**Version:** `1.4.0` · **Platform:** Python 3.8+ · **Deps:** none (stdlib only) · **Terminal:** xterm.js (CDN)

> 📖 **Dev guide:** Đọc mục [§5 Module Contract](#5-module-contract) và [§6 Tạo module từ A→Z](#6-tạo-module-từ-az) trước khi viết module mới. Đặc biệt chú ý [§5.7 Module Storage](#57-module-storage-) — API mới cho phép module upload/download file với quota riêng.

---

## Mục lục

1. [Status](#1-status)
2. [Quick start](#2-quick-start)
3. [Cấu trúc thư mục](#3-cấu-trúc-thư-mục)
4. [Architecture](#4-architecture)
5. [Module Contract](#5-module-contract) ⭐
   - [5.1 init.txt](#51-inittxt--metadata-json)
   - [5.2 main.py](#52-mainpy--class-module)
   - [5.3 Diagnostic shape](#53-diagnostic-shape)
   - [5.4 Error interceptor](#54-error-interceptor-return-shape)
   - [5.5 Overlay CSS/JS](#55-overlay-cssjs--web-vs-data)
   - [5.6 Sandbox](#56-sandbox)
   - [5.7 Module Storage](#57-module-storage-) 🆕
6. [Tạo module từ A→Z](#6-tạo-module-từ-az) ⭐
7. [API Reference](#7-api-reference)
8. [WebSocket Protocol](#8-websocket-protocol)
9. [Frontend / Editor](#9-frontend--editor)
10. [Undo / Redo](#10-undo--redo)
11. [Terminal](#11-terminal)
12. [Export / Import ZIP](#12-export--import-zip)
13. [Module Storage (v1.4.0)](#13-module-storage-v140-) 🆕
14. [Loading & Restart (v1.4.0)](#14-loading--restart-v140-) 🆕
15. [Dev workflow](#15-dev-workflow)
16. [Testing cheat-sheet](#16-testing-cheat-sheet)
17. [Troubleshooting](#17-troubleshooting)
18. [Known issues / Roadmap](#18-known-issues--roadmap)
19. [Legal](#19-legal)

---

## 1. Status

| Layer | State |
|---|---|
| Core engine + router + server | ✅ Ổn định |
| Project manager + ZIP upload/export | ✅ Ổn định |
| Process runner (`.py`/`.js`/`.sh`) | ✅ Ổn định (process-group kill) |
| Module loader + ZIP install/export | ✅ Ổn định |
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
| Undo / Redo per-tab | ✅ v1.3.3 — giống VS Code, history bảo toàn khi đổi tab |
| Dirty flag chính xác | ✅ v1.3.3 — undo về trạng thái đã lưu → dấu ● biến mất |
| Editor line wrap | ✅ v1.3.1 — mặc định **tắt**, đọc từ settings |
| Terminal (xterm.js + PTY) | ✅ v1.3.2 — Ctrl+`, gắn với WS client |
| Module watcher (auto-detect) | ✅ v1.3.5 — tự load/unload module khi filesystem thay đổi |
| System controls (restart/shutdown) | ✅ v1.3.5 — `/api/system/*` |
| Export Project / Module ZIP | ✅ v1.3.6 — download ZIP round-trip, tương thích upload |
| **Module Storage (quota 512MB)** | ✅ **v1.4.0** — upload chunk, download, export ZIP, cảnh báo quota |
| **Loading overlay** | ✅ **v1.4.0** — hiện khi init / restart |
| **Restart refresh UI** | ✅ **v1.4.0** — tự reload trang sau restart |
| **Storage warning toast** | ✅ **v1.4.0** — WS broadcast khi ≥ 90% / ≥ 98% |
| Demo module | ✅ `modules/demo_module/` |
| Code reminder module | ✅ `modules/code_reminder/` |

---

## 2. Quick start

```bash
cd /path/to/acdv-coder
python3 main.py
```

Mở: http://localhost:8765 (hoặc https nếu SSL bật)

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
├── config.json                # host/port/version/terminal/storage quota
├── README.md
│
├── core/                      # Backend (Python stdlib)
│   ├── engine.py              # CoreEngine: boot, routes, error dispatch, storage API
│   ├── server.py              # HTTP + WS server (raw socket, TLS support)
│   ├── router.py              # (method, path) → handler, core-protected
│   ├── loader.py              # ModuleBase + ModuleLoader (ZIP install + export)
│   ├── sandbox.py             # Per-module fs jail (data/)
│   ├── module_storage.py      # ⭐ v1.4.0: ModuleStorage (quota 512MB, chunked upload)
│   ├── project_manager.py     # Project CRUD + file ops + ZIP upload/export
│   ├── runner.py              # ProcessRunner (subprocess + kill group)
│   ├── settings.py            # Global + per-module settings
│   ├── diagnostics.py         # DiagnosticsManager
│   ├── terminal.py            # TerminalManager (PTY + WS)
│   └── data/                  # Auto-created: logs/, settings.json, .run_pids.json, certs/
│
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js             # REST client (bao gồm 7 storage methods)
│       ├── ws.js              # WebSocket client
│       ├── explorer.js        # Project list + file tree
│       ├── editor.js          # Per-tab Doc + undo/redo + dirty chính xác
│       ├── app.js             # Main app + loading overlay + storage warning toast
│       ├── diagnostics.js     # Problems panel + inline markers
│       ├── settings.js        # Settings UI + About tab
│       ├── terminal.js        # xterm.js wrapper
│       ├── overlay.js         # Overlay loader
│       └── storage_ui.js      # ⭐ v1.4.0: Module Storage UI (upload chunked)
│
├── modules/
│   ├── demo_module/           # Template đầy đủ contract + storage example
│   ├── code_reminder/         # Ví dụ: diagnostics module thực tế
│   └── <your_module>/
│       ├── init.txt           # Metadata (JSON)
│       ├── main.py            # Class Module
│       ├── data/              # Sandbox + overlay file lớn + settings.json
│       │   ├── overlay.css    # ưu tiên cao nhất (file lớn)
│       │   ├── overlay.js
│       │   └── settings.json  # Auto-created per-module settings
│       ├── storage/           # ⭐ v1.4.0: Storage riêng (quota 512MB)
│       │   ├── files/         # File upload (do user upload)
│       │   ├── .storage.json  # Metadata (auto)
│       │   └── .tmp_uploads/  # Chunk tạm (auto cleanup)
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
│  storage_ui.js → module storage modal                │
│  overlay.js injects module CSS/JS                    │
└──────────────────┬───────────────────────────────────┘
                   │ HTTP + WS (raw socket, no framework)
┌──────────────────▼───────────────────────────────────┐
│  CoreEngine (core/engine.py)                         │
│  ├─ Router       (core-protected vs module routes)   │
│  ├─ HttpWsServer (raw socket, WS frames, TLS)        │
│  ├─ ModuleLoader (scan modules/, ZIP install/export) │
│  ├─ Sandbox      (per-module fs jail data/)          │
│  ├─ ModuleStorage⭐ (per-module quota 512MB)         │
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

GET /module/<name>/_data_/overlay.css         (file lớn)
  → loader.py detect: data/overlay.css
  → server strip `_data_/` prefix
  → serve data/overlay.css

GET /module/<name>/_storage_/files/xxx.bin    ⭐ v1.4.0
  → server strip `_storage_/` prefix
  → serve storage/files/xxx.bin
```

Luồng Undo/Redo

```
Mỗi tab giữ một CodeMirror.Doc riêng (tab.doc)
  ↓
Khi activate tab
  → cm.swapDoc(tab.doc)        ← KHÔNG dùng setValue
  → toàn bộ undo history của tab được bảo toàn
  ↓
Ctrl+Z (focus trong editor) → CodeMirror keymap tự xử lý
Ctrl+Z (focus ngoài editor) → App._isEditableTarget() = false → App.editor.undo()
  ↓
Dirty flag = (cm.getValue() !== tab.content)
  → undo về trạng thái đã lưu → ● tự biến mất
```

Luồng Terminal

```
browser (xterm.js)
  → ws.send({type:"terminal_open", id, cols, rows, cwd})
    → TerminalManager.open(id, ws, cols, rows, cwd_hint)
    → pty.openpty() + Popen(shell, start_new_session=True)
    → reader thread đọc master_fd → ws.send terminal_output

keyboard input
  → term.onData → ws.send terminal_input → TerminalManager.write(id, data)

WS disconnect → close_by_ws(ws) → kill toàn bộ session của client đó
```

Luồng Module Storage (⭐ v1.4.0)

```
UI click 💾 (module list)
  → StorageUI.open(name)
  → API.storageUsage(name) + API.storageList(name)
  → Render usage bar + file list

Upload file (chunked 4MB)
  → FileReader.slice(start, end) → blob
  → _blobToBase64(blob)
  → API.storageUploadChunk({name, path, chunk_index, total_chunks, chunk_b64, total_size, upload_id})
  → ModuleStorage.upload_chunk()
    ├─ chunk 0: check quota (raise QuotaExceeded nếu > 98%)
    ├─ ghi vào .tmp_uploads/<upload_id>/chunk_NNNNN
    └─ chunk cuối: assemble → storage/files/<path> → cleanup tmp

Download file
  → API.storageDownload(name, path)
  → ModuleStorage.read_file() (max 50MB)
  → base64 → browser tải về

Export ZIP
  → API.storageExportZip(name)
  → ModuleStorage.export_zip() → walk storage/files/ → zipfile
  → base64 → download

Quota warning
  → sau upload completed: check_and_warn(name)
  → nếu status != 'ok': broadcast {type:"storage_warning", module, usage, severity}
  → app.js: hiển thị toast đỏ/vàng góc phải trên
```

Luồng Loading & Restart (⭐ v1.4.0)

```
App.init()
  → _showLoading("Khởi tạo ứng dụng…")
  → ... tải projects, README, modules ...
  → _hideLoading() (sau 200ms)

User click 🔄 Restart
  → POST /api/system/restart
  → engine._restart_pending = True
  → broadcast {type:"system_restarting"}
  → app.js: _showRestartOverlay()
  → engine os.execv(main.py) → khởi động lại process
  → boot() hoàn tất → broadcast {type:"system_restarted", boot_id}
  → app.js: location.reload() (sau 800ms)
  → UI mới hoàn chỉnh
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

  "module_storage_quota": 134217728,

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

Field Bắt buộc Ý nghĩa
name ✅ Tên module (unique, không có /, ..)
version ✅ Semver
description — Mô tả hiển thị trong settings UI
critical — Nếu load fail → engine exit (mặc định false)
module_storage_quota — Override quota (bytes). Mặc định dùng config.module_storage_quota (512MB)
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

5.7. Module Storage ⭐

Mới v1.4.0 — mỗi module có storage riêng biệt với quota 512MB (config được).

Vị trí

```
modules/<name>/storage/
├── files/              ← file upload (accessible)
├── .storage.json       ← metadata (auto)
└── .tmp_uploads/       ← chunk tạm (auto cleanup)
```

Đặc điểm

· Tách biệt hoàn toàn với data/ (sandbox) — dùng cho file user upload, không phải cache nội bộ.
· Quota 512MB mặc định (config module_storage_quota).
· Override per-module: khai báo module_storage_quota trong init.txt.
· Cảnh báo tự động: ≥ 90% (warn), ≥ 98% (block upload + broadcast WS).
· Upload chunked: file lớn chia 4MB/chunk, hỗ trợ tới 200MB/file.
· Export ZIP: tải toàn bộ storage 1 click.
· Path traversal safe: chống ../ escape.

Python API (từ module)

```python
def on_load(self):
    # ─── Quota info ────────────────────────────────────
    usage = self.engine.storage.usage(self.name)
    # → {"used": 12345, "quota": 536870912, "percent": 0.0023,
    #    "status": "ok"|"warn"|"full", "free": 536858567}

    # ─── Ghi/đọc file ──────────────────────────────────
    self.engine.storage.write_file(self.name, "cache/data.json", '{"x":1}')
    data = self.engine.storage.read_file(self.name, "cache/data.json")

    # ─── List ───────────────────────────────────────────
    files = self.engine.storage.list_files(self.name, "")
    # → [{"name":"x.txt","path":"x.txt","type":"file","size":123,"mtime":...}, ...]

    # ─── Delete ─────────────────────────────────────────
    self.engine.storage.delete_file(self.name, "cache/data.json")

    # ─── Clear all ──────────────────────────────────────
    self.engine.storage.clear_all(self.name)

    # ─── Export ZIP ─────────────────────────────────────
    result = self.engine.storage.export_zip(self.name)
    # → {"data": b"PK...", "files": 5, "size": 12345}
```

Quota exceptions

```python
from core.module_storage import QuotaExceeded, StorageViolation

try:
    self.engine.storage.write_file(self.name, "big.bin", data)
except QuotaExceeded as e:
    # Storage gần đầy — cần giải phóng
    return {"ok": False, "error": str(e), "quota_exceeded": True}
except StorageViolation as e:
    # Path escape
    return {"ok": False, "error": str(e)}
```

HTTP API (từ frontend / external)

Xem §7 API Reference → Storage endpoints.

UI có sẵn

· Nút 💾 cạnh mỗi module trong tab Modules → mở Storage modal.
· Mini storage bar (4px) cạnh tên module hiển thị % đã dùng.
· Upload chunked + progress bar.
· Download / delete từng file.
· Export ZIP / Clear all.

---

6. Tạo module từ A→Z

Bước 1 — Khung thư mục

```bash
mkdir -p modules/my_mod/web modules/my_mod/data modules/my_mod/storage
cd modules/my_mod
```

Bước 2 — init.txt

```json
{
  "name": "my_mod",
  "version": "1.0.0",
  "description": "Module ví dụ",
  "critical": false,
  "module_storage_quota": 134217728,

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
        # ensure storage ready
        self.engine.storage.storage_dir(self.name)

    def ping(self, req):
        usage = self.engine.storage.usage(self.name)
        return { "ok": True, "pong": True, "storage": usage }

    def on_button_show_info(self, params):
        try:
            self.engine.storage.write_file(
                self.name, "cache/last_check.txt",
                f"checked at {__import__('time').time()}"
            )
        except Exception as e:
            return { "ok": False, "error": str(e) }

        return {
            "ok": True,
            "settings": self.get_settings(),
            "storage": self.engine.storage.usage(self.name),
        }

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

# Verify storage usage
curl -X POST http://localhost:8765/api/modules/storage/usage \
  -H 'Content-Type: application/json' -d '{"name":"my_mod"}'
```

Xem UI: tab Modules → nút 💾 (storage) / Info (module action) → tab Settings → Modules (render settings).

Bước 6 — Package thành ZIP

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
/api/status GET — {status, version, boot_id, uptime_modules, system_controls}
/api/boot GET — {ok, boot_id, version, modules, storage_quota} ⭐ v1.4.0
/api/modules GET — {<name>: metadata} (kèm storage_usage)
/api/modules/install POST {zip_base64} {ok, module}
/api/modules/uninstall POST {name} {ok} (xoá cả storage)
/api/modules/reload POST {name} {ok}
/api/modules/export POST {name} {ok, filename, size, files, zip_base64}
/api/terminal/sessions GET — {ok, sessions: [{id, pid, cwd, cols, rows}]}

Module Storage ⭐ v1.4.0

Endpoint Method Body Response
/api/modules/storage/usage POST {name} {ok, usage: {used, quota, percent, status, free}}
/api/modules/storage/list POST {name, sub_dir?} {ok, files: [...], usage}
/api/modules/storage/upload_chunk POST {name, path, chunk_index, total_chunks, chunk_b64, total_size, upload_id} {ok, completed, path?, size?, usage?}
/api/modules/storage/download POST {name, path} {ok, filename, size, content_b64}
/api/modules/storage/delete POST {name, path} {ok, usage}
/api/modules/storage/clear POST {name} {ok, usage}
/api/modules/storage/export_zip POST {name, sub_dir?} {ok, filename, size, files, zip_base64}

Projects

Endpoint Method Body
/api/projects GET —
/api/projects/create POST {name, language}
/api/projects/upload POST {name, zip_base64}
/api/projects/delete POST {name}
/api/projects/export POST {name} → {ok, filename, size, files, zip_base64}
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
/api/settings POST {<patch>} → broadcast settings_changed
/api/settings/modules POST {}
/api/settings/module/get POST {name}
/api/settings/module/set POST {name, values}
/api/diagnostics/check POST {project, path}
/api/diagnostics/file POST {project, path}
/api/diagnostics/all GET —
/api/diagnostics/clear POST {project?, path?}
/api/overlay GET —
/api/readme GET —

System

Endpoint Method Body
/api/system/restart POST {} → broadcast system_restarting + system_restarted
/api/system/shutdown POST {} → broadcast system_shutdown

Gated bởi config.json → enable_system_controls (mặc định true).

Module static

```
GET /module/<name>/                    → web/index.html
GET /module/<name>/overlay.css         → web/overlay.css
GET /module/<name>/overlay.js          → web/overlay.js
GET /module/<name>/*                   → web/*
GET /module/<name>/_data_/*            → data/*
GET /module/<name>/_storage_/*         → storage/files/*    ⭐ v1.4.0
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

// terminal
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

// Settings (broadcast tới MỌI client để hot-apply)
{ "type": "settings_changed",        "settings": {...} }
{ "type": "module_settings_changed", "module", "values": {...} }

// Module auto-detect
{ "type": "modules_changed", "action": "added|removed|reloaded", "module": "..." }

// System controls
{ "type": "system_restarting" }
{ "type": "system_restarted", "boot_id": "boot_1234567890", "version": "1.4.0" }  ⭐ v1.4.0
{ "type": "system_shutdown" }

// ⭐ v1.4.0: Storage warning
{ "type": "storage_warning",
  "module": "my_mod",
  "usage": {"used": 480000000, "quota": 536870912, "percent": 89.4, "status": "warn"},
  "message": "⚠️ Module 'my_mod' storage đã dùng 89.4% ...",
  "severity": "warning" | "error" }

// Terminal
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

9.3. Settings hot apply

1. Server broadcast settings_changed qua WS mỗi lần POST /api/settings thành công
2. app.js lắng nghe settings_changed → editor.onSettingsChanged(newSettings)
3. settings.js chủ động gọi editor.onSettingsChanged() ngay sau saveSettings() (idempotent với WS handler)
4. editor.onSettingsChanged() → applySettings() → cập nhật font_size, tab_size, line_wrap, theme

Theme options hợp lệ (CM5): dracula, default, material, monokai, solarized, eclipse.

9.4. Settings structure

```jsonc
{
  "theme": "dracula",
  "editor": {
    "font_size": 14,
    "tab_size": 4,
    "line_wrap": false,
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

9.5. Overlay loader

· Fetch /api/overlay → inject <link> + <script> với ?t=<timestamp>
· Skip nếu ?safe=1 trên URL hoặc settings.overlays.safe_mode = true
· Hiển thị banner "🎨 N overlays active" — dismiss hoặc chuyển safe mode

9.6. Loading overlay (⭐ v1.4.0)

· Hiện khi App.init() bắt đầu (spinner + text "Khởi tạo ứng dụng…")
· Text cập nhật theo tiến trình: "Tải projects…", "Tải README…", "Tải modules…"
· Tự ẩn sau khi mọi thứ sẵn sàng (~200ms sau load xong)
· Khi restart: overlay riêng (restartOverlay) với spinner 🔄

9.7. Storage UI (⭐ v1.4.0)

· Modal #storageModal — mở từ nút 💾 trong module list.
· Usage bar: xanh (< 90%), vàng (≥ 90%), đỏ (≥ 98%).
· Upload chunked: 4MB/chunk, progress bar realtime, hỗ trợ tới 200MB/file.
· File list: icon 📄/📁, name, size, actions (⬇ download / 🗑 delete).
· Export ZIP: tải toàn bộ storage.
· Clear all: xoá tất cả file (confirm).
· Mini bar (4px) cạnh tên module trong list — hiển thị % đã dùng.

---

10. Undo / Redo

Hoàn tác / làm lại giống VS Code, per-tab và bảo toàn history khi đổi tab.

10.1. Thao tác

Thao tác Cách
Undo Ctrl+Z / Cmd+Z (focus trong editor hoặc ngoài)
Redo Ctrl+Y hoặc Ctrl+Shift+Z / Cmd+Shift+Z
Undo (mobile) Nút ↶ trên toolbar
Redo (mobile) Nút ↷ trên toolbar
Nút disable Tự disable khi hết history

10.2. Cơ chế

Per-tab history — mỗi tab giữ một CodeMirror.Doc riêng:

```javascript
// Khi mở tab mới
const doc = CodeMirror.Doc(content, mode);
tab.doc = doc;

// Khi chuyển tab
cm.swapDoc(tab.doc);  // ← KHÔNG dùng setValue + clearHistory
```

Dirty flag chính xác:

```javascript
this.cm.on("change", () => {
  const current = this.cm.getValue();
  const isDirty = current !== tab.content;  // ← so sánh với "last saved"
  if (tab.dirty !== isDirty) { tab.dirty = isDirty; renderTabs(); }
});
```

Global hotkey không double-undo với CM5 keymap.

10.3. API (EditorManager)

```javascript
editor.undo()           // undo 1 bước, cập nhật nút
editor.redo()           // redo 1 bước
editor.canUndo()        // → boolean
editor.canRedo()        // → boolean
```

10.4. Lưu ý

· Save không clear history — undo về trước save → dấu ● xuất hiện lại
· Đóng tab → mất history (giống VS Code)
· KHÔNG dùng cm.setValue() khi chuyển tab — sẽ xoá history

---

11. Terminal

11.1. Yêu cầu

· POSIX: dùng PTY (pty.openpty) → hỗ trợ app interactive (vim, top, htop, less…)
· Windows: fallback pipe (không có PTY, hạn chế app fullscreen)
· Frontend: xterm.js 5.3 + addons fit, web-links (CDN trong index.html)

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
    "shell": null,
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

Tự nén ZIP và tải về project / module, round-trip với chức năng upload hiện có.

12.1. Thao tác

Đối tượng Cách
Project Tab Projects → click nút ⬇ cạnh tên project → tải <name>.zip
Module Tab Modules → click nút ⬇ cạnh tên module → tải <name>.zip

Nút ⬇ nhỏ, tự disable khi đang export; có stopPropagation để không trigger long-press delete trên mobile.

12.2. Nội dung ZIP

Project ZIP (base dir = <name>/):

· ✅ Bao gồm: toàn bộ file trong project
· ❌ Bỏ qua: .project.json, __pycache__/, *.pyc, .git/, .svn/

Module ZIP (base dir = <name>/):

· ✅ Bao gồm: main.py, init.txt, web/*, data/*, storage/*, và bất kỳ file nào khác
· ❌ Bỏ qua: __pycache__/, *.pyc, .git/, .svn/, .tmp_uploads/

Cả 2 đều dùng zipfile.ZIP_DEFLATED (compress).

12.3. Round-trip

```
Export ZIP  →  Uninstall/Delete  →  Upload lại qua 📤  →  Restored 100%
```

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
  "zip_base64": "UEsDBBQAAAAIA..."
}
```

12.5. Bảo mật

· Tên project/module được validate qua _safe_path() / prefix check → chống ../ escape
· Walk bằng os.walk() + os.path.relpath() → arcname luôn nằm dưới <name>/
· Symlinks: follow mặc định của os.walk (không followlinks=True)

---

13. Module Storage (v1.4.0) ⭐

13.1. Tổng quan

Mỗi module có storage riêng — cho phép upload/download file độc lập, quota 512MB (config được).

Tính năng Mô tả
Isolated modules/<name>/storage/ — tách biệt với data/ (sandbox)
Quota 512MB mặc định, override được trong init.txt
Warning ≥ 90% broadcast WS warn, ≥ 98% block upload
Chunked upload File lớn chia 4MB/chunk, progress bar
Export ZIP Tải toàn bộ storage 1 click
Path safe Chống ../ escape, absolute path

13.2. Cấu trúc

```
modules/<name>/storage/
├── files/              ← file upload (accessible)
│   ├── image.png
│   └── cache/data.json
├── .storage.json       ← metadata (auto)
└── .tmp_uploads/       ← chunk tạm (auto cleanup sau assemble)
```

13.3. Config

Global (config.json):

```json
{
  "module_storage_quota": 536870912
}
```

Per-module (init.txt):

```json
{
  "module_storage_quota": 134217728
}
```

134217728 = 128MB, 536870912 = 512MB.

13.4. Ngưỡng cảnh báo

Mức Điều kiện Hành vi
ok < 90% Bình thường
warn ≥ 90% Broadcast WS warning (vàng)
full ≥ 98% Broadcast WS error (đỏ) + block upload

13.5. Python API cho module

```python
# Usage info
usage = self.engine.storage.usage(self.name)
# → {"used": 12345, "quota": 536870912, "percent": 0.0023,
#    "status": "ok"|"warn"|"full", "free": 536858567}

# Write/read
self.engine.storage.write_file(self.name, "cache/x.json", '{"a":1}')
data = self.engine.storage.read_file(self.name, "cache/x.json")

# List files
files = self.engine.storage.list_files(self.name, "cache")

# Delete
self.engine.storage.delete_file(self.name, "cache/x.json")

# Clear all
self.engine.storage.clear_all(self.name)

# Export ZIP
result = self.engine.storage.export_zip(self.name)
# → {"data": b"PK...", "files": 5, "size": 12345}

# Raise
from core.module_storage import QuotaExceeded, StorageViolation
```

13.6. HTTP API

Xem §7 → Storage endpoints.

13.7. Serve file trực tiếp

File trong storage có thể serve qua URL tĩnh (với điều kiện file nằm trong storage/files/):

```
GET /module/<name>/_storage_/image.png
  → server strip `_storage_/` → serve storage/files/image.png
```

⚠️ Không có auth — chỉ serve file user upload.

13.8. Quota override pattern

Module có thể check quota trước khi ghi file lớn:

```python
def upload_big_file(self, req):
    try:
        data = req.get("data", "")
        usage = self.engine.storage.usage(self.name)
        estimated_size = len(data)
        if usage["used"] + estimated_size > usage["quota"] * 0.98:
            return {
                "ok": False,
                "error": f"Quota gần đầy: {usage['used']}/{usage['quota']} bytes",
                "usage": usage,
            }
        self.engine.storage.write_file(self.name, "big.bin", data)
        return {"ok": True, "usage": self.engine.storage.usage(self.name)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

---

14. Loading & Restart (v1.4.0) ⭐

14.1. Loading overlay

· Hiện khi App.init() bắt đầu
· Cập nhật text theo tiến trình: "Khởi tạo…", "Tải projects…", "Tải README…", "Tải modules…"
· Ẩn sau khi mọi thứ sẵn sàng (~200ms)
· Style: overlay tối + spinner xanh + text dim

14.2. Restart flow

```
User click 🔄 Restart (confirm dialog)
  ↓
App._showRestartOverlay()  ← overlay 🔄
  ↓
POST /api/system/restart
  ↓
engine._restart_pending = True
  ↓
broadcast {type:"system_restarting"}
  ↓
os.execv(main.py) → process restart
  ↓
boot() hoàn tất
  ↓
broadcast {type:"system_restarted", boot_id}
  ↓
app.js: location.reload() (sau 800ms)
  ↓
UI mới hoàn chỉnh
```

14.3. Storage warning toast

Khi nhận storage_warning qua WS:

· warn (≥ 90%): toast vàng góc phải trên, tự ẩn sau 6s
· error (≥ 98%): toast đỏ, tự ẩn sau 10s
· Click toast → mở Storage UI của module

14.4. Boot info endpoint

```bash
curl http://localhost:8765/api/boot
# {
#   "ok": true,
#   "boot_id": "boot_1699999999999",
#   "version": "1.4.0",
#   "modules": ["demo_module", "code_reminder"],
#   "storage_quota": 536870912
# }
```

---

15. Dev workflow

15.1. Thêm route core (protected)

Trong core/engine.py → _init_core():

```python
A = self.router.add_core          # ← protected route
A("GET", "/api/my_endpoint", self._api_my_endpoint)
```

⚠️ LUÔN dùng add_core — nếu dùng router.add, module có thể override.

15.2. Add overlay cho module

```bash
# File nhỏ
touch modules/my_mod/web/overlay.css
touch modules/my_mod/web/overlay.js

# File lớn (> 50KB bundle)
touch modules/my_mod/data/overlay.css
touch modules/my_mod/data/overlay.js
```

Reload module → overlay tự inject. Test safe mode: /?safe=1.

15.3. Trigger diagnostics từ module

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

15.4. Intercept errors

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

15.5. Override file (dev only)

Đặt .py trong overrides/ → được exec() sau _init_core, trước khi load modules.

```python
# overrides/my_patch.py
def patch(engine, sandbox, config, router):
    print("[patch] applying custom route")
    router.add_core("GET", "/api/dev/debug", lambda req: {"debug": True})
```

15.6. Dùng Module Storage trong module

```python
class Module(ModuleBase):
    def on_load(self):
        # Ensure storage ready
        self.engine.storage.storage_dir(self.name)

    def save_cache(self, key, value):
        import json
        self.engine.storage.write_file(
            self.name, f"cache/{key}.json",
            json.dumps(value)
        )

    def load_cache(self, key):
        import json
        try:
            data = self.engine.storage.read_file(self.name, f"cache/{key}.json")
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None
```

15.7. Add export cho resource mới

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
await App.exportTemplate(name);
```

---

16. Testing cheat-sheet

```bash
# Backend up?
curl http://localhost:8765/api/status
curl http://localhost:8765/api/boot

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

# Overlays
curl http://localhost:8765/api/overlay

# Module static
curl http://localhost:8765/module/demo_module/
curl http://localhost:8765/module/my_mod/_data_/overlay.css

# Terminal
curl http://localhost:8765/api/terminal/sessions

# Export project / module
curl -X POST http://localhost:8765/api/projects/export \
  -H 'Content-Type: application/json' -d '{"name":"demo"}' \
  | head -c 200
curl -X POST http://localhost:8765/api/modules/export \
  -H 'Content-Type: application/json' -d '{"name":"demo_module"}' \
  | head -c 200

# ⭐ v1.4.0: Storage
curl -X POST http://localhost:8765/api/modules/storage/usage \
  -H 'Content-Type: application/json' -d '{"name":"demo_module"}'

curl -X POST http://localhost:8765/api/modules/storage/list \
  -H 'Content-Type: application/json' -d '{"name":"demo_module"}'

# Upload 1 chunk nhỏ (giả lập)
echo -n "hello world" | base64 > /tmp/chunk.b64
curl -X POST http://localhost:8765/api/modules/storage/upload_chunk \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"demo_module\",\"path\":\"hello.txt\",\"chunk_index\":0,\"total_chunks\":1,\"chunk_b64\":\"$(cat /tmp/chunk.b64)\",\"total_size\":11,\"upload_id\":\"test1\"}"

# Download
curl -X POST http://localhost:8765/api/modules/storage/download \
  -H 'Content-Type: application/json' -d '{"name":"demo_module","path":"hello.txt"}'

# Export ZIP
curl -X POST http://localhost:8765/api/modules/storage/export_zip \
  -H 'Content-Type: application/json' -d '{"name":"demo_module"}' \
  | python3 -c "import sys,json,base64; d=json.load(sys.stdin); open('/tmp/storage.zip','wb').write(base64.b64decode(d['zip_base64'])); print('files:', d['files'], 'size:', d['size'])"

unzip -l /tmp/storage.zip
```

Test Storage UI (browser)

1. Vào tab Modules → click 💾 cạnh module
2. Xem usage bar (xanh/vàng/đỏ theo %)
3. Click 📤 Upload file → chọn file → xem progress bar
4. Click ⬇ trên file row → tải về
5. Click ⬇ Export ZIP → tải <name>_storage.zip
6. Click 🗑 Clear all → confirm → storage trống

Test Quota warning

```bash
# Tạo module test với quota nhỏ
mkdir -p modules/quick_test
cat > modules/quick_test/init.txt << 'EOF'
{
  "name": "quick_test",
  "version": "1.0.0",
  "module_storage_quota": 1048576
}
EOF
cat > modules/quick_test/main.py << 'EOF'
from core.loader import ModuleBase
class Module(ModuleBase):
    pass
EOF

# Reload → thử upload 900KB → xem toast cảnh báo (≥90%)
# Upload tiếp 100KB → block (≥98%)
```

Test Loading & Restart

1. Reload trang → thấy loading overlay
2. Click 🔄 Restart → thấy overlay 🔄
3. Đợi ~2s → trang tự reload
4. Kiểm tra #connDot xanh + output log có "Server restarted"

Test Undo/Redo

1. Mở file A → gõ vài dòng → mở file B → gõ vài dòng
2. Quay lại tab A → Ctrl+Z → chỉ undo được những gì đã sửa ở A
3. Ctrl+Z liên tục đến khi hết → nút ↶ tự disable
4. Ctrl+Y → redo từng bước → nút ↷ tự disable khi hết
5. Sửa 1 dòng → Ctrl+S → dấu ● biến mất → Ctrl+Z → dấu ● xuất hiện lại
6. Undo tiếp về trước bước save → dấu ● vẫn còn
7. Redo về đúng trạng thái đã lưu → dấu ● tự biến mất

Reset khi kẹt

```bash
pkill -f "python main.py"
fuser -k 8765/tcp
rm core/data/.run_pids.json
rm core/data/settings.json
# Storage cache: xoá thủ công từng module
rm -rf modules/*/storage/.tmp_uploads
```

---

17. Troubleshooting

Vấn đề Nguyên nhân Fix
Undo/redo không hoạt động Focus trong input/modal Click vào editor rồi thử lại
Undo mất history khi đổi tab Code cũ dùng setValue Hard-reload để lấy code mới (v1.3.3 fix bằng swapDoc)
Dirty ● không biến mất sau undo So sánh string thất bại (line ending?) Kiểm tra file có CRLF không
Android: Backspace không xoá dòng cuối CM5 + contenteditable v1.3.2 đã fix (_fixAndroidLineMerge)
Settings lưu nhưng không áp dụng Thiếu listener settings_changed v1.3.2 đã fix
Theme chọn "light"/"dark" không đổi Không phải theme CM5 hợp lệ Đổi sang dracula/default/material/monokai/solarized/eclipse
Auto-wrap bật dù đã tắt Settings cũ còn line_wrap: true Vào Settings → Editor → bỏ tick
Overlay CSS không load File đặt sai chỗ data/ hoặc web/, tên overlay.css / override.css
Module route bị reject Trùng core route Đổi path, không override /api/status, /api/projects/*
get_settings() trả về {} Chưa có settings_schema Khai báo schema trong init.txt
Fold không hoạt động trên JS Thiếu addon Check index.html có load brace-fold.min.js
Process treo khi disconnect auto_stop_on_disconnect=false Đặt true trong config.json
Terminal không mở được CDN chặn xterm.js Kiểm tra console: [Terminal] xterm.js not loaded
Terminal "limit reached" Đã đủ max_sessions Tăng terminal.max_sessions
Export nút ⬇ không hiện Code frontend cũ Hard-reload (Ctrl+Shift+R)
Export trả 404 Backend chưa update Restart server (route khai báo trong _init_core)
ZIP export rỗng (0 files) Project/module rỗng Tạo ít nhất 1 file user-facing
Import báo "already installed" Module cùng tên tồn tại Uninstall/delete trước, hoặc đổi tên khi upload
Storage upload báo "QuotaExceeded" ≥ 98% quota Xoá file cũ / clear all
Storage upload 400 Thiếu upload_id hoặc chunk_b64 Check payload JSON
Storage file không list được Path escape hoặc file không tồn tại Verify path không có ../
Storage warning không hiện WS chưa kết nối Check #connDot xanh; thử refresh
Loading overlay không ẩn JS error trước _hideLoading() Check DevTools console
Restart không reload trang WS system_restarted không tới Check Network tab → WS frames
Module storage chiếm nhiều disk File user upload không dọn Dùng UI 💾 → Clear all
Export module ZIP chứa .tmp_uploads Chunk chưa cleanup v1.4.0 đã exclude; nếu còn → check export_module_zip filters

---

18. Known issues / Roadmap

🔴 Cần test kỹ

· ☐ Error dispatch chain: on_any_error → on_http_error (pass-through + handle)
· ☐ Settings modal: schema validation, on_settings_changed callback
· ☐ Overlay: data/ bundle load, safe mode ?safe=1, per-module toggle
· ☐ Diagnostics: auto-run on save, inline markers, jump-to-line
· ☐ Core route protection: module cố override /api/status phải bị reject
· ☐ Folding: Python nested functions, JS template strings
· ☐ Android: Samsung Internet, Firefox mobile
· ☐ Terminal: Windows pipes (không có PTY), copy/paste mobile, ZMODEM
· ☐ Undo/Redo: selection state sau swapDoc, fold state per-tab, IME composition
· ☐ Export: symlink handling, project lớn (> 100MB), concurrent export
· ☐ Storage: quota edge case (upload vượt 100%, concurrent upload)
· ☐ Storage: file > 200MB (giới hạn frontend)
· ☐ Storage: Windows path handling

🟢 Nice to have

· ☐ Import from Git URL
· ☐ Multi-user auth
· ☐ Resource limits (CPU/mem per process)
· ☐ Overlay hot-reload khi save file trong data/
· ☐ Per-file undo history persistence (sessionStorage, giữ khi F5)
· ☐ Per-file fold state persistence (localStorage)
· ☐ Terminal scrollback persistence
· ☐ Terminal split panes
· ☐ Export: chọn subset file (checkbox tree)
· ☐ Export: .tar.gz option
· ☐ Export: server-side save to disk (không cần base64 round-trip)
· ☐ Storage: file preview (image, text)
· ☐ Storage: folder upload
· ☐ Storage: share link (temporary token)
· ☐ Storage: quota dashboard toàn hệ thống

Roadmap

v1.4.x — polish

· Test suite (pytest cho core, playwright cho frontend)
· Docs: error dispatch chain + 3 module examples ✅
· Diagnostics: severity filter trong UI
· Storage: file preview (image/text)
· Storage: quota dashboard

v1.5.0 — developer experience

· Hot reload module (watch modules/*/main.py + data/*.css|js)
· Preview HTML project (/preview/<project>/)
· Terminal: multiple tabs
· Undo history persistence qua sessionStorage
· Multi-cursor editing (giống VS Code Alt+Click)
· Export: stream download (không buffer toàn bộ vào RAM)
· Storage: folder upload + drag & drop

v2.0.0 — scale

· Multi-user + auth
· Collaborative editing (WS) — conflict resolution + OT
· Docker isolation per project
· Resource limits
· Terminal sandbox (Docker exec)
· Cloud sync / Git integration

---

19. Legal

Educational / personal use. Không cài module từ nguồn không tin cậy — module có toàn quyền Python. Không chạy server bằng sudo. Terminal chạy với quyền user server — cẩn trọng khi expose ra mạng LAN/WAN.

Module Storage không có authentication — chỉ serve file user upload. Không lưu dữ liệu nhạy cảm.

```

---

## 📌 Tóm tắt những gì đã thay đổi trong README v1.4.0

| Mục | Nội dung mới |
|---|---|
| **Header** | Version `1.4.0`, thêm "module storage với quota 512MB" |
| **§1 Status** | Thêm 4 dòng: Module Storage, Loading overlay, Restart refresh UI, Storage warning toast |
| **§3 Cấu trúc** | Thêm `core/module_storage.py`, `frontend/js/storage_ui.js`, `modules/<name>/storage/` (3 sub-dir) |
| **§4 Architecture** | Thêm luồng **Module Storage** + **Loading & Restart**, cập nhật `ModuleStorage` trong engine |
| **§5 Module Contract** | ⭐ Thêm **[§5.7 Module Storage](#57-module-storage-)** — Python API, quota, exception, UI |
| **§6 Tạo module** | Bước 1 thêm `storage/`, Bước 5 thêm test storage |
| **§7 API Reference** | Thêm 7 storage endpoints + `/api/boot`; note `_storage_/` static path |
| **§8 WS Protocol** | Thêm `storage_warning`, `system_restarted` |
| **§9 Frontend** | Thêm §9.6 Loading overlay, §9.7 Storage UI |
| **§13 Module Storage** ⭐ | **Section hoàn toàn mới** — tổng quan, cấu trúc, config, ngưỡng, Python API, HTTP API, serve file, quota override pattern |
| **§14 Loading & Restart** ⭐ | **Section hoàn toàn mới** — loading flow, restart flow, storage warning toast, boot info endpoint |
| **§15 Dev workflow** | Thêm §15.6 dùng Storage trong module, đánh số lại các mục |
| **§16 Testing** | Thêm curl storage + test quota + test loading/restart + reset `.tmp_uploads` |
| **§17 Troubleshooting** | Thêm 8 dòng về storage + loading/restart |
| **§18 Roadmap** | Thêm nice-to-have storage (file preview, folder upload, share link, quota dashboard); note storage edge cases cần test |
| **§19 Legal** | Thêm note storage không auth |

**Điểm nhấn quan trọng:**

- ⭐ **§5.7 + §13 là trung tâm** — mô tả đầy đủ Python API, HTTP API, quota, cảnh báo, UI
- **Quota 512MB** mặc định, override per-module qua `init.txt`
- **Ngưỡng**: ≥ 90% warn, ≥ 98% block
- **Chunked upload** 4MB/chunk, hỗ trợ tới 200MB/file
- **Loading & Restart** — UX mượt, tự reload sau restart
- **Pattern tái sử dụng** trong §15.7 → dễ mở rộng export cho resource mới