🚀 ACDV-Teams Coder — Bản tóm tắt Welcome Screen

Local Web IDE nhẹ, tự chủ, chạy ngay trên máy bạn — Termux/Android hoặc Linux.
Phiên bản: v2.0.1

---

📑 Mục lục

1. Vì sao có ACDV-Teams Coder?
2. 🚨 Cảnh báo an toàn — ĐỌC TRƯỚC
3. ⚡ Bắt đầu trong 30 giây
4. ✅ Nên làm / ⛔ Không nên làm
5. 🧠 Triết lý cốt lõi — Edit ≠ Run
6. 🩹 v2.0.1 có gì mới?
7. 🔧 Kẹt thì làm gì?
8. 📚 Đọc thêm ở đâu?
9. 🎯 Ưu tiên đọc theo thứ tự
10. ⚠️ Trạng thái hiện tại

---

<a id="1"></a>

1. 💡 Vì sao có ACDV-Teams Coder?

Tôi mê code nhưng máy yếu. Trên chiếc Android RAM có hạn, mỗi lần code là một lần khổ: mở AIDE để gõ, mở Termux để chạy, mở browser để debug — quay qua quay lại thì tràn RAM, app bị kill ngang, code chưa lưu đã bay màu 💀.

ACDV-Teams Coder ra đời để giải quyết đúng bài toán đó:

# Đặc điểm Mô tả
✅ Một chỗ duy nhất Không mở loạn xạ 3–4 app
✅ Vỏ siêu nhẹ Python stdlib làm backend, CodeMirror làm editor
✅ Không bị kill giữa chừng Chạy local, không phụ thuộc cloud
✅ Mở rộng bằng module Ngôn ngữ nào cần thì cài module đó, không nhồi compiler vào core
✅ Mã nguồn mở, tự chủ Dữ liệu của bạn nằm trên máy bạn

---

<a id="2"></a>

2. 🚨 CẢNH BÁO AN TOÀN — ĐỌC TRƯỚC KHI DÙNG

ACDV-Teams Coder là Python thuần, chạy trực tiếp (interpreted) — không có "lớp giáp" bảo vệ. Module độc có thể:

· 🔴 Đọc/ghi file cá nhân, đánh cắp SSH key, token, cookie, API key
· 🔴 Cài backdoor, biến máy thành botnet
· 🔴 Trên Android đã root: chiếm toàn quyền thiết bị, đọc tin nhắn, danh bạ, ảnh, mật khẩu

⛔ 5 quy tắc KHÔNG NGOẠI LỆ

# Quy tắc Chi tiết
1 KHÔNG cài module không chính thức Chỉ dùng module có hash SHA256 khớp danh sách ACDV-Teams công bố. Mọi module "share lại", "mod by...", "tải từ group" → coi như mã độc.
2 KHÔNG chạy bằng sudo/root Không sudo python, không chạy trên Android đã root khi chưa cô lập.
3 KHUYẾN NGHỊ CỰC MẠNH: chạy trong sandbox • Android/Termux → proot-distro (Debian/Ubuntu/Alpine) • Linux → Docker/Podman với --cap-drop=ALL, --security-opt=no-new-privileges, mount chỉ thư mục project
4 KHÔNG chạy trên máy có dữ liệu quan trọng Không đăng nhập ngân hàng/email/MXH trong lúc test module lạ.
5 Kiểm hash trước khi tin Hash mismatch → DỪNG NGAY, xoá module, không cố chạy.

⚠️ Riêng v2.0.1

· CSP đã siết (connect-src chỉ cho WS tới host:port hiện tại).
· Nhưng overlay vẫn có thể gửi terminal_open qua WS same-origin → shell thực thi với quyền user.
· Fix triệt để cần iframe sandbox (roadmap v2.1). Trong lúc chờ: chỉ cài module tin cậy.

💀 Tóm lại: cài module lạ không sandbox = trao chìa khóa thiết bị cho người lạ.

---

<a id="3"></a>

3. ⚡ Bắt đầu trong 30 giây

🔹 Bước 1 — Khởi động server

