"""ModuleStorage — per-module isolated storage with 512MB quota.

v1.4.0:
  - Mỗi module có "storage/" riêng biệt (ngoài sandbox data/).
  - Quota 512MB (config được), cảnh báo khi > 90%, từ chối ghi khi đầy.
  - Upload file → tự động chia chunk, lưu metadata.
  - Export ZIP toàn bộ storage → download.
  - Tự động cleanup file tạm sau upload.
"""
import os
import io
import json
import time
import shutil
import hashlib
import zipfile
import threading

DEFAULT_QUOTA = 512 * 1024 * 1024        # 512 MB
WARN_THRESHOLD = 0.90                    # cảnh báo khi >= 90%
HARD_THRESHOLD = 0.98                    # từ chối upload khi >= 98%
CHUNK_SIZE = 4 * 1024 * 1024             # 4MB mỗi chunk khi upload


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

        # quota per module (có thể override qua config hoặc init.txt)
        self.default_quota = int(
            self.config.get("module_storage_quota", DEFAULT_QUOTA)
        )

        # cache warning state: name -> {warned: bool, last_check: ts}
        self._warned = {}
        # back-ref engine (gán từ engine __init__) — dùng cho quota override
        self.engine = None

    # ================================================================ #
    #  Paths
    # ================================================================ #
    def storage_dir(self, module_name):
        """Thư mục storage của module — tách biệt với data/ (sandbox)."""
        if not self._safe_name(module_name):
            raise StorageViolation(f"Invalid module name: {module_name!r}")
        path = os.path.join(self.modules_dir, module_name, "storage")
        os.makedirs(path, exist_ok=True)
        return path

    def files_dir(self, module_name):
        """Thư mục con chứa file upload."""
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
        """Validate relative path — reject ../ và absolute."""
        rel = (rel or "").lstrip("/").replace("\\", "/")
        if not rel:
            return ""
        for part in rel.split("/"):
            if part == "..":
                raise StorageViolation(f"Path traversal not allowed: {rel!r}")
        return rel

    def resolve(self, module_name, rel):
        """Resolve file path trong storage/files/<rel>."""
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
        """Quota riêng — có thể override trong init.txt (module_storage_quota)."""
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
        """Trả về dict: used, quota, percent, status ('ok'|'warn'|'full')."""
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
        """Raise QuotaExceeded nếu vượt quota."""
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
        """List files trong storage/files/<sub_dir>."""
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
        """Ghi file — data là bytes hoặc str."""
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
        """Xoá toàn bộ file trong storage/files/."""
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
    #  Upload chunk (hỗ trợ file lớn)
    # ================================================================ #
    def upload_chunk(self, module_name, rel, chunk_index, total_chunks,
                     chunk_b64, total_size, upload_id=None):
        """Ghi từng chunk — assemble thành file cuối khi đủ."""
        import base64

        if not upload_id:
            raise Exception("Missing upload_id")

        tmp_dir = os.path.join(self.storage_dir(module_name), ".tmp_uploads", upload_id)
        os.makedirs(tmp_dir, exist_ok=True)

        chunk_path = os.path.join(tmp_dir, f"chunk_{chunk_index:05d}")
        try:
            raw = base64.b64decode(chunk_b64)
        except Exception as e:
            raise Exception(f"Invalid chunk base64: {e}")

        # quota check trước khi ghi (dùng total_size để estimate chính xác hơn)
        if chunk_index == 0:
            self.check_quota(module_name, total_size)

        with open(chunk_path, "wb") as f:
            f.write(raw)

        # đủ chunk → assemble
        if chunk_index == total_chunks - 1:
            target = self.resolve(module_name, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as out:
                for i in range(total_chunks):
                    cp = os.path.join(tmp_dir, f"chunk_{i:05d}")
                    if not os.path.isfile(cp):
                        raise Exception(f"Missing chunk {i}")
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
        }

    # ================================================================ #
    #  Export ZIP
    # ================================================================ #
    def export_zip(self, module_name, sub_dir=""):
        """Export storage/files/<sub_dir> thành ZIP bytes."""
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
    #  Metadata (.storage.json)
    # ================================================================ #
    def _touch_meta(self, module_name, rel, size, deleted=False):
        path = self.meta_path(module_name)
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
            with open(path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

    # ================================================================ #
    #  Cleanup
    # ================================================================ #
    def cleanup_module(self, module_name):
        """Gọi khi uninstall module."""
        try:
            path = os.path.join(self.modules_dir, module_name, "storage")
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass
        self._warned.pop(module_name, None)

    def check_and_warn(self, module_name):
        """Trả về warning dict nếu cần cảnh báo, ngược lại None."""
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