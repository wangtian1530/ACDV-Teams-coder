"""
AI Autocomplete — Gemini (free) + DeepSeek (rẻ)
Copyright © ACDV-Teams
"""
from core.loader import ModuleBase
import json
import os
import urllib.request
import urllib.error


GEMINI_URL   = ("https://generativelanguage.googleapis.com/v1beta/models/"
                "{model}:generateContent?key={key}")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

VERSION   = "1.3.0"
AUTHOR    = "ACDV-Teams"
COPYRIGHT = "© ACDV-Teams"

MODEL_CATALOG = {
    "gemini": [
        {"id": "gemini-3.8-flash",      "name": "Gemini 3.8 Flash",      "desc": "Cân bằng tốc độ / chất lượng / quota miễn phí", "badge": "⭐ Recommend", "tier": "stable",   "free": True},
        {"id": "gemini-3.8-flash-lite", "name": "Gemini 3.8 Flash Lite", "desc": "Nhẹ, nhanh, ít token — phù hợp file lớn",       "badge": "⚡ Fast",     "tier": "fast",     "free": True},
        {"id": "gemini-3.7-flash",      "name": "Gemini 3.7 Flash",      "desc": "Ổn định, hiệu năng cao tối ưu cho code",        "badge": "🎯 Stable",   "tier": "legacy",   "free": True},
        {"id": "gemini-3.5-flash-8b",   "name": "Gemini 3.5 Flash 8B",   "desc": "Nhỏ nhất, cực nhẹ — tốt cho máy yếu",          "badge": "💨 Tiny",     "tier": "tiny",     "free": True},
        {"id": "gemini-3.1-pro",        "name": "Gemini 3.1 Pro",        "desc": "Chất lượng cao — quota miễn phí hạn chế",       "badge": "💎 Pro",      "tier": "pro",      "free": False},
        {"id": "gemini-4.0-flash",      "name": "Gemini 4.0 Flash",      "desc": "Thế hệ mới nhất — tối ưu hóa vượt trội",        "badge": "🆕 New",     "tier": "newest",   "free": True},
    ],
    "deepseek": [
        {"id": "deepseek-chat",     "name": "DeepSeek Chat",     "desc": "Nhanh + cực rẻ (~$0.14/1M token) — tốt cho autocomplete", "badge": "⭐ Recommend", "tier": "general",   "free": False},
        {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner", "desc": "Suy luận sâu — chậm hơn, hợp thuật toán phức tạp",         "badge": "🧠 Reasoner",  "tier": "reasoning", "free": False},
    ],
}

VALID_MODELS = {p: {m["id"] for m in lst} for p, lst in MODEL_CATALOG.items()}
ALLOWED_KEYS = {
    "enabled", "provider",
    "model_gemini", "model_deepseek",
    "fallback_gemini", "fallback_deepseek",
    "max_tokens", "temperature",
}

DEFAULTS = {
    "enabled": True,
    "provider": "gemini",
    "model_gemini": "gemini-3.8-flash",
    "model_deepseek": "deepseek-chat",
    "fallback_gemini": "gemini-3.5-flash-8b",
    "fallback_deepseek": "deepseek-chat",
    "max_tokens": 120,
    "temperature": 0.3,
}

LOCAL_MARKERS = {"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"}

HELP_TEXT = """═══════════════════════════════════════════════════════════════
 AI AUTOCOMPLETE — GEMINI + DEEPSEEK (v1.3.0)
 © ACDV-Teams — Hướng dẫn cài đặt & sử dụng
═══════════════════════════════════════════════════════════════


1. YÊU CẦU
───────────────────────────────────────────────────────────────
 • ACDV-Teams Coder v1.4.0 trở lên (có Module Storage)
 • Python 3.8+ (không cần cài thêm thư viện — module dùng stdlib)
 • Kết nối Internet (để gọi Gemini hoặc DeepSeek API)
 • API key của ít nhất một trong hai nhà cung cấp:
     ✨ Gemini    — MIỄN PHÍ, quota ~1500 request/ngày
     🐋 DeepSeek  — KHÔNG free, nhưng cực rẻ (~$0.14 / 1M token)


2. CÀI ĐẶT
───────────────────────────────────────────────────────────────
 Cách A — Upload qua UI (khuyến nghị)
   1. Nén thư mục ai_autocomplete/ thành ai_autocomplete.zip
        cd modules && zip -r ai_autocomplete.zip ai_autocomplete/
   2. Mở ACDV-Teams Coder → tab Modules → 📤 Upload
   3. Chọn ai_autocomplete.zip → module tự load

 Cách B — Copy thủ công
   1. Copy toàn bộ thư mục ai_autocomplete/
      vào  <acdv-coder>/modules/ai_autocomplete/
   2. Khởi động lại server HOẶC reload module:
        curl -X POST http://localhost:8765/api/modules/reload \\
          -H 'Content-Type: application/json' \\
          -d '{"name":"ai_autocomplete"}'

 Sau khi cài, kiểm tra module đã nhận chưa:
        curl http://localhost:8765/api/ai_autocomplete/info
 Kỳ vọng:
        {"ok":true,"version":"1.3.0","author":"ACDV-Teams",...}


3. CHẾ ĐỘ LOCALHOST (TỰ THIẾT LẬP)
───────────────────────────────────────────────────────────────
 🆕 Khi bạn mở module qua http://localhost:8765 hoặc
     http://127.0.0.1:8765, module sẽ TỰ ĐỘNG:

   1. Detect "localhost mode" → hiện badge 🏠 Localhost
   2. Tự động tạo data/settings.json với DEFAULTS nếu chưa có
      (chỉ lần đầu — không ghi đè khi đã có)
   3. Tự động TEST API khi mở trang nếu đã có API key
      (chỉ 1 lần / session — lưu cờ trong sessionStorage)
   4. Hiển thị cảnh báo bảo mật nếu phát hiện không phải local

 ❌ KHÔNG dùng chế độ này khi deploy công khai — nó được
    thiết kế cho dev local. Production nên tắt qua Settings hoặc
    cấu hình NAT/firewall chặn port 8765 từ Internet.

 Cách nhận biết:
   • Badge vàng "🏠 Localhost" cạnh tên version
   • Dòng status ghi "Localhost auto-setup: đã tạo settings.json"
   • Toast "Auto-test API thành công (localhost mode)"


4. API KEY
───────────────────────────────────────────────────────────────

 4.1. Gemini (MIỄN PHÍ)
   1. Mở: https://aistudio.google.com/app/apikey
   2. Đăng nhập tài khoản Google
   3. Bấm "Create API key" → chọn project (hoặc tạo mới)
   4. Copy chuỗi key dạng:  AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXX
      (khoảng 39 ký tự)
   Free tier (gemini-3.8-flash):
     • ~15 request / phút
     • ~1500 request / ngày
     • ~1 triệu token input / tháng
   Với autocomplete cá nhân, mức này dư sức dùng.

 4.2. DeepSeek (TRẢ PHÍ NHƯNG RẺ)
   1. Mở: https://platform.deepseek.com/api_keys
   2. Đăng ký / đăng nhập
   3. Bấm "Create new API key"
   4. Copy chuỗi key dạng:  sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   Bảng giá (tham khảo, thay đổi theo thời gian):
     • deepseek-chat     : ~$0.14 / 1M input  · ~$0.28 / 1M output
     • deepseek-reasoner : ~$0.55 / 1M input  · ~$2.19 / 1M output
   Autocomplete chỉ dùng ~2000 token/lần, nên 1$ dùng được
   hàng chục nghìn lần gợi ý → gần như miễn phí cho nhu cầu cá nhân.

 4.3. Bạn cần CẢ HAI KEY?
   Không bắt buộc. Chỉ cần key của provider bạn sẽ dùng.
   Module lưu key riêng cho từng provider — có thể chuyển
   qua lại bất kỳ lúc nào mà không mất key đã lưu.


5. CẤU HÌNH BẰNG GIAO DIỆN
───────────────────────────────────────────────────────────────
 Mở trang cấu hình đầy đủ:
        http://localhost:8765/module/ai_autocomplete/

 5.1. Chọn PROVIDER (tab trên cùng)
   • ✨ Gemini    — miễn phí, phù hợp dùng hằng ngày
   • 🐋 DeepSeek  — trả phí cực rẻ, chất lượng cao hơn
   • Chấm xanh nhỏ cạnh tên provider = đã có key
   • Click tab → toàn bộ UI bên dưới đổi theo provider đó:
       - Ô nhập API key riêng
       - Danh sách model riêng
       - Fallback riêng

 5.2. Chọn MODEL CHÍNH (dạng thẻ, click chọn 1)

   ✨ GEMINI (mới):
     • Gemini 3.8 Flash       ⭐ Recommend — cân bằng tốc độ/chất lượng
     • Gemini 3.8 Flash Lite  ⚡ Fast      — nhẹ, ít token
     • Gemini 3.7 Flash       🎯 Stable    — ổn định, tối ưu cho code
     • Gemini 3.5 Flash 8B    💨 Tiny      — nhỏ nhất, máy yếu
     • Gemini 3.1 Pro         💎 Pro       — chất lượng cao (quota hạn chế)
     • Gemini 4.0 Flash       🆕 New       — thế hệ mới nhất

   🐋 DEEPSEEK:
     • DeepSeek Chat          ⭐ Recommend — nhanh, cực rẻ, hợp autocomplete
     • DeepSeek Reasoner      🧠 Reasoner  — suy luận sâu, chậm hơn

 5.3. Chọn MODEL DỰ PHÒNG (dropdown)
   • Nếu model chính bị 429 (rate limit) hoặc 503 (quá tải),
     module tự động thử model dự phòng CÙNG PROVIDER.
   • Ví dụ: Gemini 3.8 Flash → fallback → Gemini 3.5 Flash 8B
   • Để "— Không dùng dự phòng —" nếu muốn kiểm soát thủ công.

 5.4. Tham số sinh
   • Max output tokens  : 20 – 800 (mặc định 120)
                          Cao = gợi ý dài hơn, tốn token hơn
   • Temperature        : 0.00 – 1.00 (mặc định 0.30)
                          0.0 = chính xác · 1.0 = sáng tạo
                          Code production khuyến nghị 0.1 – 0.3
   • Bật AI Autocomplete: tắt tạm module mà không cần xoá

 5.5. Nút "💾 Lưu cấu hình"
   • Ghi vào settings → áp dụng NGAY cho lần gọi tiếp theo
   • Không cần reload trang / restart server
   • Lưu TẤT CẢ provider cùng lúc (model/fallback của cả 2)

 5.6. Nút "↺ Đặt lại mặc định"
   • Reset form về mặc định (CHƯA lưu, phải bấm Lưu)


6. NHẬP KEY & TEST API
───────────────────────────────────────────────────────────────

 Bước 1 — Nhập key
   • Click tab provider muốn dùng (Gemini hoặc DeepSeek)
   • Dán key vào ô "xxx API Key"
   • Bấm "💾 Lưu key"

 Bước 2 — Test
   • Bấm "🧪 Test API" (sẽ dùng model đang chọn của provider)
   • Kết quả xanh  → "gemini API hoạt động (model: gemini-3.8-flash)"
   • Kết quả đỏ    → chi tiết lỗi kèm provider/model đang test

 💡 Trên localhost: nếu đã có key, module tự test 1 lần khi mở trang.
    Kết quả hiện tự động trong khung status.

 Cách B — Test qua curl (dành cho dev)
        # Test Gemini
        curl -X POST http://localhost:8765/api/ai_autocomplete/test \\
          -H 'Content-Type: application/json' \\
          -d '{"provider":"gemini","api_key":"AIzaSy..."}'

        # Test DeepSeek
        curl -X POST http://localhost:8765/api/ai_autocomplete/test \\
          -H 'Content-Type: application/json' \\
          -d '{"provider":"deepseek","api_key":"sk-..."}'

 Kiểm tra trạng thái:
        curl http://localhost:8765/api/ai_autocomplete/info
        → {
            "has_keys": {"gemini": true, "deepseek": true},
            "is_localhost": true,
            "auto_setup": false,
            "provider": "gemini",
            ...
          }


7. SỬ DỤNG TRONG EDITOR
───────────────────────────────────────────────────────────────
 Sau khi load module, mở bất kỳ file nào trong ACDV-Teams Coder:

   • Toolbar editor xuất hiện 2 nút mới:
        🤖 AI  → kích hoạt gợi ý tại vị trí cursor
        ⚙     → mở trang cấu hình / test

   • Hotkey:
        Ctrl + Space   → gọi AI ngay tại cursor

   • Ghost-text (chữ mờ):
        • Xuất hiện sau cursor, màu xám in nghiêng
        • Tab   → chấp nhận gợi ý (chèn vào file)
        • Esc   → huỷ gợi ý
        • Gõ tiếp / di chuyển cursor → tự huỷ
        • Tự huỷ sau 30 giây nếu không thao tác

   • Fallback tự động:
        • Nếu gợi ý đến từ model dự phòng → toast vàng
          "Fallback: <model>"


8. BẢO MẬT & CHI PHÍ
───────────────────────────────────────────────────────────────
 • API key lưu tại:
     modules/ai_autocomplete/storage/config.json
   Nội dung (ví dụ):
     {
       "gemini_key":   "AIzaSy...",
       "deepseek_key": "sk-..."
     }
   → KHÔNG commit lên Git công khai
   → KHÔNG broadcast qua WebSocket
   → Chỉ trả về qua HTTP nội bộ

 • Cấu hình (provider, model, tokens, temp) lưu tại:
     modules/ai_autocomplete/data/settings.json
   → Đồng bộ với hệ thống settings core

 • Module KHÔNG có authentication:
   → Chỉ dùng trên localhost hoặc LAN tin cậy
   → KHÔNG mở port 8765 ra Internet công khai

 • Localhost mode:
   → Chỉ auto-setup khi Host header là localhost/127.x/::1
   → KHÔNG auto-setup khi truy cập qua domain/IP public

 • Chi phí DeepSeek:
   → Mỗi gợi ý ~500 – 2000 token
   → ~$0.14/1M input → 1$ ≈ 500 – 2000 lần gợi ý

 • Context gửi lên AI:
   → 2000 ký tự cuối TRƯỚC cursor
   → 600 ký tự đầu SAU cursor
   → Không gửi toàn bộ file, không gửi file khác


9. XỬ LÝ SỰ CỐ
───────────────────────────────────────────────────────────────
 ❌ "Chưa có xxx API key"
    → Chuyển sang tab provider đó, nhập key rồi lưu.

 ❌ "HTTP 400" (Gemini)
    → Key sai định dạng, hoặc model không tồn tại.
      Nếu vừa đổi sang model mới (vd: gemini-3.8-flash) mà
      Gemini chưa release → đổi về model khác trong UI.

 ❌ "HTTP 401" (DeepSeek)
    → Key sai hoặc đã bị xoá. Tạo key mới tại
      platform.deepseek.com/api_keys

 ❌ "HTTP 402" (DeepSeek)
    → Hết số dư tài khoản. Nạp thêm tại platform.deepseek.com

 ❌ "HTTP 403" (Gemini)
    → Key bị thu hồi / project bị chặn. Tạo key mới.

 ❌ "HTTP 429"
    → Rate limit:
        • Gemini free tier: đợi 1 phút, hoặc bật fallback
        • DeepSeek: thường không bị với autocomplete

 ❌ "HTTP 503"
    → Provider quá tải. Bật fallback trong UI.

 ❌ "Network: ..."
    → Server không có Internet / DNS / tường lửa.
      Kiểm tra:
        curl https://generativelanguage.googleapis.com
        curl https://api.deepseek.com

 ❌ Nút 🤖 AI không hiện trên toolbar
    → Overlay chưa load. Hard-reload: Ctrl+Shift+R
    → Kiểm tra URL không có ?safe=1
    → Settings → Overlays → safe_mode phải = false

 ❌ Ctrl+Space không hoạt động
    → Click chuột vào vùng editor trước (focus)
    → Một số OS đè hotkey — thử click nút 🤖 AI

 ❌ Không có gợi ý, toast "AI không có gợi ý"
    → Cursor đang ở đầu file (chưa có context).
      Gõ vài dòng trước cursor rồi thử lại.

 ❌ Cấu hình lưu nhưng không có tác dụng
    → Hard-reload trang (Ctrl+Shift+R)
    → Kiểm tra:
        cat modules/ai_autocomplete/data/settings.json

 ❌ Badge "🏠 Localhost" không hiện dù đang chạy localhost
    → Truy cập qua IP LAN (192.168.x.x) → đúng, chỉ localhost
      (127.x, ::1, localhost) mới hiện badge.
    → Nếu vẫn không hiện: proxy có thể rewrite Host header.


10. GỠ CÀI ĐẶT
───────────────────────────────────────────────────────────────
   • Tab Modules → click nút 🗑 cạnh ai_autocomplete
   • Storage + config.json (chứa cả 2 key) sẽ bị xoá theo
   • Không còn overlay, không còn route API


11. API REFERENCE (cho dev)
───────────────────────────────────────────────────────────────
 GET  /api/ai_autocomplete/info
      → {
          ok, version, author, copyright,
          has_key (bool cho provider hiện tại),
          has_keys: {gemini: bool, deepseek: bool},
          is_localhost: bool,     ← 🆕
          auto_setup: bool,        ← 🆕 (true nếu vừa tạo settings)
          provider, settings, storage
        }

 GET  /api/ai_autocomplete/models
      → {
          ok,
          catalog: {
            gemini: [{id, name, desc, badge, tier, free}, ...],
            deepseek: [{id, name, desc, badge, tier, free}, ...]
          },
          version
        }

 GET  /api/ai_autocomplete/help_install
      → {ok, filename: "help-install.txt", content}   ← nội dung này

 POST /api/ai_autocomplete/save_key
      body: {provider: "gemini"|"deepseek", api_key: "..."}
      → {ok, provider, message}

 POST /api/ai_autocomplete/save_config
      body: {
        values: {
          enabled: true,
          provider: "gemini",
          model_gemini: "gemini-3.8-flash",
          model_deepseek: "deepseek-chat",
          fallback_gemini: "gemini-3.5-flash-8b",
          fallback_deepseek: "deepseek-chat",
          max_tokens: 120,
          temperature: 0.3
        }
      }
      → {ok, message, settings, version}

 POST /api/ai_autocomplete/test
      body: {
        provider: "gemini"|"deepseek",
        api_key: "..." (tùy chọn — dùng khi chưa lưu),
        model: "..." (tùy chọn — mặc định dùng model đang cấu hình)
      }
      → {ok, provider, message, reply, model_used, version, copyright}

 POST /api/ai_autocomplete/complete
      body: {
        prefix:    "code before cursor",
        suffix:    "code after cursor",
        language:  "python" | "javascript" | ... ,
        filename:  "app.py"
      }
      → {
          ok, suggestion, version,
          provider, model_used,
          used_fallback
        }


12. LICENSE
───────────────────────────────────────────────────────────────
 Module này là phần mở rộng cho ACDV-Teams Coder.
 © ACDV-Teams — Educational / personal use.

 Không bán lại, không đóng gói vào sản phẩm thương mại mà
 không có sự đồng ý của ACDV-Teams.

 Google Gemini là thương hiệu của Google LLC.
 DeepSeek là thương hiệu của DeepSeek AI.
 Module chỉ gọi API công khai, không phân phối lại dịch vụ.

═══════════════════════════════════════════════════════════════
  Hết. Chúc bạn code vui vẻ!
  Mọi góp ý / báo lỗi: ACDV-Teams
═══════════════════════════════════════════════════════════════
"""


class Module(ModuleBase):
    # ── lifecycle ─────────────────────────────────────────
    def on_load(self):
        print(f"[{self.name}] v{VERSION} loaded — {COPYRIGHT}")
        try:
            self.engine.storage.storage_dir(self.name)
        except Exception:
            pass

    # ── localhost detection ───────────────────────────────
    def _is_localhost(self, req) -> bool:
        """Detect if the current request comes from localhost."""
        host = ""
        try:
            if isinstance(req, dict):
                host = (req.get("host") or
                        req.get("headers", {}).get("Host") or
                        req.get("headers", {}).get("host") or
                        req.get("remote_addr") or "")
        except Exception:
            pass

        host = str(host).strip().lower()
        if not host:
            return False

        if host.startswith("["):  # IPv6 with brackets
            host = host.split("]")[0] + "]"
        elif ":" in host:
            host = host.rsplit(":", 1)[0]

        if host in LOCAL_MARKERS:
            return True
        if host.startswith("127."):
            return True
        return False

    def _maybe_autosetup(self, is_localhost: bool) -> bool:
        """On localhost: create default settings.json if missing."""
        if not is_localhost:
            return False
        try:
            path = self._settings_path()
            if os.path.exists(path):
                return False
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULTS, f, indent=2, ensure_ascii=False)
            print(f"[{self.name}] localhost auto-setup: wrote default settings.json")
            return True
        except Exception as e:
            print(f"[{self.name}] auto-setup failed: {e}")
            return False

    # ── config helpers ────────────────────────────────────
    def _settings_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "settings.json")

    def _load_cfg(self) -> dict:
        try:
            data = self.engine.storage.read_file(self.name, "config.json")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            cfg = json.loads(data)
            if "api_key" in cfg and "gemini_key" not in cfg:
                cfg["gemini_key"] = cfg.pop("api_key")
            return cfg
        except Exception:
            return {}

    def _save_cfg(self, cfg: dict) -> bool:
        try:
            self.engine.storage.write_file(
                self.name, "config.json", json.dumps(cfg, indent=2)
            )
            return True
        except Exception as e:
            print(f"[{self.name}] save cfg error: {e}")
            return False

    def _key(self, provider: str) -> str:
        return (self._load_cfg().get(f"{provider}_key") or "").strip()

    def _default_model(self, provider: str) -> str:
        return DEFAULTS.get(f"model_{provider}") or next(iter(VALID_MODELS[provider]))

    # ── save settings ─────────────────────────────────────
    def _save_settings_direct(self, values: dict) -> bool:
        try:
            path = self._settings_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            existing = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}
            existing.update(values)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[{self.name}] direct settings write: {e}")
            return False

    def _save_settings(self, values: dict) -> bool:
        try:
            sm = getattr(self.engine, "settings", None)
            if sm is not None:
                for method in (
                    "set_module_settings", "set_module",
                    "update_module_settings", "update_module",
                    "save_module",
                ):
                    if hasattr(sm, method):
                        try:
                            getattr(sm, method)(self.name, values)
                            return True
                        except Exception as e:
                            print(f"[{self.name}] {method} failed: {e}")
        except Exception as e:
            print(f"[{self.name}] settings manager access: {e}")
        return self._save_settings_direct(values)

    # ── LLM calls ─────────────────────────────────────────
    def _call_gemini(self, prompt, model, max_tokens, temperature):
        key = self._key("gemini")
        if not key:
            return {"ok": False, "error": "Chưa có Gemini API key. Mở /module/ai_autocomplete/ để nhập."}

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": int(max_tokens),
                "temperature": float(temperature),
            },
        }
        url = GEMINI_URL.format(model=model, key=key)
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try: detail = e.read().decode("utf-8")
            except Exception: detail = str(e)
            return {"ok": False, "error": f"HTTP {e.code}", "code": e.code, "detail": detail[:800]}
        except urllib.error.URLError as e:
            return {"ok": False, "error": f"Network: {e.reason}"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

        cands = body.get("candidates") or []
        if not cands:
            return {"ok": False, "error": "Không có phản hồi", "raw": body}
        parts = (cands[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        return {"ok": True, "text": text, "model_used": model, "provider": "gemini"}

    def _call_deepseek(self, prompt, model, max_tokens, temperature):
        key = self._key("deepseek")
        if not key:
            return {"ok": False, "error": "Chưa có DeepSeek API key. Mở /module/ai_autocomplete/ để nhập."}

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "stream": False,
        }
        req = urllib.request.Request(
            DEEPSEEK_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try: detail = e.read().decode("utf-8")
            except Exception: detail = str(e)
            return {"ok": False, "error": f"HTTP {e.code}", "code": e.code, "detail": detail[:800]}
        except urllib.error.URLError as e:
            return {"ok": False, "error": f"Network: {e.reason}"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

        choices = body.get("choices") or []
        if not choices:
            return {"ok": False, "error": "Không có phản hồi", "raw": body}
        text = ((choices[0].get("message") or {}).get("content")) or ""
        return {"ok": True, "text": text, "model_used": model, "provider": "deepseek"}

    def _call_llm(self, provider, model, prompt, max_tokens, temperature):
        if provider == "deepseek":
            return self._call_deepseek(prompt, model, max_tokens, temperature)
        return self._call_gemini(prompt, model, max_tokens, temperature)

    def _call_with_fallback(self, prompt, settings):
        provider = settings.get("provider", "gemini")
        if provider not in VALID_MODELS:
            provider = "gemini"
        primary  = settings.get(f"model_{provider}", self._default_model(provider))
        fallback = settings.get(f"fallback_{provider}", "") or ""
        max_tok  = int(settings.get("max_tokens", 120))
        temp     = float(settings.get("temperature", 0.3))

        result = self._call_llm(provider, primary, prompt, max_tok, temp)
        if result.get("ok"):
            return result

        code = result.get("code")
        should_try_fb = (
            fallback and fallback != primary
            and fallback in VALID_MODELS[provider]
            and (code in (429, 503) or "quota" in str(result.get("error", "")).lower())
        )
        if should_try_fb:
            print(f"[{self.name}] primary '{primary}' failed ({result.get('error')}) — trying fallback: {fallback}")
            fb = self._call_llm(provider, fallback, prompt, max_tok, temp)
            if fb.get("ok"):
                fb["used_fallback"] = True
                fb["primary_error"] = result.get("error")
                return fb
        return result

    # ── helpers ───────────────────────────────────────────
    @staticmethod
    def _strip_fence(text: str) -> str:
        t = (text or "").strip()
        if t.startswith("```"):
            lines = t.split("\n")[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            t = "\n".join(lines)
        return t.strip("\n")

    # ── routes ────────────────────────────────────────────
    def info(self, req):
        is_local = self._is_localhost(req)
        auto_setup = self._maybe_autosetup(is_local)

        settings = self.get_settings()
        cfg = self._load_cfg()
        try:
            usage = self.engine.storage.usage(self.name)
        except Exception:
            usage = {}
        has_keys = {
            "gemini":   bool((cfg.get("gemini_key")   or "").strip()),
            "deepseek": bool((cfg.get("deepseek_key") or "").strip()),
        }
        current = settings.get("provider", "gemini")
        return {
            "ok": True,
            "version": VERSION,
            "author": AUTHOR,
            "copyright": COPYRIGHT,
            "has_key": has_keys.get(current, False),
            "has_keys": has_keys,
            "is_localhost": is_local,
            "auto_setup": auto_setup,
            "provider": current,
            "settings": settings,
            "storage": usage,
        }

    def models(self, req):
        return {"ok": True, "catalog": MODEL_CATALOG, "version": VERSION}

    def help_install(self, req):
        return {"ok": True, "filename": "help-install.txt", "content": HELP_TEXT}

    def save_key(self, req):
        provider = (req.get("provider") or "gemini").lower()
        if provider not in VALID_MODELS:
            return {"ok": False, "error": f"Provider không hợp lệ: {provider}"}

        key = (req.get("api_key") or "").strip()
        if not key:
            return {"ok": False, "error": "API key trống"}
        if len(key) < 20:
            return {"ok": False, "error": "API key quá ngắn (Gemini ~39 ký tự, DeepSeek ~35 ký tự)"}

        cfg = self._load_cfg()
        cfg[f"{provider}_key"] = key
        ok = self._save_cfg(cfg)
        return {
            "ok": ok,
            "provider": provider,
            "message": f"Đã lưu {provider} API key" if ok else "Lưu thất bại",
        }

    def save_config(self, req):
        values = req.get("values", {})
        if not isinstance(values, dict):
            return {"ok": False, "error": "values phải là dict"}

        clean = {}
        for k, v in values.items():
            if k not in ALLOWED_KEYS:
                continue
            if k == "enabled":
                clean[k] = bool(v)
            elif k == "provider":
                if v in VALID_MODELS:
                    clean[k] = v
            elif k in ("model_gemini", "model_deepseek", "fallback_gemini", "fallback_deepseek"):
                if k.startswith("model_"):
                    p = k.split("_", 1)[1]
                    if v in VALID_MODELS[p]:
                        clean[k] = v
                else:
                    p = k.split("_", 1)[1]
                    if v == "" or v in VALID_MODELS[p]:
                        clean[k] = v
            elif k == "max_tokens":
                try:
                    n = int(v)
                    if 20 <= n <= 800:
                        clean[k] = n
                except Exception:
                    pass
            elif k == "temperature":
                try:
                    t = float(v)
                    if 0.0 <= t <= 1.0:
                        clean[k] = round(t, 2)
                except Exception:
                    pass

        if not clean:
            return {"ok": False, "error": "Không có giá trị hợp lệ"}

        ok = self._save_settings(clean)
        return {
            "ok": ok,
            "message": "Đã lưu cấu hình" if ok else "Lưu thất bại",
            "settings": self.get_settings(),
            "version": VERSION,
        }

    def test_api(self, req):
        settings = self.get_settings()
        provider = (req.get("provider") or settings.get("provider", "gemini")).lower()
        if provider not in VALID_MODELS:
            provider = "gemini"

        incoming = (req.get("api_key") or "").strip()
        if incoming and len(incoming) >= 20:
            cfg = self._load_cfg()
            cfg[f"{provider}_key"] = incoming
            self._save_cfg(cfg)

        if not self._key(provider):
            return {"ok": False, "error": f"Chưa có {provider} API key. Nhập ở ô trên và bấm Test."}

        model = req.get("model") or settings.get(f"model_{provider}", self._default_model(provider))
        if model not in VALID_MODELS[provider]:
            model = self._default_model(provider)

        result = self._call_llm(provider, model, "Reply with exactly one word: OK", 20, 0.0)
        if not result.get("ok"):
            return {
                "ok": False,
                "provider": provider,
                "error": result.get("error", "Unknown"),
                "detail": result.get("detail") or result.get("raw"),
            }
        reply = (result.get("text") or "").strip()
        return {
            "ok": True,
            "provider": provider,
            "message": f"{provider} API hoạt động (model: {model})",
            "reply": reply[:120],
            "model_used": model,
            "version": VERSION,
            "copyright": COPYRIGHT,
        }

    def complete(self, req):
        settings = self.get_settings()
        if not settings.get("enabled", True):
            return {"ok": False, "error": "Module đang tắt trong Settings"}

        prefix   = req.get("prefix", "") or ""
        suffix   = req.get("suffix", "") or ""
        language = req.get("language", "text") or "text"
        filename = req.get("filename", "") or ""

        if not prefix.strip():
            return {"ok": False, "error": "Cần code trước cursor để gợi ý"}

        prefix = prefix[-2000:]
        suffix = suffix[:600]

        prompt = (
            f"You are a code-autocomplete engine for {language}.\n"
            f"Complete the code naturally starting EXACTLY at the cursor.\n"
            f"Return ONLY the continuation code — no markdown fences, "
            f"no backticks, no explanation, no repetition of existing code.\n\n"
            f"File: {filename or '(unknown)'}   Language: {language}\n\n"
            f"<<<CODE BEFORE CURSOR>>>\n{prefix}\n<<<CURSOR HERE>>>\n"
            f"<<<CODE AFTER CURSOR>>>\n{suffix}\n<<<END>>>\n\n"
            f"Continuation:"
        )

        result = self._call_with_fallback(prompt, settings)
        if not result.get("ok"):
            return result

        suggestion = self._strip_fence(result.get("text", ""))
        if not suggestion:
            return {"ok": False, "error": "AI không có gợi ý"}
        return {
            "ok": True,
            "suggestion": suggestion,
            "version": VERSION,
            "provider": result.get("provider"),
            "model_used": result.get("model_used"),
            "used_fallback": bool(result.get("used_fallback")),
        }