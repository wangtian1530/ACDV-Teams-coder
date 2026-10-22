"""Terminal session manager — spawn shell with PTY (POSIX) or pipes (Windows).

v1.3.2:
  - Mỗi session gắn với một WebSocket cụ thể (ws), output chỉ gửi cho client đó.
  - Auto cleanup khi WS disconnect.
  - Hỗ trợ resize (TIOCSWINSZ + SIGWINCH).
"""
import os
import subprocess
import threading

try:
    import pty
    import termios
    import fcntl
    import struct
    HAS_PTY = True
except ImportError:
    HAS_PTY = False


class TerminalSession:
    def __init__(self, term_id, engine, ws, cols=80, rows=24, cwd=None):
        self.id = term_id
        self.engine = engine
        self.ws = ws
        self.cols = cols
        self.rows = rows
        self.cwd = cwd or engine.base_dir
        self.proc = None
        self.master_fd = None
        self.reader_thread = None
        self.closed = False
        self.lock = threading.Lock()

    def start(self):
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["PYTHONUNBUFFERED"] = "1"

        shell = ((self.engine.config.get("terminal") or {}).get("shell")
                 or env.get("SHELL") or "/bin/bash")

        if HAS_PTY:
            self.master_fd, slave_fd = pty.openpty()
            self._set_winsize(self.master_fd, self.rows, self.cols)
            kwargs = dict(
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                cwd=self.cwd, env=env, close_fds=True,
            )
            if os.name == "posix":
                kwargs["start_new_session"] = True
            self.proc = subprocess.Popen([shell, "-i"], **kwargs)
            try:
                os.close(slave_fd)
            except Exception:
                pass
        else:
            self.proc = subprocess.Popen(
                [shell],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.cwd, env=env, bufsize=0,
            )

        self.reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True,
        )
        self.reader_thread.start()

    def _set_winsize(self, fd, rows, cols):
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            pass

    def _reader_loop(self):
        try:
            if HAS_PTY and self.master_fd is not None:
                while not self.closed:
                    try:
                        data = os.read(self.master_fd, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    self._broadcast(data)
            else:
                while not self.closed:
                    try:
                        data = self.proc.stdout.read(4096)
                    except Exception:
                        break
                    if not data:
                        break
                    self._broadcast(data)
        except Exception as e:
            print(f"[Terminal:{self.id}] reader error: {e}")
        finally:
            code = self.proc.poll()
            if code is None:
                try:
                    self.proc.wait(timeout=1)
                    code = self.proc.returncode
                except Exception:
                    code = -1
            self._send({"type": "terminal_exit", "id": self.id, "code": code})

    def _send(self, payload):
        try:
            ws = getattr(self, "ws", None)
            if ws is not None and not getattr(ws, "closed", True):
                ws.send_json(payload)
            elif getattr(self.engine, "server", None):
                self.engine.server.broadcast(payload)
        except Exception:
            pass

    def _broadcast(self, data):
        try:
            text = data.decode("utf-8", errors="replace")
            self._send({
                "type": "terminal_output",
                "id": self.id,
                "data": text,
            })
        except Exception:
            pass

    def write(self, data):
        if self.closed or not self.proc:
            return
        try:
            if HAS_PTY and self.master_fd is not None:
                os.write(self.master_fd, data.encode("utf-8", errors="replace"))
            else:
                self.proc.stdin.write(data.encode("utf-8", errors="replace"))
                self.proc.stdin.flush()
        except Exception as e:
            print(f"[Terminal:{self.id}] write error: {e}")

    def resize(self, cols, rows):
        self.cols = cols
        self.rows = rows
        if HAS_PTY and self.master_fd is not None:
            self._set_winsize(self.master_fd, rows, cols)
            try:
                import signal as _sig
                os.killpg(os.getpgid(self.proc.pid), _sig.SIGWINCH)
            except Exception:
                pass

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.proc:
                try:
                    if os.name == "posix":
                        import signal as _sig
                        os.killpg(os.getpgid(self.proc.pid), _sig.SIGTERM)
                    else:
                        self.proc.terminate()
                except Exception:
                    pass
                try:
                    self.proc.wait(timeout=2)
                except Exception:
                    try:
                        if os.name == "posix":
                            import signal as _sig
                            os.killpg(os.getpgid(self.proc.pid), _sig.SIGKILL)
                        else:
                            self.proc.kill()
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            if self.master_fd is not None:
                os.close(self.master_fd)
                self.master_fd = None
        except Exception:
            pass


class TerminalManager:
    def __init__(self, engine):
        self.engine = engine
        self.sessions = {}
        self.lock = threading.Lock()

    def _resolve_cwd(self, hint):
        base = os.path.abspath(self.engine.base_dir)
        if not hint:
            return base
        target = os.path.abspath(os.path.join(base, hint.lstrip("/")))
        if target != base and not target.startswith(base + os.sep):
            return base
        if os.path.isdir(target):
            return target
        return base

    def open(self, term_id, ws, cols=80, rows=24, cwd_hint=None):
        with self.lock:
            if term_id in self.sessions:
                sess = self.sessions[term_id]
                sess.ws = ws
                return sess
            max_sessions = int(
                (self.engine.config.get("terminal") or {}).get("max_sessions", 8)
            )
            if len(self.sessions) >= max_sessions:
                raise Exception(f"Terminal limit reached ({max_sessions})")
            cwd = self._resolve_cwd(cwd_hint)
            sess = TerminalSession(term_id, self.engine, ws,
                                   cols=cols, rows=rows, cwd=cwd)
            sess.start()
            self.sessions[term_id] = sess
            return sess

    def write(self, term_id, data):
        sess = self.sessions.get(term_id)
        if sess:
            sess.write(data)

    def resize(self, term_id, cols, rows):
        sess = self.sessions.get(term_id)
        if sess:
            sess.resize(cols, rows)

    def close(self, term_id):
        with self.lock:
            sess = self.sessions.pop(term_id, None)
        if sess:
            try:
                sess.close()
            except Exception:
                pass

    def close_by_ws(self, ws):
        with self.lock:
            ids = [tid for tid, s in self.sessions.items()
                   if getattr(s, "ws", None) is ws]
        for tid in ids:
            self.close(tid)

    def close_all(self):
        with self.lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for s in sessions:
            try:
                s.close()
            except Exception:
                pass