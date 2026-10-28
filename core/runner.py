"""Process runner — chạy file project, stream output, kill process group an toàn.

v2.0.1 (hotfix):
  - L8: log name dùng hash để tránh collision giữa "a/b.py" và "a_b.py".
  - L10: giới hạn số log file để tránh đầy disk (xóa log cũ hơn 7 ngày).
"""
import os
import sys
import json
import shutil
import time
import hashlib
import signal
import subprocess
import threading
import atexit


class ProcessRunner:
    SUPPORTED = (".py", ".js", ".sh", ".bash")
    GRACE_PERIOD = 2.0
    HARD_KILL_WAIT = 2.0
    BATCH_INTERVAL = 0.10
    BATCH_MAX_LINES = 100
    LOG_MAX_AGE_DAYS = 7

    def __init__(self, engine, logs_dir):
        self.engine = engine
        self.logs_dir = logs_dir
        self.current = None
        self.lock = threading.Lock()
        self._pids_file = os.path.join(self.logs_dir, ".run_pids.json")
        os.makedirs(self.logs_dir, exist_ok=True)
        try:
            atexit.register(self._atexit_kill)
        except Exception:
            pass
        try:
            self._cleanup_old_logs()
        except Exception:
            pass

    def _cleanup_old_logs(self):
        """Xóa log cũ hơn N ngày để tránh đầy disk."""
        now = time.time()
        max_age = self.LOG_MAX_AGE_DAYS * 86400
        try:
            for fn in os.listdir(self.logs_dir):
                if fn.startswith(".") or not fn.endswith(".log"):
                    continue
                full = os.path.join(self.logs_dir, fn)
                try:
                    if now - os.path.getmtime(full) > max_age:
                        os.remove(full)
                except Exception:
                    pass
        except Exception:
            pass

    def _read_pids(self):
        try:
            if not os.path.isfile(self._pids_file):
                return []
            with open(self._pids_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("entries", []) if isinstance(data, dict) else []
        except Exception:
            return []

    def _write_pids(self, entries):
        try:
            with open(self._pids_file, "w", encoding="utf-8") as f:
                json.dump({"entries": entries}, f)
        except Exception:
            pass

    def _track_pid(self, pid, pgid):
        entries = self._read_pids()
        entries.append({"pid": pid, "pgid": pgid, "ts": time.time()})
        self._write_pids(entries)

    def _untrack_pid(self, pid):
        entries = [e for e in self._read_pids() if e.get("pid") != pid]
        self._write_pids(entries)

    def reap_orphans(self):
        entries = self._read_pids()
        for e in entries:
            pgid = e.get("pgid")
            pid = e.get("pid")
            if not pgid and not pid:
                continue
            try:
                if pgid and os.name == "posix":
                    try:
                        os.killpg(pgid, 0)
                        os.killpg(pgid, signal.SIGKILL)
                        print(f"[Runner] ♻ reaped orphan pgid={pgid} pid={pid}")
                        continue
                    except Exception:
                        pass
                if pid:
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, signal.SIGKILL)
                        print(f"[Runner] ♻ reaped orphan pid={pid}")
                    except Exception:
                        pass
            except Exception:
                pass
        self._write_pids([])

    def _cmd_for(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".py":
            return [sys.executable, "-u", filepath]
        if ext == ".js":
            node = shutil.which("node") or shutil.which("nodejs")
            if not node:
                raise Exception(
                    "Node.js not found in PATH. "
                    "Cài: pkg install nodejs (Termux) hoặc cài Node từ nodejs.org"
                )
            return [node, filepath]
        if ext in (".sh", ".bash"):
            bash = shutil.which("bash") or "/bin/bash"
            return [bash, filepath]
        raise Exception(
            f"Không hỗ trợ chạy '{ext}'. Hỗ trợ: {', '.join(self.SUPPORTED)}"
        )

    def _log_path_for(self, project, rel_path):
        """⭐ L8: dùng hash để tránh collision giữa 'a/b.py' và 'a_b.py'."""
        # Sanitize project name (an toàn cho filename)
        safe_proj = (project or "proj").replace("/", "_").replace("\\", "_")
        # Full hash của rel_path, chỉ lấy 12 ký tự
        path_hash = hashlib.sha1((rel_path or "").encode("utf-8")).hexdigest()[:12]
        # Filename ngắn gọn (giữ để dễ đọc)
        base = os.path.basename(rel_path or "file").replace("/", "_").replace("\\", "_")
        return os.path.join(self.logs_dir, f"{safe_proj}__{base}__{path_hash}.log")

    def _is_alive(self, cur):
        try:
            return cur["proc"].poll() is None
        except Exception:
            return False

    def run(self, project_dir, project_name, rel_path):
        with self.lock:
            if self.current and not self._is_alive(self.current):
                try: self.current["log"].close()
                except Exception: pass
                try: self.current["proc"].stdout.close()
                except Exception: pass
                self.current = None
            if self.current and self._is_alive(self.current):
                raise Exception(
                    f"Đang chạy '{self.current['info']['project']}/"
                    f"{self.current['info']['path']}' — dừng trước đã"
                )

            project_dir = os.path.abspath(project_dir)
            filepath = os.path.abspath(os.path.join(project_dir, rel_path or ""))
            if filepath != project_dir and not filepath.startswith(project_dir + os.sep):
                raise Exception("Path escape")
            if not os.path.isfile(filepath):
                raise Exception("File không tồn tại")
            if os.path.getsize(filepath) > 5 * 1024 * 1024:
                raise Exception("File quá lớn (> 5MB)")

            cmd = self._cmd_for(filepath)
            log_path = self._log_path_for(project_name, rel_path)
            os.makedirs(os.path.dirname(log_path), exist_ok=True)

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            env["FORCE_COLOR"] = "0"

            log_file = open(log_path, "a", encoding="utf-8", errors="replace")
            header = (
                f"\n===== RUN {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n"
                f"CMD: {' '.join(cmd)}\n"
                f"CWD: {project_dir}\n" + "-" * 60 + "\n"
            )
            try:
                log_file.write(header); log_file.flush()
            except Exception:
                pass

            kwargs = dict(
                cwd=project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=env,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
            )
            if os.name == "posix":
                kwargs["start_new_session"] = True

            try:
                proc = subprocess.Popen(cmd, **kwargs)
            except Exception as e:
                try: log_file.close()
                except Exception: pass
                raise Exception(f"Không khởi động được tiến trình: {e}")

            try:
                pgid = os.getpgid(proc.pid) if os.name == "posix" else proc.pid
            except Exception:
                pgid = proc.pid
            self._track_pid(proc.pid, pgid)

            info = {
                "project": project_name, "path": rel_path,
                "log_path": log_path, "log_name": os.path.basename(log_path),
                "started": time.time(), "pid": proc.pid, "pgid": pgid,
            }
            self.current = {"proc": proc, "info": info, "log": log_file}

        self._broadcast({
            "type": "run_started",
            "project": project_name, "path": rel_path,
            "log_name": info["log_name"], "pid": proc.pid,
        })

        threading.Thread(
            target=self._stream, args=(proc, log_file, info),
            daemon=True,
        ).start()

        return info

    def _stream(self, proc, log_file, info):
        pending, last_flush = [], time.time()

        def flush():
            nonlocal pending, last_flush
            if not pending:
                return
            try:
                self._broadcast({
                    "type": "run_output",
                    "project": info["project"], "path": info["path"],
                    "lines": pending,
                })
            except Exception:
                pass
            pending = []
            last_flush = time.time()

        try:
            try:
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    pending.append(line)
                    try:
                        log_file.write(line + "\n")
                    except Exception:
                        pass
                    now = time.time()
                    if len(pending) >= self.BATCH_MAX_LINES or (now - last_flush) >= self.BATCH_INTERVAL:
                        try: log_file.flush()
                        except Exception: pass
                        flush()
            except Exception:
                pass
        finally:
            flush()
            try:
                proc.wait(timeout=2)
            except Exception:
                pass
            code = proc.returncode if proc.returncode is not None else -1
            try:
                log_file.write(f"\n[exit code: {code}]\n")
                log_file.flush()
            except Exception:
                pass
            try: log_file.close()
            except Exception: pass
            try: proc.stdout.close()
            except Exception: pass
            self._untrack_pid(info["pid"])

            with self.lock:
                if self.current and self.current["proc"] is proc:
                    self.current = None

            self._broadcast({
                "type": "run_finished",
                "project": info["project"], "path": info["path"],
                "exit_code": code, "log_name": info["log_name"],
            })

    def _broadcast(self, msg):
        try:
            if self.engine.server:
                self.engine.server.broadcast(msg)
        except Exception:
            pass

    def _sigterm(self, pid):
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            try: os.kill(pid, signal.SIGTERM)
            except Exception: pass

    def _sigkill(self, pid):
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass

    def _wait_dead(self, proc, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if proc.poll() is not None:
                return True
            time.sleep(0.05)
        return proc.poll() is not None

    def _force_close_stdout(self, proc):
        try: proc.stdout.close()
        except Exception: pass

    def stop(self, force=False):
        with self.lock:
            cur = self.current
        if not cur:
            return False
        proc = cur["proc"]
        pid = proc.pid
        if proc.poll() is not None:
            self._force_close_stdout(proc)
            return True

        if force:
            self._sigkill(pid)
            self._wait_dead(proc, self.HARD_KILL_WAIT)
        else:
            self._sigterm(pid)
            if not self._wait_dead(proc, self.GRACE_PERIOD):
                self._sigkill(pid)
                self._wait_dead(proc, self.HARD_KILL_WAIT)

        self._force_close_stdout(proc)
        return True

    def _force_kill_current(self):
        with self.lock:
            cur = self.current
        if not cur:
            return
        try: self._sigkill(cur["proc"].pid)
        except Exception: pass
        self._force_close_stdout(cur["proc"])

    def _atexit_kill(self):
        try: self._force_kill_current()
        except Exception: pass

    def status(self):
        with self.lock:
            cur = self.current
            if not cur:
                return {"running": False}
            return {
                "running": cur["proc"].poll() is None,
                "project": cur["info"]["project"],
                "path": cur["info"]["path"],
                "log_name": cur["info"]["log_name"],
                "pid": cur["info"]["pid"],
                "pgid": cur["info"].get("pgid"),
                "started": cur["info"]["started"],
            }