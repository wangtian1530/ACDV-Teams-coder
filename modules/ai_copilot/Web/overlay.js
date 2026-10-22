 (function() {
    console.log("[AI Copilot] Overlay loaded.");

    // Chờ hệ thống editor sẵn sàng
    window.addEventListener("DOMContentLoaded", () => {
        setTimeout(initAICopilot, 1000);
    });

    function initAICopilot() {
        // Kiểm tra xem global app hoặc editor đã sẵn sàng chưa
        if (!window.app || !window.app.editor || !window.app.editor.cm) {
            setTimeout(initAICopilot, 500);
            return;
        }

        const cm = window.app.editor.cm;
        let suggestionWidget = null;
        let currentSuggestionText = "";

        // Thêm nút trigger AI nhanh trên thanh toolbar nếu muốn, hoặc dùng phím tắt Ctrl + Space
        cm.on("keyHandled", (instance, name, e) => {
            // Có thể tuỳ biến phím tắt ở đây
        });

        // Lắng nghe sự kiện nhấn phím Tab đểAccept gợi ý khi đang hiện ghost text, 
        // hoặc nhấn Ctrl + Space để gọi gợi ý AI
        document.addEventListener("keydown", async (e) => {
            // Nhấn Ctrl + Space để yêu cầu AI gợi ý dòng code tiếp theo
            if (e.ctrlKey && e.code === "Space") {
                e.preventDefault();
                await triggerAISuggestion(cm);
            }
        });
    }

    async function triggerAISuggestion(cm) {
        const cursor = cm.getCursor();
        const codePrefix = cm.getRange({line: 0, ch: 0}, cursor);
        const codeSuffix = cm.getRange(cursor, {line: cm.lastLine(), ch: null});
        const mode = cm.getMode().name || "text";

        // Hiển thị thông báo đang load nhẹ nhàng góc màn hình
        showToast("🤖 AI đang suy nghĩ...");

        try {
            const resp = await fetch("/api/ai_copilot/suggest", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    prefix: codePrefix,
                    suffix: codeSuffix,
                    language: mode
                })
            });
            const data = await resp.json();
            
            if (data.ok && data.suggestion) {
                // Chèn trực tiếp đoạn code gợi ý vào vị trí con trỏ hiện tại
                cm.replaceRange(data.suggestion, cursor);
                showToast("✨ Đã hoàn tất gợi ý AI!");
            } else {
                showToast("⚠️ AI: " + (data.error || "Không có gợi ý phù hợp."));
            }
        } catch (err) {
            console.error("AI Copilot request failed:", err);
            showToast("❌ Lỗi kết nối tới AI module.");
        }
    }

    function showToast(msg) {
        let toast = document.getElementById("ai-toast-notification");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "ai-toast-notification";
            toast.style.cssText = "position:fixed; bottom:20px; right:20px; background:#222; color:#0f0; padding:8px 16px; border-radius:4px; z-index:9999; font-size:13px; border: 1px solid #0f0; box-shadow: 0 4px 6px rgba(0,0,0,0.3);";
            document.body.appendChild(toast);
        }
        toast.innerText = msg;
        toast.style.display = "block";
        setTimeout(() => {
            toast.style.display = "none";
        }, 3000);
    }
})();
