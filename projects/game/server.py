"""
Snake.io Tết Đinh Mùi 2027 🧧 - HTTP Server
Chạy: python server.py
Mở:  http://localhost:8000
"""
import http.server
import socketserver
import os
print('ACDV-Teams')
PORT = 8000
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("=" * 55)
        print(f"  🧧  SNAKE.IO TẾT ĐINH MÙI 2027: http://localhost:{PORT}")
        print(f"  📁  {DIRECTORY}")
        print("  ⏹   Ctrl+C để dừng")
        print("=" * 55)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Xuân Bình An · Vạn Sự Như Ý")


if __name__ == "__main__":
    main()