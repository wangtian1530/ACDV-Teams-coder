#!/usr/bin/env python3
"""Termux bridge client — connect to ACDV Coder from your phone."""
import os
import sys
import json
import socket
import struct
import base64
import threading


def _connect(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((
        f"GET /ws HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        c = sock.recv(4096)
        if not c:
            raise RuntimeError("handshake failed")
        buf += c
    if b"101" not in buf.split(b"\r\n")[0]:
        raise RuntimeError(f"handshake rejected: {buf[:100]!r}")
    return sock


def _send(sock, payload):
    data = payload.encode("utf-8")
    n = len(data)
    mask = os.urandom(4)
    frame = bytearray([0x81])
    if n < 126:
        frame.append(0x80 | n)
    elif n < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", n))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", n))
    frame.extend(mask)
    frame.extend(bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
    sock.sendall(bytes(frame))


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c:
            return None
        buf += c
    return buf


def _recv(sock):
    h = _recv_exact(sock, 2)
    if not h:
        return None
    opcode = h[0] & 0x0F
    ln = h[1] & 0x7F
    if ln == 126:
        ln = struct.unpack(">H", _recv_exact(sock, 2))[0]
    elif ln == 127:
        ln = struct.unpack(">Q", _recv_exact(sock, 8))[0]
    payload = _recv_exact(sock, ln) if ln else b""
    return opcode, payload


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765

    print(f"→ connecting ws://{host}:{port}")
    sock = _connect(host, port)
    print("✓ connected · type JSON commands (or 'quit')")

    def reader():
        while True:
            f = _recv(sock)
            if not f:
                print("\n[!] server closed")
                os._exit(0)
            op, payload = f
            if op == 0x1:
                try:
                    obj = json.loads(payload.decode("utf-8"))
                    print(f"\n<< {json.dumps(obj, ensure_ascii=False, indent=2)}")
                except Exception:
                    print(f"\n<< {payload.decode('utf-8', errors='replace')}")
            elif op == 0x8:
                print("\n[!] server sent close")
                os._exit(0)

    threading.Thread(target=reader, daemon=True).start()

    # Sample commands list
    print("""
Examples:
  {"type":"status"}
  {"type":"modules"}
  {"type":"route","id":1,"method":"GET","path":"/api/tasks"}
  {"type":"route","id":2,"method":"POST","path":"/api/tasks/add","body":{"text":"hello"}}
""")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line in ("quit", "exit", "/quit"):
            break
        try:
            obj = json.loads(line)
        except Exception:
            obj = {"type": "ping", "time": line}
        _send(sock, json.dumps(obj))
        print(f">> {json.dumps(obj, ensure_ascii=False)}")


if __name__ == "__main__":
    main()