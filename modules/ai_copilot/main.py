import json
import urllib.request
import urllib.error
from core.loader import ModuleBase

class Module(ModuleBase):
    def on_load(self):
        print(f"[{self.name}] AI Copilot module loaded successfully.")

    def suggest_code(self, req):
        """Handler nhận context từ editor và gọi Google Gemini Free API"""
        body = req.get("body", {})
        code_prefix = body.get("prefix", "")
        code_suffix = body.get("suffix", "")
        language = body.get("language", "python")

        settings = self.get_settings()
        if not settings.get("enabled", True):
            return {"ok": False, "error": "AI Copilot đang bị tắt trong cài đặt."}

        api_key = settings.get("api_key", "").strip()
        if not api_key:
            return {"ok": False, "error": "Chưa cấu hình Gemini API Key trong Settings!"}

        model = settings.get("model", "gemini-2.5-flash")
        
        # Xây dựng prompt dạng FIM (Fill-in-the-Middle) cho AI hiểu ngữ cảnh viết code
        prompt = f"""You are an AI coding assistant like GitHub Copilot. Complete the code naturally.
Language: {language}
Prefix (code before cursor):
Rules:
1. Return ONLY the raw code snippet that should be inserted at the cursor.
2. Do NOT wrap the response in markdown code blocks (like ```python ... ```).
3. Keep it concise and continuation-focused.
"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 150
            }
        }

        req_data = json.dumps(payload).encode("utf-8")
        http_req = urllib.request.Request(
            url, 
            data=req_data, 
            headers={"Content-Type": "application/json"}, 
            method="POST"
        )

        try:
            with urllib.request.urlopen(http_req, timeout=10) as response:
                res_body = json.loads(response.read().decode("utf-8"))
                # Trích xuất text từ response chuẩn của Gemini API
                candidates = res_body.get("candidates", [])
                if not candidates:
                    return {"ok": True, "suggestion": ""}
                
                content_parts = candidates[0].get("content", {}).get("parts", [])
                suggestion = "".join([p.get("text", "") for p in content_parts])
                
                # Dọn dẹp markdown thừa nếu lỡ model trả về
                suggestion = suggestion.strip()
                if suggestion.startswith("```"):
                    lines = suggestion.split("\n")
                    suggestion = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

                return {"ok": True, "suggestion": suggestion}

        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            return {"ok": False, "error": f"Gemini API Error: {err_msg}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}