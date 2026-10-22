"""HTTP + WebSocket server written from scratch on raw sockets.

v1.3.2:
  - Terminal over WebSocket (`terminal_open`, `terminal_input`,
    `terminal_resize`, `terminal_close`).
  - Auto close terminals owned by a disconnected ws.
"""
import os
import struct
import time
import json
import socket
import base64
import hashlib
import mimetypes
import threading
import urllib.parse
import traceback

WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketConnection:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.closed = False
        self._send_lock = threading.Lock()

    def send_text(self, text):
        if self.closed:
            return
        try:
            with self._send_lock:
                self._send_frame(0x1, text.encode("utf-8"))
        except Exception:
            self.closed = True

    def send_json(self, obj):
        self.send_text(json.dumps(obj, ensure_ascii=False))

    def _send_frame(self, opcode, payload):
        length = len(payload)
        frame = bytearray([0x80 | opcode])
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.extend(struct.pack(">H", length))
        else:
            frame.append(127)
            frame.extend(struct.pack(">Q", length))
        frame.extend(payload)
        self.sock.sendall(bytes(frame))

    def recv_frame(self):
        try:
            header = self._recv_exact(2)
            if not header:
                return None
            opcode = header[0] & 0x0F
            masked = (header[1] & 0x80) != 0
            length = header[1] & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if masked else None
            payload = self._recv_exact(length) if length > 0 else b""
            if masked and mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            return opcode, payload
        except Exception:
            return None

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def close(self):
        if self.closed:
            return
        self.closed = True
        try: self._send_frame(0x8, b"")
        except Exception: pass
        try: self.sock.close()
        except Exception: pass


