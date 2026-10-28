"""ModuleStorage — per-module isolated storage with 512MB quota.

v2.0.1 (hotfix):
  - H6: assemble khi đủ chunk (không phụ thuộc thứ tự) — hỗ trợ parallel upload.
  - H7: meta update dưới lock + atomic write — không corrupt khi concurrent.
  - H8: quota check lại lúc assemble (chống client lie total_size).
"""
import os
import io
import json
import time
import shutil
import hashlib
import zipfile
import threading

DEFAULT_QUOTA = 512 * 1024 * 1024
WARN_THRESHOLD = 0.90
HARD_THRESHOLD = 0.98
CHUNK_SIZE = 4 * 1024 * 1024


class QuotaExceeded(Exception):
    pass


class StorageViolation(Exception):
    pass


class ModuleStorage:
    def __init__(self, base_dir, config=None):
        self.base_dir = base_dir
        self.config = config or {}
        self.modules_dir = os.path.join(base_dir, "modules")
        self.lock = threading.Lock()

        self.default_quota = int(
            self.config.get("module_storage_quota", DEFAULT_QUOTA)
        )

        self._warned = {}
        self.engine = None

    # ================================================================ #
    #  Paths
    # ================================================================ #
    def storage_dir(self, module_name):
        if not self._safe_name(module_name):
            raise StorageViolation(f"Invalid module name: {module_name!r}")
        path = os.path.join(self.modules_dir, module_name, "storage")
        os.makedirs(path, exist_ok=True)
        return path

    def files_dir(self, module_name):
        path = os.path.join(self.storage_dir(module_name), "files")
        os.makedirs(path, exist_ok=True)
        return path

    def meta_path(self, module_name):
        return os.path.join(self.storage_dir(module_name), ".storage.json")

    def _safe_name(self, name):
        if not name:
            return False
        if "/" in name or "\\" in name or name in (".", ".."):
            return False
        return True

    def _safe_rel(self, rel):
        rel = (rel or "").lstrip("/").replace("\\", "/")
        if not rel:
            return ""
        for part in rel.split("/"):
            if part == "..":
                raise StorageViolation(f"Path traversal not allowed: {rel!r}")
        return rel

    def resolve(self, module_name, rel):
        rel = self._safe_rel(rel)
        base = os.path.abspath(self.files_dir(module_name))
        target = os.path.abspath(os.path.join(base, rel))
        if target != base and not target.startswith(base + os.sep):
            raise StorageViolation(f"Path escape: {rel!r}")
        return target

    # ================================================================ #
    #  Quota calculation
    # ================================================================ #
    def _dir_size(self, path):
        total = 0
        if not os.path.isdir(path):
            return 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total

    def quota_for(self, module_name):
        module = None
        try:
            if self.engine is not None:
                module = self.engine.modules.get(module_name)
        except Exception:
            module = None
        if module:
            meta_q = module.metadata.get("module_storage_quota")
            if meta_q:
                try:
                    return int(meta_q)
                except (TypeError, ValueError):
                    pass
        return self.default_quota

    def usage(self, module_name):
        used = self._dir_size(self.files_dir(module_name))
        quota = self.quota_for(module_name)
        percent = used / quota if quota > 0 else 0.0
        if percent >= HARD_THRESHOLD:
            status = "full"
        elif percent >= WARN_THRESHOLD:
            status = "warn"
        else:
            status = "ok"
        return {
            "used": used,
            "quota": quota,
            "percent": round(percent * 100, 2),
            "status": status,
            "free": max(0, quota - used),
        }

    def check_quota(self, module_name, incoming_bytes=0):
        info = self.usage(module_name)
        quota = info["quota"]
        used = info["used"]
        if used + incoming_bytes > quota * HARD_THRESHOLD:
            raise QuotaExceeded(
                f"Module '{module_name}' storage nearly full: "
                f"{used / (1024*1024):.1f}MB / {quota / (1024*1024):.1f}MB "
                f"({info['percent']:.1f}%). "
                f"Vui lòng giải phóng bớt (xoá file cũ) để tiếp tục."
            )

    # ================================================================ #
    #  File operations
    # ================================================================ #
    def list_files(self, module_name, sub_dir=""):
        root = self.resolve(module_name, sub_dir)
        if not os.path.isdir(root):
            return []
        out = []
        for name in sorted(os.listdir(root)):
            full = os.path.join(root, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            rel = os.path.relpath(full, self.files_dir(module_name)).replace("\\", "/")
            out.append({
                "name": name,
                "path": rel,
                "type": "dir" if os.path.isdir(full) else "file",
                "size": 0 if os.path.isdir(full) else st.st_size,
                "mtime": st.st_mtime,
            })
        return out

    def write_file(self, module_name, rel, data, check=True):
        if isinstance(data, str):
            data = data.encode("utf-8")
        if check:
            self.check_quota(module_name, len(data))
        target = self.resolve(module_name, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(data)
        self._touch_meta(module_name, rel, len(data))
        return {
            "path": rel,
            "size": len(data),
            "usage": self.usage(module_name),
        }

    def read_file(self, module_name, rel):
        target = self.resolve(module_name, rel)
        if not os.path.isfile(target):
            raise Exception("File not found")
        if os.path.getsize(target) > 50 * 1024 * 1024:
            raise Exception("File quá lớn (> 50MB) — dùng download ZIP")
        with open(target, "rb") as f:
            return f.read()

    def delete_file(self, module_name, rel):
        target = self.resolve(module_name, rel)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        elif os.path.isfile(target):
            os.remove(target)
        self._touch_meta(module_name, rel, 0, deleted=True)
        return {"ok": True, "usage": self.usage(module_name)}

    def clear_all(self, module_name):
        files_dir = self.files_dir(module_name)
        if os.path.isdir(files_dir):
            for name in os.listdir(files_dir):
                full = os.path.join(files_dir, name)
                try:
                    if os.path.isdir(full):
                        shutil.rmtree(full, ignore_errors=True)
                    else:
                        os.remove(full)
                except Exception:
                    pass
        self._touch_meta(module_name, "", 0, deleted=True)
        return {"ok": True, "usage": self.usage(module_name)}

    # ================================================================ #
    #  Upload chunk
    # ================================================================ #
    def upload_chunk(self, module_name, rel, chunk_index, total_chunks,
                     chunk_b64, total_size, upload_id=None):
        import base64

        if not upload_id:
            raise Exception("Missing upload_id")

        # Upload_id safety
        if "/" in upload_id or "\\" in upload_id or ".." in upload_id:
            raise StorageViolation(f"Invalid upload_id: {upload_id!r}")

        tmp_dir = os.path.join(self.storage_dir(module_name), ".tmp_uploads", upload_id)
        os.makedirs(tmp_dir, exist_ok=True)

        chunk_path = os.path.join(tmp_dir, f"chunk_{chunk_index:05d}")
        try:
            raw = base64.b64decode(chunk_b64)
        except Exception as e:
            raise Exception(f"Invalid chunk base64: {e}")

        if chunk_index == 0:
            self.check_quota(module_name, total_size)

        with open(chunk_path, "wb") as f:
            f.write(raw)

        # ⭐ H6: assemble khi ĐỦ chunk (không phụ thuộc thứ tự)
        existing_chunks = [
            fn for fn in os.listdir(tmp_dir) if fn.startswith("chunk_")
        ]
        if len(existing_chunks) >= total_chunks:
            # Verify có đủ 0..total_chunks-1
            missing = []
            for i in range(total_chunks):
                cp = os.path.join(tmp_dir, f"chunk_{i:05d}")
                if not os.path.isfile(cp):
                    missing.append(i)
            if missing:
                return {
                    "ok": True,
                    "completed": False,
                    "chunk": chunk_index,
                    "waiting_for": missing[:5],
                }

            # ⭐ H8: verify actual size trước khi ghi vào files/
            actual_size = sum(
                os.path.getsize(os.path.join(tmp_dir, f"chunk_{i:05d}"))
                for i in range(total_chunks)
            )
            self.check_quota(module_name, actual_size)

            target = self.resolve(module_name, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as out:
                for i in range(total_chunks):
                    cp = os.path.join(tmp_dir, f"chunk_{i:05d}")
                    with open(cp, "rb") as cf:
                        shutil.copyfileobj(cf, out)

            shutil.rmtree(tmp_dir, ignore_errors=True)
            size = os.path.getsize(target)
            self._touch_meta(module_name, rel, size)
            return {
                "ok": True,
                "completed": True,
                "path": rel,
                "size": size,
                "usage": self.usage(module_name),
            }

        return {
            "ok": True,
            "completed": False,
            "chunk": chunk_index,
            "received": len(existing_chunks),
            "total": total_chunks,
        }

    # ================================================================ #
    #  Export ZIP
    # ================================================================ #
    def export_zip(self, module_name, sub_dir=""):
        base = self.resolve(module_name, sub_dir)
        if not os.path.isdir(base):
            raise Exception("Storage dir not found")

        buf = io.BytesIO()
        count = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(base):
                dirs[:] = sorted(d for d in dirs if d not in (".tmp_uploads", "__pycache__"))
                for fname in sorted(files):
                    full = os.path.join(root, fname)
                    try:
                        rel = os.path.relpath(full, base)
                    except Exception:
                        continue
                    arcname = (module_name + "_storage/" + rel).replace("\\", "/")
                    try:
                        zf.write(full, arcname=arcname)
                        count += 1
                    except (OSError, IOError):
                        continue

        return {
            "data": buf.getvalue(),
            "files": count,
            "size": buf.tell(),
        }

    # ================================================================ #
    #  Metadata — H7: atomic + lock
    # ================================================================ #
    def _touch_meta(self, module_name, rel, size, deleted=False):
        path = self.meta_path(module_name)
        with self.lock:  # ⭐ H7: thread-safe
            try:
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                else:
                    meta = {"files": {}}
            except Exception:
                meta = {"files": {}}
            files = meta.setdefault("files", {})
            if deleted and not rel:
                meta["files"] = {}
            elif rel:
                if deleted:
                    files.pop(rel, None)
                else:
                    files[rel] = {
                        "size": size,
                        "updated_at": time.time(),
                    }
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
                os.replace(tmp, path)
            except Exception:
                pass

    # ================================================================ #
    #  Cleanup / warning
    # ================================================================ #
    def cleanup_module(self, module_name):
        try:
            path = os.path.join(self.modules_dir, module_name, "storage")
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass
        self._warned.pop(module_name, None)

    def check_and_warn(self, module_name):
        info = self.usage(module_name)
        if info["status"] == "ok":
            self._warned.pop(module_name, None)
            return None

        last = self._warned.get(module_name, {})
        last_ts = last.get("ts", 0)
        if (time.time() - last_ts) < 30 and last.get("status") == info["status"]:
            return None

        self._warned[module_name] = {"ts": time.time(), "status": info["status"]}

        if info["status"] == "full":
            msg = (
                f"⛔ Module '{module_name}' storage gần đầy "
                f"({info['percent']:.1f}% / {info['quota'] / (1024*1024):.0f}MB). "
                f"Cần giải phóng để upload tiếp."
            )
        else:
            msg = (
                f"⚠️ Module '{module_name}' storage đã dùng "
                f"{info['percent']:.1f}% ({info['used'] / (1024*1024):.1f}MB / "
                f"{info['quota'] / (1024*1024):.0f}MB)."
            )

        return {
            "module": module_name,
            "usage": info,
            "message": msg,
            "severity": "error" if info["status"] == "full" else "warning",
        }