```bash
cd /path/to/acdv-coder
python3 main.py
```

· Mặc định: http://localhost:8765 — mở trình duyệt là dùng được.
· Đổi port nếu bị chiếm:

```bash
python3 main.py --port 9000
```

🔹 Bước 2 — Tạo project đầu tiên

1. Bấm nút ＋ trên toolbar (hoặc New Project ngay màn hình này).
2. Nhập tên project → chọn ngôn ngữ → bấm Create.
3. File starter tự sinh, syntax highlight sẵn.

🔹 Bước 3 — Code và chạy

1. Click file trong Explorer để mở tab.
2. Gõ code → Ctrl + S để lưu (tab có chấm ● = chưa lưu).
3. Bấm ▶ để chạy — chỉ .py / .js / .sh / .bash (ngôn ngữ khác cần module).
4. Output stream realtime vào panel Run bên dưới.

🔹 Bước 4 — Terminal (tùy chọn)

· Bấm Ctrl + ` hoặc nút ⌨ để mở terminal.
· Shell thật qua PTY — dùng được vim / htop / less.
· Cài compiler cho module:
  · Java: pkg install openjdk-17
  · C/C++: pkg install clang

🔹 Bước 5 — Cài module khi cần ngôn ngữ khác

· Tab Modules → 📤 Upload ZIP → chọn file .zip module.
· Module tự pkg install compiler khi bạn bấm nút của nó.
· Export backup: ⬇ cạnh tên module.

---

<a id="4"></a>

4. ✅ Nên làm / ⛔ Không nên làm

✅ Nên làm ngay

· ☐ Đọc Cảnh báo an toàn phía trên — đừng bỏ qua.
· ☐ Chạy trong sandbox nếu test module lạ (proot-distro hoặc Docker).
· ☐ Backup project trước khi thử module mới — tab Projects → ⬇.
· ☐ Kiểm hash SHA256 module tải về — không tin bằng mắt.
· ☐ Đọc README.md để hiểu đầy đủ — file này chỉ tóm tắt.

⛔ KHÔNG nên làm

· ❌ Chạy sudo python main.py trên Linux.
· ❌ Cài module từ group chat, diễn đàn, "share lại".
· ❌ Test module lạ trên máy có dữ liệu quan trọng.
· ❌ Bật quyền trợ năng (Accessibility) cho module không rõ nguồn.
· ❌ Tin vào "mod by...", "fork không rõ nguồn".

---

<a id="5"></a>

5. 🧠 Triết lý cốt lõi — Edit ≠ Run

```
EDIT  →  ~50 ngôn ngữ (syntax highlight + save UTF-8)     [core]
RUN   →  CHỈ .py / .js / .sh / .bash                       [core]
RUN   →  Java, C/C++, Go, Rust, PHP, Ruby, ...             [module tự lo]
```

Thành phần Phạm vi Ghi chú
Core – Edit ~50 ngôn ngữ (Python, JS, Java, C/C++, Go, Rust, PHP, Ruby, …) syntax highlight + save UTF-8
Core – Run Chỉ .py, .js, .sh, .bash 
Module – Run Java, C/C++, Go, Rust, PHP, Ruby, … module tự pkg install compiler + spawn process

Không nhồi compiler vào core → core nhẹ, không phình, không bị kill.

---

<a id="6"></a>

6. 🩹 v2.0.1 có gì mới?

35 bug đã fix — nâng cấp từ v2.0.0 hoặc 1.4.x ngay.

Nhóm Fix tiêu biểu
Watcher Auto-detect module hoạt động đúng (add/reload/remove)
Terminal Không còn leak session, heartbeat 90s chống timeout
Overlay Tắt JS không mất CSS, CSP siết WS, không double-init
Editor Dirty flag giữ khi lazy load mode, markers không mất
Diagnostics Nested path OK, timeout 5s chống treo
Storage Concurrent upload an toàn, chunk out-of-order OK, quota check chặt
Settings Atomic write — không corrupt khi crash
Project Save sau delete không resurrect, tab tự đóng khi file/project xoá
Run Module output không trộn panel Run của core
Bảo mật CSP siết, chặn dotfile, body cap 64MB

Chi tiết từng bug → xem README.md (file đầy đủ).

---

<a id="7"></a>

7. 🔧 Kẹt thì làm gì?

🔄 Reset nhanh

```bash
pkill -f "python main.py"
fuser -k 8765/tcp
rm core/data/.run_pids.json
rm core/data/settings.json
rm -rf modules/*/storage/.tmp_uploads
python3 main.py
```

🔃 Hard reload browser

Ctrl + Shift + R — không phải F5. Nhiều bug UI cũ do cache.

🐞 Các lỗi thường gặp

Lỗi Fix
Port bị chiếm python3 main.py --port 9000
Undo/redo không chạy Click vào editor rồi thử lại (không focus input)
Terminal "Connecting…" mãi WS chưa sẵn sàng — đợi kết nối rồi mở lại
Chạy .java báo "Core không hỗ trợ" Đúng thiết kế — cài module lang_java
javac not found Terminal → pkg install openjdk-17
Overlay phá UI http://localhost:8765/?safe=1 (safe mode)
Storage đầy Tab Modules → 💾 → xoá file / clear all

---

<a id="8"></a>

8. 📚 Đọc thêm ở đâu?

Nguồn Nội dung
README.md Tài liệu đầy đủ: API reference, Module Contract, Overlay API, WebSocket protocol, roadmap, troubleshooting chi tiết
config.json Cấu hình server (port, host, quota, SSL, terminal)
modules/demo_module/ Template module đầy đủ contract + overlay v2.0.1
Tab Settings → About Hướng dẫn chi tiết ngay trong app

---

<a id="9"></a>

9. 🎯 Ưu tiên đọc theo thứ tự

👤 Nếu bạn là USER mới

1. Đọc Cảnh báo an toàn ở trên.
2. Làm Bắt đầu trong 30 giây → tạo project → chạy "Hello World".
3. Đọc README.md phần Hướng dẫn sử dụng (§ User Guide).

🛠️ Nếu bạn muốn viết MODULE

1. Đọc Cảnh báo an toàn — hiểu rủi ro.
2. Đọc README.md phần Module Contract + Overlay Runtime.
3. Xem modules/demo_module/ làm mẫu.
4. Viết module → test trong sandbox.

🐞 Nếu bạn đang DEBUG

1. Mở DevTools Console — lỗi frontend ở đây.
2. Xem terminal server — lỗi backend ở đây.
3. Đọc README.md phần Troubleshooting (30+ dòng bug → fix).

---

<a id="10"></a>

10. ⚠️ Trạng thái hiện tại (v2.0.1)

Trạng thái Hạng mục
✅ Core engine, router, server: ổn định
✅ Watcher auto-detect: hoạt động đúng
✅ Terminal session: tự cleanup, không leak
✅ Overlay: cleanup registry, ETag, CSP siết
✅ Storage: quota, chunk, concurrent-safe
✅ Settings: atomic write, không corrupt
⚠️ Overlay vẫn có thể gửi terminal_open qua WS (fix ở v2.1 iframe sandbox)
⚠️ Error dispatch chain cần test thêm với 3+ module
⚠️ Android: cần test thêm Samsung Internet, Firefox mobile

Mọi đóng góp, báo lỗi, hoặc tự do vọc vạch tùy biến đều được hoan nghênh theo tinh thần mã nguồn mở và tự chủ công nghệ!

---

🚀 Sẵn sàng chưa?

1. Bấm ＋ New Project ngay trên màn hình này.
2. Chọn Python → bấm Create.
3. Gõ print("Hello, ACDV!") → Ctrl + S → ▶.
4. Thấy output → bạn đã sẵn sàng! 🎉

Chúc bạn code thật mượt — và thật an toàn — cùng ACDV-Teams Coder v2.0.1! 💙

---

📝 File này là bản tóm tắt cho welcome screen. Để đọc đầy đủ (API, module contract, overlay API, roadmap), mở README.md hoặc vào Settings → About.