class HttpWsServer:
    def __init__(self, host, port, engine):
        self.host = host
        self.port = port
        self.engine = engine
        self.frontend_dir = os.path.join(engine.base_dir, "frontend")
        self.sock = None
        self.running = False
        self.ws_clients = []
        self.ws_lock = threading.Lock()

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(64)
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        print(f"[Server] ✓ listening on http://{self.host}:{self.port}")

    def stop(self):
        self.running = False
        try: self.sock.close()
        except Exception: pass

    def _accept_loop(self):
        while self.running:
            try:
                client, addr = self.sock.accept()
                threading.Thread(target=self._handle_client,
                                 args=(client, addr), daemon=True).start()
            except Exception:
                if not self.running:
                    break

    def _handle_client(self, client, addr):
        try:
            client.settimeout(60)
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = client.recv(4096)
                if not chunk:
                    client.close(); return
                data += chunk
                if len(data) > 2 * 1024 * 1024:
                    client.close(); return

            header_data, _, body = data.partition(b"\r\n\r\n")
            lines = header_data.decode("utf-8", errors="replace").split("\r\n")
            if not lines or len(lines[0].split(" ")) < 3:
                client.close(); return

            method, path, _version = lines[0].split(" ", 2)
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            if headers.get("upgrade", "").lower() == "websocket":
                self._handle_websocket(client, headers)
                return

            clen = int(headers.get("content-length", "0") or "0")
            while len(body) < clen:
                chunk = client.recv(4096)
                if not chunk:
                    break
                body += chunk

            status, resp_headers, resp_body = self._handle_http(method, path, headers, body)
            out = f"HTTP/1.1 {status}\r\n"
            for k, v in resp_headers.items():
                out += f"{k}: {v}\r\n"
            out += f"Content-Length: {len(resp_body)}\r\n"
            out += "Connection: close\r\n\r\n"
            client.sendall(out.encode("utf-8") + resp_body)
            client.close()
        except Exception:
            try: client.close()
            except Exception: pass

    def _handle_http(self, method, path, headers, body):
        parsed = urllib.parse.urlparse(path)
        route_path = parsed.path
        if route_path.startswith("/api/"):
            handler = self.engine.router.match(method, route_path)
            if not handler:
                return ("404 Not Found",
                        {"Content-Type": "application/json"},
                        b'{"error":"route not found"}')
            req_data = {}
            try:
                if body:
                    try:
                        req_data = json.loads(body.decode("utf-8"))
                    except Exception:
                        req_data = {"raw": body.decode("utf-8", errors="replace")}
                if not isinstance(req_data, dict):
                    req_data = {"data": req_data}
                req_data["_method"] = method
                req_data["_path"] = route_path
                req_data["_query"] = urllib.parse.parse_qs(parsed.query)
                req_data["_headers"] = headers
                result = handler(req_data)
                return ("200 OK",
                        {"Content-Type": "application/json; charset=utf-8"},
                        json.dumps(result, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                traceback.print_exc()
                handled = None
                try:
                    handled = self.engine.dispatch_error({
                        "source": "http",
                        "method": method,
                        "path": route_path,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "request": req_data,
                    })
                except Exception:
                    pass
                if handled is not None:
                    try:
                        return ("200 OK",
                                {"Content-Type": "application/json; charset=utf-8"},
                                json.dumps(handled, ensure_ascii=False).encode("utf-8"))
                    except Exception:
                        pass
                return ("500 Internal Server Error",
                        {"Content-Type": "application/json"},
                        json.dumps({"error": str(e)}).encode("utf-8"))
        if route_path.startswith("/module/"):
            return self._serve_module_asset(route_path)
        return self._serve_static(route_path)

    def _serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        rel = path.lstrip("/")
        frontend_abs = os.path.abspath(self.frontend_dir)
        target = os.path.abspath(os.path.join(frontend_abs, rel))
        if target != frontend_abs and not target.startswith(frontend_abs + os.sep):
            return ("403 Forbidden", {"Content-Type": "text/plain"}, b"forbidden")
        if not os.path.isfile(target):
            return ("404 Not Found", {"Content-Type": "text/plain"}, b"not found")
        mime, _ = mimetypes.guess_type(target)
        mime = mime or "application/octet-stream"
        with open(target, "rb") as f:
            content = f.read()
        return ("200 OK", {"Content-Type": mime}, content)

    def _serve_module_asset(self, path):
        parts = path.split("/", 3)
        if len(parts) < 3 or not parts[2]:
            return ("400 Bad Request", {"Content-Type": "text/plain"}, b"bad module path")
        module_name = parts[2]
        rest = parts[3] if len(parts) > 3 else ""
        if "/" in module_name or "\\" in module_name or module_name in (".", ".."):
            return ("400 Bad Request", {"Content-Type": "text/plain"}, b"bad module name")
        if module_name not in self.engine.modules:
            return ("404 Not Found", {"Content-Type": "text/plain"}, b"module not found")

        source = "web"
        if rest.startswith("_data_/"):
            source = "data"
            rest = rest[len("_data_/"):]

        source_dir = os.path.join(self.engine.base_dir, "modules", module_name, source)
        if not os.path.isdir(source_dir):
            return ("404 Not Found", {"Content-Type": "text/plain"},
                    b"no " + source.encode() + b" dir")

        rel = rest or "index.html"
        if "?" in rel:
            rel = rel.split("?", 1)[0]
        if not rel:
            rel = "index.html"
        if ".." in rel.replace("\\", "/").split("/"):
            return ("403 Forbidden", {"Content-Type": "text/plain"}, b"forbidden")

        source_abs = os.path.abspath(source_dir)
        target = os.path.abspath(os.path.join(source_abs, rel))
        if target != source_abs and not target.startswith(source_abs + os.sep):
            return ("403 Forbidden", {"Content-Type": "text/plain"}, b"forbidden")
        if os.path.isdir(target):
            target = os.path.join(target, "index.html")
        if not os.path.isfile(target):
            return ("404 Not Found", {"Content-Type": "text/plain"}, b"not found")

        mime, _ = mimetypes.guess_type(target)
        mime = mime or "application/octet-stream"
        with open(target, "rb") as f:
            content = f.read()
        return ("200 OK", {"Content-Type": mime}, content)

    def _handle_websocket(self, client, headers):
        key = headers.get("sec-websocket-key")
        if not key:
            client.close(); return
        accept = base64.b64encode(
            hashlib.sha1((key + WS_MAGIC).encode()).digest()
        ).decode()

        try:
            if os.name == "posix":
                import struct as _st
                tv = _st.pack("ll", 3, 0)
                client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, tv)
        except Exception:
            pass
        try:
            client.settimeout(120)
        except Exception:
            pass

        client.sendall((
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        ).encode())

        ws = WebSocketConnection(client, client.getpeername())
        with self.ws_lock:
            self.ws_clients.append(ws)
        print(f"[WS] + {ws.addr}  (clients: {len(self.ws_clients)})")

        try:
            while not ws.closed:
                frame = ws.recv_frame()
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:
                    break
                elif opcode == 0x9:
                    try: ws._send_frame(0xA, payload)
                    except Exception: break
                elif opcode == 0x1:
                    self._handle_ws_message(ws, payload.decode("utf-8", errors="replace"))
        except Exception as e:
            print(f"[WS] error: {e}")
        finally:
            with self.ws_lock:
                if ws in self.ws_clients:
                    self.ws_clients.remove(ws)
                no_clients = len(self.ws_clients) == 0
            ws.close()
            print(f"[WS] - {ws.addr}  (clients: {len(self.ws_clients)})")

            # ⭐ v1.3.2: kill terminals owned by this ws
            try:
                if hasattr(self.engine, "terminal"):
                    self.engine.terminal.close_by_ws(ws)
            except Exception as e:
                print(f"[WS] terminal cleanup error: {e}")

            if no_clients and self.engine.config.get("auto_stop_on_disconnect", True):
                threading.Thread(
                    target=self._auto_stop_after_grace, daemon=True
                ).start()

    def _auto_stop_after_grace(self):
        time.sleep(5)
        with self.ws_lock:
            if self.ws_clients:
                return
        try:
            st = self.engine.runner.status()
            if st.get("running"):
                print("[WS] no clients — auto-stopping running process")
                self.engine.runner.stop(force=False)
        except Exception:
            pass

    def _handle_ws_message(self, ws, text):
        try:
            msg = json.loads(text)
            if not isinstance(msg, dict):
                raise ValueError
        except Exception:
            ws.send_json({"type": "error", "error": "invalid json"}); return

        mtype = msg.get("type")

        if mtype == "ping":
            ws.send_json({"type": "pong", "time": msg.get("time")})

        elif mtype == "status":
            ws.send_json({
                "type": "status",
                "data": {
                    "modules": list(self.engine.modules.keys()),
                    "running": self.engine.running,
                    "clients": len(self.ws_clients),
                    "runner": self.engine.runner.status(),
                    "settings": self.engine.settings.get_global(),
                    "terminals": len(self.engine.terminal.sessions),
                },
            })

        elif mtype == "modules":
            info = {n: m.metadata for n, m in self.engine.modules.items()}
            ws.send_json({"type": "modules", "data": info})

        elif mtype == "settings":
            ws.send_json({"type": "settings", "data": self.engine.settings.get_global()})

        elif mtype == "module_settings":
            name = msg.get("module")
            if name and name in self.engine.modules:
                ws.send_json({
                    "type": "module_settings",
                    "module": name,
                    "data": self.engine.get_module_settings(name),
                })
            else:
                ws.send_json({"type": "error", "error": "module not found"})

        elif mtype == "route":
            method = msg.get("method", "GET")
            rpath = msg.get("path", "/")
            body = msg.get("body") or {}
            msg_id = msg.get("id")
            handler = self.engine.router.match(method, rpath)
            if not handler:
                ws.send_json({"type": "route_result", "id": msg_id,
                              "ok": False, "error": "route not found"}); return
            req = dict(body) if isinstance(body, dict) else {}
            try:
                req["_method"] = method
                req["_path"] = rpath
                req["_via"] = "ws"
                result = handler(req)
                ws.send_json({"type": "route_result", "id": msg_id, "ok": True, "data": result})
            except Exception as e:
                traceback.print_exc()
                handled = None
                try:
                    handled = self.engine.dispatch_error({
                        "source": "ws_route",
                        "method": method,
                        "path": rpath,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "request": req,
                    })
                except Exception:
                    pass
                if handled is not None:
                    ws.send_json({"type": "route_result", "id": msg_id,
                                  "ok": True, "data": handled})
                else:
                    ws.send_json({"type": "route_result", "id": msg_id,
                                  "ok": False, "error": str(e)})

        elif mtype == "module_action":
            module_name = msg.get("module")
            button_id = msg.get("button_id")
            params = msg.get("params") or {}
            module = self.engine.modules.get(module_name)
            if not module:
                ws.send_json({"type": "module_action_result",
                              "module": module_name, "button_id": button_id,
                              "ok": False, "error": "module not loaded"}); return
            handler = getattr(module, f"on_button_{button_id}", None)
            if not handler:
                ws.send_json({"type": "module_action_result",
                              "module": module_name, "button_id": button_id,
                              "ok": False,
                              "error": f"handler on_button_{button_id} not found"}); return
            try:
                result = handler(params)
                ws.send_json({"type": "module_action_result",
                              "module": module_name, "button_id": button_id,
                              "ok": True, "result": result})
            except Exception as e:
                traceback.print_exc()
                handled = None
                try:
                    handled = self.engine.dispatch_error({
                        "source": "ws_action",
                        "module": module_name,
                        "button_id": button_id,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "params": params,
                    })
                except Exception:
                    pass
                if handled is not None:
                    ws.send_json({"type": "module_action_result",
                                  "module": module_name, "button_id": button_id,
                                  "ok": True, "result": handled})
                else:
                    ws.send_json({"type": "module_action_result",
                                  "module": module_name, "button_id": button_id,
                                  "ok": False, "error": str(e)})

        # ⭐ v1.3.2: terminal WS protocol
        elif mtype == "terminal_open":
            term_id = msg.get("id")
            if not term_id:
                ws.send_json({"type": "terminal_error", "id": None,
                              "error": "missing terminal id"}); return
            try:
                cols = int(msg.get("cols", 80) or 80)
                rows = int(msg.get("rows", 24) or 24)
                cwd_hint = msg.get("cwd")
                self.engine.terminal.open(
                    term_id, ws, cols=cols, rows=rows, cwd_hint=cwd_hint,
                )
                ws.send_json({"type": "terminal_opened", "id": term_id})
            except Exception as e:
                ws.send_json({"type": "terminal_error", "id": term_id,
                              "error": str(e)})

        elif mtype == "terminal_input":
            term_id = msg.get("id")
            data = msg.get("data") or ""
            if term_id and isinstance(data, str):
                self.engine.terminal.write(term_id, data)

        elif mtype == "terminal_resize":
            term_id = msg.get("id")
            if term_id:
                try:
                    cols = int(msg.get("cols", 80) or 80)
                    rows = int(msg.get("rows", 24) or 24)
                    self.engine.terminal.resize(term_id, cols, rows)
                except Exception:
                    pass

        elif mtype == "terminal_close":
            term_id = msg.get("id")
            if term_id:
                self.engine.terminal.close(term_id)

        else:
            ws.send_json({"type": "error", "error": f"unknown type: {mtype}"})

    def broadcast(self, obj):
        with self.ws_lock:
            clients = list(self.ws_clients)
        for ws in clients:
            try:
                ws.send_json(obj)
            except Exception:
                pass