import json, threading, time, os, atexit
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from config import SUBSTEP_MS, SPEED_MULT
from engine import Game, save_learning, load_learning

BROADCAST_HZ = 30


class GameServer:
    def __init__(self):
        self.game = Game()
        load_learning(self.game.bots)
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.speed = 2                       # x2 = normal by default
        self.version = 0
        self.paused = False

    def loop(self):
        last_broadcast = 0
        while True:
            with self.cond:
                if not self.paused and not self.game.over:
                    self.game.substep()
                    self.version += 1
                now = time.time()
                if now - last_broadcast >= 1.0 / BROADCAST_HZ:
                    self.cond.notify_all()
                    last_broadcast = now
            mult = SPEED_MULT.get(self.speed, 1.0)
            sleep = (SUBSTEP_MS / 1000.0) / mult
            time.sleep(max(0.001, sleep))

    def wait_update(self, last_v):
        with self.cond:
            while self.version == last_v:
                self.cond.wait()
            return self.version, self.game.state_json()

    def set_speed(self, s):
        with self.lock:
            self.speed = max(1, min(5, int(s)))

    def rewind(self):
        with self.lock:
            return self.game.rewind()

    def toggle_pause(self):
        with self.lock:
            self.paused = not self.paused
            return self.paused

    def reset(self):
        with self.lock:
            old_q = [b.q for b in self.game.bots]
            save_learning(self.game.bots)
            self.game = Game()
            for i, b in enumerate(self.game.bots):
                if i < len(old_q):
                    b.q = old_q[i]
            self.version += 1
            self.cond.notify_all()

    def get_state(self):
        with self.lock:
            return self.game.state_json()


server = GameServer()
atexit.register(lambda: save_learning(server.game.bots))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path):
        sd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        fp = os.path.abspath(os.path.join(sd, path))
        if not fp.startswith(os.path.abspath(sd)) or not os.path.isfile(fp):
            self.send_error(404); return
        with open(fp, 'rb') as f:
            data = f.read()
        ext = path.rsplit('.', 1)[-1]
        mime = {'html': 'text/html; charset=utf-8',
                'js': 'application/javascript',
                'css': 'text/css'}.get(ext, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ('/', '/index.html'):
            self._file('index.html')
        elif p.startswith('/static/'):
            self._file(p[len('/static/'):])
        elif p == '/api/state':
            self._json(server.get_state())
        elif p == '/api/stream':
            self._stream()
        else:
            self.send_error(404)

    def _stream(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        last = -1
        try:
            while True:
                v, st = server.wait_update(last)
                self.wfile.write(f'data: {json.dumps(st)}\n\n'.encode())
                self.wfile.flush()
                last = v
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        u = urlparse(self.path)
        p, qs = u.path, parse_qs(u.query)
        if p == '/api/speed':
            server.set_speed(qs.get('m', ['2'])[0])
            self._json({'ok': True, 'speed': server.speed})
        elif p == '/api/rewind':
            self._json({'ok': server.rewind()})
        elif p == '/api/reset':
            server.reset()
            self._json({'ok': True})
        elif p == '/api/pause':
            self._json({'ok': True, 'paused': server.toggle_pause()})
        else:
            self.send_error(404)


def main():
    port = 8000
    threading.Thread(target=server.loop, daemon=True).start()
    print(f'🌐 Server: http://localhost:{port}')
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()


if __name__ == '__main__':
    main()