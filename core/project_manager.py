"""Project manager: CRUD projects + file operations inside projects.

Mỗi project nằm trong projects/<name>/ và hoàn toàn cô lập với các project
khác cũng như với core engine. Toàn bộ đường dẫn được kiểm tra anti-escape
tương tự sandbox của modules.
"""
import os
import io
import json
import time
import shutil
import base64
import zipfile


class ProjectManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.projects_dir = os.path.join(base_dir, "projects")
        os.makedirs(self.projects_dir, exist_ok=True)

    # ---------------------------------------------------------------- #
    #  Helpers
    # ---------------------------------------------------------------- #
    def _safe_path(self, project, path=""):
        if not project or "/" in project or "\\" in project or project in (".", ".."):
            raise Exception("Invalid project name")

        proj_dir = os.path.abspath(os.path.join(self.projects_dir, project))
        projects_root = os.path.abspath(self.projects_dir)
        if proj_dir != projects_root and not proj_dir.startswith(projects_root + os.sep):
            raise Exception("Invalid project path")

        rel = (path or "").lstrip("/").replace("\\", "/")
        for part in rel.split("/"):
            if part == "..":
                raise Exception("Path traversal not allowed")

        target = os.path.abspath(os.path.join(proj_dir, rel))
        if target != proj_dir and not target.startswith(proj_dir + os.sep):
            raise Exception("Path escape")
        return target

    def _meta_path(self, project):
        return os.path.join(self.projects_dir, project, ".project.json")

    # ---------------------------------------------------------------- #
    #  Projects CRUD
    # ---------------------------------------------------------------- #
    def list_projects(self):
        out = []
        if not os.path.isdir(self.projects_dir):
            return out
        for name in sorted(os.listdir(self.projects_dir)):
            p = os.path.join(self.projects_dir, name)
            if not os.path.isdir(p):
                continue
            meta = {}
            mp = self._meta_path(name)
            if os.path.isfile(mp):
                try:
                    with open(mp, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    meta = {}
            out.append({
                "name": name,
                "created_at": meta.get("created_at", 0),
                "language": meta.get("language", "plaintext"),
            })
        return out

    def create(self, name, language="plaintext"):
        if not name:
            raise Exception("Missing project name")
        if "/" in name or "\\" in name or name in (".", ".."):
            raise Exception("Invalid project name")

        target = os.path.join(self.projects_dir, name)
        if os.path.exists(target):
            raise Exception("Project already exists")

        os.makedirs(target, exist_ok=True)

        meta = {"name": name, "created_at": time.time(), "language": language}
        with open(self._meta_path(name), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        starter = self._starter_file(language)
        if starter:
            fname, content = starter
            with open(os.path.join(target, fname), "w", encoding="utf-8") as f:
                f.write(content)

        return meta

    def _starter_file(self, language):
        if language == "python":
            return ("main.py",
                    "def main():\n"
                    "    print('Hello, ACDV!')\n\n\n"
                    "if __name__ == '__main__':\n"
                    "    main()\n")
        if language == "javascript":
            return ("index.js", "console.log('Hello, ACDV!');\n")
        if language == "html":
            return ("index.html",
                    "<!DOCTYPE html>\n<html>\n<head>\n"
                    "  <meta charset=\"utf-8\">\n  <title>Hello</title>\n"
                    "</head>\n<body>\n  <h1>Hello, ACDV!</h1>\n</body>\n</html>\n")
        return ("README.md", "# New project\n")

    # ---------------------------------------------------------------- #
    #  ⭐ Upload từ ZIP (v1.1.0)
    # ---------------------------------------------------------------- #
    def create_from_zip(self, name, zip_base64):
        """Tạo project từ ZIP base64. Tự động giải nén + strip root folder."""
        if not name:
            raise Exception("Missing project name")
        if "/" in name or "\\" in name or name in (".", ".."):
            raise Exception("Invalid project name")

        target = os.path.join(self.projects_dir, name)
        if os.path.exists(target):
            raise Exception("Project already exists")

        # ---- Decode base64 ----
        if not zip_base64:
            raise Exception("Missing zip_base64")
        try:
            # Strip data URL prefix if present
            if isinstance(zip_base64, str) and zip_base64.startswith("data:"):
                zip_base64 = zip_base64.split(",", 1)[1]
            raw = base64.b64decode(zip_base64)
        except Exception as e:
            raise Exception(f"Invalid base64 data: {e}")
        if not raw:
            raise Exception("Empty ZIP payload")

        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as e:
            raise Exception(f"Invalid ZIP file: {e}")

        with zf:
            names = zf.namelist()
            if not names:
                raise Exception("ZIP contains no entries")

            # ---- Validate mọi entry (chống zip-slip) ----
            for n in names:
                norm = n.replace("\\", "/")
                if norm.startswith("/"):
                    raise Exception(f"Absolute path not allowed: {n}")
                if ".." in norm.split("/"):
                    raise Exception(f"Path traversal not allowed: {n}")

            # ---- Strip common root folder nếu có ----
            top_dirs = set()
            for n in names:
                norm = n.replace("\\", "/").strip("/")
                if not norm:
                    continue
                parts = norm.split("/")
                if len(parts) > 1:
                    top_dirs.add(parts[0])

            strip_prefix = ""
            if len(top_dirs) == 1:
                candidate = list(top_dirs)[0]
                ok, has_content = True, False
                for n in names:
                    norm = n.replace("\\", "/").strip("/")
                    if not norm or norm == candidate:
                        continue
                    if not norm.startswith(candidate + "/"):
                        ok = False
                        break
                    has_content = True
                if ok and has_content:
                    strip_prefix = candidate + "/"

            os.makedirs(target, exist_ok=True)
            target_abs = os.path.abspath(target)
            extracted, skipped = 0, 0

            try:
                for n in names:
                    if n.endswith("/"):
                        continue
                    norm = n.replace("\\", "/")
                    rel = norm[len(strip_prefix):] if strip_prefix and norm.startswith(strip_prefix) else norm
                    if not rel:
                        continue

                    parts = rel.split("/")
                    if "__MACOSX" in parts or rel.endswith(".DS_Store"):
                        skipped += 1
                        continue

                    dest = os.path.abspath(os.path.join(target, rel))
                    if dest != target_abs and not dest.startswith(target_abs + os.sep):
                        raise Exception(f"Path escape attempt: {rel}")

                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(n) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted += 1

                if extracted == 0:
                    raise Exception("ZIP contained no extractable files")
            except Exception:
                shutil.rmtree(target, ignore_errors=True)
                raise

        # ---- Meta ----
        meta = {
            "name": name,
            "created_at": time.time(),
            "language": "zip_import",
        }
        with open(self._meta_path(name), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return {**meta, "files_extracted": extracted, "files_skipped": skipped}

    # ---------------------------------------------------------------- #
    #  ⭐ Export ZIP
    # ---------------------------------------------------------------- #
    def export_zip(self, name):
        """Export project thành ZIP bytes (base dir = <name>/).

        - Bỏ `.project.json` (metadata nội bộ) và `__pycache__`.
        - Round-trip: ZIP này có thể upload lại qua `create_from_zip()`.
        """
        if not name:
            raise Exception("Missing project name")
        if "/" in name or "\\" in name or name in (".", ".."):
            raise Exception("Invalid project name")

        proj_dir = self._safe_path(name)
        if not os.path.isdir(proj_dir):
            raise Exception("Project not found")

        buf = io.BytesIO()
        count = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(proj_dir):
                dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", ".git", ".svn"))
                for fname in sorted(files):
                    if fname == ".project.json" or fname.endswith(".pyc"):
                        continue
                    full = os.path.join(root, fname)
                    try:
                        rel = os.path.relpath(full, proj_dir)
                    except Exception:
                        continue
                    arcname = (name + "/" + rel).replace("\\", "/")
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

    def delete(self, name):
        target = self._safe_path(name)
        if os.path.isdir(target):
            shutil.rmtree(target)

    # ---------------------------------------------------------------- #
    #  File tree
    # ---------------------------------------------------------------- #
    def tree(self, project, path=""):
        root = self._safe_path(project, path)
        if not os.path.exists(root):
            return []
        return self._tree_recursive(root)

    def _tree_recursive(self, root):
        dirs, files = [], []
        try:
            entries = sorted(os.listdir(root))
        except Exception:
            return []
        for entry in entries:
            if entry in (".project.json", "__pycache__"):
                continue
            full = os.path.join(root, entry)
            rel = os.path.relpath(full, self.projects_dir).replace("\\", "/")
            parts = rel.split("/", 1)
            if len(parts) < 2:
                continue
            rel_path = parts[1]
            if os.path.isdir(full):
                dirs.append({
                    "name": entry, "path": rel_path, "type": "dir",
                    "children": self._tree_recursive(full),
                })
            else:
                try:
                    size = os.path.getsize(full)
                except Exception:
                    size = 0
                files.append({
                    "name": entry, "path": rel_path, "type": "file", "size": size,
                })
        return dirs + files

    # ---------------------------------------------------------------- #
    #  File operations
    # ---------------------------------------------------------------- #
    def read_file(self, project, path):
        target = self._safe_path(project, path)
        if not os.path.isfile(target):
            raise Exception("File not found")
        if os.path.getsize(target) > 5 * 1024 * 1024:
            raise Exception("File too large (> 5MB)")
        with open(target, "rb") as f:
            data = f.read()
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise Exception("File is not valid UTF-8 text")

    def write_file(self, project, path, content):
        target = self._safe_path(project, path)
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def create_file(self, project, path):
        target = self._safe_path(project, path)
        if os.path.exists(target):
            raise Exception("Already exists")
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        open(target, "w", encoding="utf-8").close()
        return True

    def create_folder(self, project, path):
        target = self._safe_path(project, path)
        if os.path.exists(target):
            raise Exception("Already exists")
        os.makedirs(target, exist_ok=True)
        return True

    def delete_file(self, project, path):
        target = self._safe_path(project, path)
        if not os.path.exists(target):
            raise Exception("Not found")
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
        return True

    def rename(self, project, old_path, new_path):
        src = self._safe_path(project, old_path)
        dst = self._safe_path(project, new_path)
        if not os.path.exists(src):
            raise Exception("Source not found")
        if os.path.exists(dst):
            raise Exception("Target already exists")
        parent = os.path.dirname(dst)
        if parent:
            os.makedirs(parent, exist_ok=True)
        os.rename(src, dst)
        return True