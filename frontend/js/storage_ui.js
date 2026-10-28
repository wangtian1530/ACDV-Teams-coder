/* ACDV Module Storage UI — v2.0.1
 * v2.0.1 fixes:
 * - M4: hiển thị path đầy đủ khi file ở subdir (tránh nhầm khi cùng tên).
 * - M5: cảnh báo trước khi upload file có tên trùng.
 */
const StorageUI = {
  _currentModule: null,
  _modalEl: null,
  _lastFiles: [],

  _ensureModal() {
    if (this._modalEl) return this._modalEl;

    const modal = document.createElement("div");
    modal.id = "storageModal";
    modal.className = "modal hidden";
    modal.innerHTML = `
      <div class="modal-card storage-card">
        <div class="storage-header">
          <h3>💾 Storage — <span id="storageModuleName">?</span></h3>
          <button class="icon-btn small" id="storageCloseBtn" title="Close">×</button>
        </div>
        <div class="storage-usage" id="storageUsageBar">
          <div class="storage-usage-text">Đang tải…</div>
          <div class="storage-bar"><div class="storage-bar-fill"></div></div>
        </div>
        <div class="storage-actions">
          <button class="btn btn-sm btn-primary" id="storageUploadBtn">📤 Upload file</button>
          <button class="btn btn-sm btn-info" id="storageExportZipBtn">⬇ Export ZIP</button>
          <button class="btn btn-sm btn-danger" id="storageClearBtn">🗑 Clear all</button>
          <button class="icon-btn small" id="storageRefreshBtn" title="Refresh">⟳</button>
        </div>
        <div class="storage-files" id="storageFiles">
          <div class="storage-loading">Đang tải danh sách file…</div>
        </div>
        <input type="file" id="storageFileInput" hidden multiple>
        <div class="storage-upload-progress hidden" id="storageUploadProgress">
          <div class="progress-label" id="storageProgressLabel">Uploading…</div>
          <div class="progress-bar"><div class="progress-fill" id="storageProgressFill"></div></div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    this._modalEl = modal;

    modal.querySelector("#storageCloseBtn").onclick = () => this.close();
    modal.querySelector("#storageRefreshBtn").onclick = () => this.refresh();
    modal.querySelector("#storageUploadBtn").onclick = () => {
      modal.querySelector("#storageFileInput").click();
    };
    modal.querySelector("#storageFileInput").onchange = (e) => {
      const files = Array.from(e.target.files || []);
      e.target.value = "";
      if (files.length) this._uploadFiles(files);
    };
    modal.querySelector("#storageExportZipBtn").onclick = () => this._exportZip();
    modal.querySelector("#storageClearBtn").onclick = () => this._clearAll();

    modal.addEventListener("click", (e) => {
      if (e.target === modal) this.close();
    });

    return modal;
  },

  async open(moduleName) {
    this._currentModule = moduleName;
    const modal = this._ensureModal();
    modal.classList.remove("hidden");
    modal.querySelector("#storageModuleName").textContent = moduleName;
    await this.refresh();
  },

  close() {
    if (this._modalEl) this._modalEl.classList.add("hidden");
    this._currentModule = null;
  },

  async refresh() {
    if (!this._currentModule) return;
    const name = this._currentModule;
    try {
      const [usageRes, listRes] = await Promise.all([
        API.storageUsage(name).catch(e => ({ ok: false, error: e.message })),
        API.storageList(name, "").catch(e => ({ ok: false, error: e.message })),
      ]);
      if (usageRes && usageRes.ok) this._renderUsage(usageRes.usage);
      if (listRes && listRes.ok) {
        this._lastFiles = listRes.files || [];
        this._renderFiles(this._lastFiles);
      } else {
        const el = document.getElementById("storageFiles");
        if (el) el.innerHTML = `<div class="storage-error">✗ ${listRes.error || "load failed"}</div>`;
      }
    } catch (e) {
      console.error("[StorageUI] refresh", e);
    }
  },

  _renderUsage(usage) {
    const el = document.getElementById("storageUsageBar");
    if (!el || !usage) return;
    const usedMB = (usage.used / (1024 * 1024)).toFixed(2);
    const quotaMB = (usage.quota / (1024 * 1024)).toFixed(0);
    const percent = Math.min(100, usage.percent);
    const cls = usage.status === "full" ? "danger"
              : usage.status === "warn" ? "warn" : "ok";
    el.innerHTML = `
      <div class="storage-usage-text">
        <span>${usedMB} MB / ${quotaMB} MB</span>
        <span class="storage-percent ${cls}">${percent.toFixed(1)}%</span>
      </div>
      <div class="storage-bar">
        <div class="storage-bar-fill ${cls}" style="width:${percent}%"></div>
      </div>
      ${usage.status !== "ok"
        ? `<div class="storage-warn-msg">${usage.status === "full"
            ? "⛔ Gần đầy — cần xoá file để upload tiếp"
            : "⚠️ Đã dùng trên 90% quota"}</div>`
        : ""}
    `;
  },

  _renderFiles(files) {
    const el = document.getElementById("storageFiles");
    if (!el) return;
    if (!files.length) {
      el.innerHTML = `<div class="storage-empty">📭 Storage trống — upload file đầu tiên</div>`;
      return;
    }
    el.innerHTML = "";
    files.forEach(f => {
      const row = document.createElement("div");
      row.className = "storage-file-row";
      const icon = f.type === "dir" ? "📁" : "📄";
      const sizeTxt = f.type === "dir" ? "" : this._fmtSize(f.size);

      // ⭐ M4: hiển thị path đầy đủ nếu file nằm trong subdir
      const label = f.path && f.path !== f.name ? f.path : f.name;

      row.innerHTML = `
        <span class="storage-file-icon">${icon}</span>
        <span class="storage-file-name" title="${this._escape(f.path)}">${this._escape(label)}</span>
        <span class="storage-file-size">${sizeTxt}</span>
      `;
      const actions = document.createElement("div");
      actions.className = "storage-file-actions";

      if (f.type === "file") {
        const dl = document.createElement("button");
        dl.className = "icon-btn small";
        dl.textContent = "⬇";
        dl.title = "Download";
        dl.onclick = () => this._download(f.path);
        actions.appendChild(dl);
      }

      const del = document.createElement("button");
      del.className = "icon-btn small";
      del.textContent = "🗑";
      del.title = "Delete";
      del.onclick = () => this._delete(f.path);
      actions.appendChild(del);

      row.appendChild(actions);
      el.appendChild(row);
    });
  },

  _fmtSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  },

  _escape(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  },

  async _uploadFiles(files) {
    if (!this._currentModule) return;
    const name = this._currentModule;
    const CHUNK = 4 * 1024 * 1024;

    // ⭐ M5: cảnh báo overwrite nếu trùng tên
    const existingPaths = new Set(
      (this._lastFiles || [])
        .filter(f => f.type === "file")
        .map(f => f.path)
    );
    const conflicts = files.filter(f => existingPaths.has(f.name)).map(f => f.name);
    if (conflicts.length > 0) {
      const msg = `Các file sau đã tồn tại và sẽ bị GHI ĐÈ:\n\n${conflicts.join("\n")}\n\nTiếp tục?`;
      if (!confirm(msg)) return;
    }

    for (const file of files) {
      if (file.size === 0) continue;
      if (file.size > 200 * 1024 * 1024) {
        alert(`File "${file.name}" quá lớn (> 200MB). Chia nhỏ trước khi upload.`);
        continue;
      }

      const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK));
      const uploadId = "up_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
      const relPath = file.name;

      this._showProgress(`Uploading ${file.name} (0/${totalChunks})…`, 0);

      try {
        for (let i = 0; i < totalChunks; i++) {
          const start = i * CHUNK;
          const end = Math.min(start + CHUNK, file.size);
          const blob = file.slice(start, end);
          const b64 = await this._blobToBase64(blob);

          const res = await API.storageUploadChunk({
            name,
            path: relPath,
            chunk_index: i,
            total_chunks: totalChunks,
            chunk_b64: b64,
            total_size: file.size,
            upload_id: uploadId,
          });

          if (!res || !res.ok) {
            throw new Error(res && res.error ? res.error : "upload failed");
          }

          const pct = Math.round(((i + 1) / totalChunks) * 100);
          this._showProgress(
            `Uploading ${file.name} (${i + 1}/${totalChunks})…`, pct);

          if (res.usage && res.usage.status !== "ok") {
            App.log(res.usage.status === "full"
              ? `⛔ ${name}: storage gần đầy — cần giải phóng`
              : `⚠️ ${name}: storage đã dùng ${res.usage.percent}%`,
              res.usage.status === "full" ? "error" : "success");
          }
        }
        App.log(`✓ Uploaded ${file.name} (${this._fmtSize(file.size)})`, "success");
      } catch (e) {
        App.log(`✗ Upload ${file.name}: ${e.message}`, "error");
        alert(`Upload failed: ${e.message}`);
      }
    }

    this._hideProgress();
    await this.refresh();
  },

  _blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const s = String(reader.result || "");
        const i = s.indexOf(",");
        resolve(i >= 0 ? s.slice(i + 1) : s);
      };
      reader.onerror = () => reject(reader.error || new Error("read error"));
      reader.readAsDataURL(blob);
    });
  },

  _showProgress(label, pct) {
    const el = document.getElementById("storageUploadProgress");
    const lbl = document.getElementById("storageProgressLabel");
    const fill = document.getElementById("storageProgressFill");
    if (!el) return;
    el.classList.remove("hidden");
    if (lbl) lbl.textContent = label;
    if (fill) fill.style.width = pct + "%";
  },

  _hideProgress() {
    const el = document.getElementById("storageUploadProgress");
    if (el) el.classList.add("hidden");
  },

  async _download(path) {
    if (!this._currentModule) return;
    try {
      const res = await API.storageDownload(this._currentModule, path);
      const bin = atob(res.content_b64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const blob = new Blob([bytes]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.filename || "download.bin";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1500);
      App.log(`✓ Downloaded ${res.filename}`, "success");
    } catch (e) {
      App.log(`✗ Download: ${e.message}`, "error");
      alert(e.message);
    }
  },

  async _delete(path) {
    if (!this._currentModule) return;
    if (!confirm(`Xoá "${path}"?`)) return;
    try {
      await API.storageDelete(this._currentModule, path);
      App.log(`✓ Deleted ${path}`, "success");
      await this.refresh();
    } catch (e) {
      App.log(`✗ Delete: ${e.message}`, "error");
    }
  },

  async _exportZip() {
    if (!this._currentModule) return;
    try {
      App.log(`📦 Exporting storage ZIP của ${this._currentModule}…`);
      const res = await API.storageExportZip(this._currentModule, "");
      if (!res.zip_base64) {
        return alert("Storage trống — không có gì để export");
      }
      if (window.App && App._downloadBase64) {
        App._downloadBase64(res.zip_base64, res.filename);
      } else {
        const bin = atob(res.zip_base64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        const blob = new Blob([bytes], { type: "application/zip" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = res.filename;
        a.click();
      }
      App.log(`✓ Downloaded ${res.filename} (${res.files} files)`, "success");
    } catch (e) {
      App.log(`✗ Export: ${e.message}`, "error");
      alert(e.message);
    }
  },

  async _clearAll() {
    if (!this._currentModule) return;
    if (!confirm(`Xoá TOÀN BỘ storage của "${this._currentModule}"?\nKhông thể hoàn tác.`)) return;
    try {
      await API.storageClear(this._currentModule);
      App.log(`✓ Cleared storage của ${this._currentModule}`, "success");
      await this.refresh();
    } catch (e) {
      App.log(`✗ Clear: ${e.message}`, "error");
    }
  },
};

window.StorageUI = StorageUI;