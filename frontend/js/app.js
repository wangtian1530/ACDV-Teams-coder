const App = {
  editor: null,
  ws: null,
  _promptResolve: null,
  _run: { project: null, path: null, running: false },

  // ============================================================ //
  //  INIT
  // ============================================================ //
  async init() {
    this.editor = new EditorManager();
    this.editor.init();

    // ---- WebSocket ----
    this.ws = new WSClient();
    this.ws.on("open", () => {
      this._setOnline(true);
      this._refreshRunStatus();
    });
    this.ws.on("close", () => this._setOnline(false));
    this.ws.on("run_started", (m) => this._onRunStarted(m));
    this.ws.on("run_output", (m) => this._onRunOutput(m));
    this.ws.on("run_finished", (m) => this._onRunFinished(m));
    this.ws.on("module_action_result", (m) => this._onModuleActionResult(m));

    // ⭐ v1.3.0: route diagnostics WS messages
    this.ws.on("diagnostics_update", (m) => {
      if (window.DiagnosticsUI) window.DiagnosticsUI.handleWsMessage(m);
    });
    this.ws.on("diagnostics_cleared", () => {
      if (window.DiagnosticsUI) window.DiagnosticsUI.handleWsMessage({ type: "diagnostics_cleared" });
    });

    // ⭐ v1.3.0: toast helper (used by settings.js / diagnostics.js)
    window.AppToast = function (msg, type) {
      const t = document.createElement("div");
      t.textContent = msg;
      t.style.cssText =
        "position:fixed;bottom:50px;right:10px;" +
        "background:" + (type === "error" ? "#c33" : "#2a7a2a") + ";" +
        "color:#fff;padding:8px 16px;border-radius:4px;z-index:100000;" +
        "font:13px sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.3);";
      document.body.appendChild(t);
      setTimeout(() => t.remove(), 3000);
    };

    // ⭐ v1.3.0: AppEditor — wrapper for DiagnosticsUI
    window.AppEditor = {
      getCm(project, path) {
        return App.editor && typeof App.editor.getCm === "function"
          ? App.editor.getCm(project, path)
          : null;
      },
      async openFileAtLine(project, path, line, column) {
        if (App.editor && typeof App.editor.openFileAtLine === "function") {
          return App.editor.openFileAtLine(project, path, line, column);
        }
      },
    };

    this.ws.connect();

    // ---- Keyboard shortcuts ----
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        this.editor.save();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        this.runCurrent();
      }
    });

    this._bind();

    if (window.innerWidth < 768) {
      document.getElementById("bottomPanel").classList.add("collapsed");
    }

    await Explorer.loadProjects();
    this.log("ACDV-Teams Coder ready.");
    try {
      const s = await fetch("/api/status").then(r => r.json());
      this.log(`Backend v${s.version} · modules: ${(s.uptime_modules || []).length}`);
    } catch (e) {}
    this._refreshRunStatus();

    // ⭐ v1.3.0: load any existing diagnostics from server
    setTimeout(() => {
      if (window.DiagnosticsUI) window.DiagnosticsUI.refreshAll();
    }, 500);
  },

  // ============================================================ //
  //  BINDINGS
  // ============================================================ //
  _bind() {
    document.getElementById("menuBtn").onclick = () => {
      document.getElementById("sidebar").classList.toggle("open");
    };

    document.querySelectorAll(".sidebar-tabs .tab").forEach(t => {
      t.onclick = () => this.switchTab(t.dataset.tab);
    });

    const openModal = () => {
      document.getElementById("projectModal").classList.remove("hidden");
      setTimeout(() => document.getElementById("projectNameInput").focus(), 50);
    };
    ["newProjectBtn", "newProjectBtn2", "emptyNewProjectBtn"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.onclick = openModal;
    });

    const upBtn = document.getElementById("uploadProjectBtn");
    if (upBtn) upBtn.onclick = () => document.getElementById("projectZipInput").click();
    const pzIn = document.getElementById("projectZipInput");
    if (pzIn) pzIn.onchange = async (e) => {
      const f = e.target.files && e.target.files[0];
      e.target.value = "";
      if (f) await this._uploadProjectZip(f);
    };

    const upModBtn = document.getElementById("uploadModuleBtn");
    if (upModBtn) upModBtn.onclick = () => document.getElementById("moduleZipInput").click();
    const mzIn = document.getElementById("moduleZipInput");
    if (mzIn) mzIn.onchange = async (e) => {
      const f = e.target.files && e.target.files[0];
      e.target.value = "";
      if (f) await this._installModuleZip(f);
    };

    document.getElementById("modalCancel").onclick = () => {
      document.getElementById("projectModal").classList.add("hidden");
    };
    document.getElementById("modalCreate").onclick = () => this._createProject();
    document.getElementById("projectNameInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this._createProject();
    });

    document.getElementById("newFileBtn").onclick = () => Explorer.promptNewFile();
    document.getElementById("newFolderBtn").onclick = () => Explorer.promptNewFolder();
    document.getElementById("refreshTreeBtn").onclick = () => Explorer.refreshTree();

    document.getElementById("saveBtn").onclick = () => this.editor.save();

    const runBtn = document.getElementById("runBtn");
    if (runBtn) runBtn.onclick = () => this.runCurrent();
    const stopBtn = document.getElementById("stopRunBtn");
    if (stopBtn) stopBtn.onclick = () => this.stopRun();

    const logsBtn = document.getElementById("logsBtn");
    if (logsBtn) logsBtn.onclick = () => this.openLogsModal();

    // ⭐ v1.3.0: Problems + Settings
    const problemsBtn = document.getElementById("problemsBtn");
    if (problemsBtn) problemsBtn.onclick = () => {
      this._switchPanelTab("problems");
      document.getElementById("bottomPanel").classList.remove("collapsed");
      if (window.DiagnosticsUI) window.DiagnosticsUI.renderPanel();
    };
    const settingsBtn = document.getElementById("settingsBtn");
    if (settingsBtn) settingsBtn.onclick = () => {
      if (window.SettingsUI) window.SettingsUI.open();
    };

    document.querySelectorAll(".ptab").forEach(t => {
      t.onclick = () => this._switchPanelTab(t.dataset.ptab);
    });

    document.getElementById("clearOutputBtn").onclick = () => {
      const active = document.querySelector(".ptab.active");
      const tab = active ? active.dataset.ptab : "output";
      if (tab === "run") {
        const el = document.getElementById("runLog");
        if (el) el.textContent = "";
      } else if (tab === "problems") {
        if (window.DiagnosticsUI) {
          // clear all
          fetch("/api/diagnostics/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          }).catch(() => {});
        }
      } else {
        const el = document.getElementById("outputLog");
        if (el) el.textContent = "";
      }
    };

    document.getElementById("togglePanelBtn").onclick = () => {
      document.getElementById("bottomPanel").classList.toggle("collapsed");
    };

    document.querySelectorAll(".mb").forEach(btn => {
      btn.onclick = () => {
        const t = btn.dataset.mobileTab;
        if (t === "projects" || t === "explorer") {
          this.switchTab(t);
          document.getElementById("sidebar").classList.add("open");
        } else if (t === "editor") {
          document.getElementById("sidebar").classList.remove("open");
        } else if (t === "output") {
          document.getElementById("bottomPanel").classList.remove("collapsed");
        }
        document.querySelectorAll(".mb").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
      };
    });

    document.getElementById("promptCancel").onclick = () => {
      document.getElementById("promptModal").classList.add("hidden");
      if (this._promptResolve) { this._promptResolve(null); this._promptResolve = null; }
    };
    document.getElementById("promptOk").onclick = () => {
      const val = document.getElementById("promptInput").value.trim();
      document.getElementById("promptModal").classList.add("hidden");
      if (this._promptResolve) { this._promptResolve(val); this._promptResolve = null; }
    };
    document.getElementById("promptInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") document.getElementById("promptOk").click();
    });
  },

  // ============================================================ //
  //  RUN
  // ============================================================ //
  async runCurrent() {
    const tab = this.editor.currentTab();
    if (!tab) return alert("Không có file nào đang mở");
    if (tab.dirty) {
      try { await this.editor.save(); } catch (e) { return; }
    }
    try {
      document.getElementById("bottomPanel").classList.remove("collapsed");
      this._switchPanelTab("run");
      const runLog = document.getElementById("runLog");
      if (runLog) runLog.textContent = "";
      const hdr = document.getElementById("runHeader");
      if (hdr) hdr.textContent = `▶ Running ${tab.project}/${tab.path} …`;

      await API.runFile(tab.project, tab.path);
      this._run = { project: tab.project, path: tab.path, running: true };
      this._refreshRunStatus();
      this.log(`▶ ${tab.project}/${tab.path} — started`);
    } catch (e) {
      this.log(`✗ Run: ${e.message}`, "error");
      alert(e.message);
    }
  },

  async runFile(project, path) {
    const tab = this.editor.tabs.find(t => t.project === project && t.path === path);
    if (tab && tab.dirty) {
      try { await this.editor.save(); } catch (e) { return; }
    }
    try {
      document.getElementById("bottomPanel").classList.remove("collapsed");
      this._switchPanelTab("run");
      const runLog = document.getElementById("runLog");
      if (runLog) runLog.textContent = "";
      const hdr = document.getElementById("runHeader");
      if (hdr) hdr.textContent = `▶ Running ${project}/${path} …`;

      await API.runFile(project, path);
      this._run = { project, path, running: true };
      this._refreshRunStatus();
      this.log(`▶ ${project}/${path} — started`);
    } catch (e) {
      this.log(`✗ Run: ${e.message}`, "error");
      alert(e.message);
    }
  },

  async stopRun() {
    const stopBtn = document.getElementById("stopRunBtn");
    try {
      if (stopBtn) stopBtn.disabled = true;
      this.log("⏹ Stopping…");
      try { await API.stopRun(false); } catch (_) {}
      const stopped = await this._pollStopped(20, 500);
      if (stopped) {
        this.log("⏹ Stopped", "success");
        this._refreshRunStatus();
        return;
      }
      this.log("⚠ Process chưa dừng sau 10s — force kill (SIGKILL)?", "error");
      if (!confirm("Process vẫn chạy sau SIGTERM.\n\nForce kill (SIGKILL) process group?")) {
        this._refreshRunStatus();
        return;
      }
      try { await API.stopRun(true); } catch (_) {}
      const killed = await this._pollStopped(10, 500);
      if (killed) {
        this.log("⏹ Force-killed", "success");
      } else {
        this.log("✗ Process vẫn sống sau SIGKILL", "error");
      }
    } catch (e) {
      this.log(`✗ Stop: ${e.message}`, "error");
    } finally {
      if (stopBtn) stopBtn.disabled = false;
      this._refreshRunStatus();
    }
  },

  async _pollStopped(attempts, intervalMs) {
    for (let i = 0; i < attempts; i++) {
      await new Promise(r => setTimeout(r, intervalMs));
      try {
        const res = await API.runStatus();
        if (!res.status || !res.status.running) return true;
      } catch (_) {}
    }
    return false;
  },

  async _refreshRunStatus() {
    try {
      const res = await API.runStatus();
      const st = res.status || {};
      this._run.running = !!st.running;
      const runBtn = document.getElementById("runBtn");
      const stopBtn = document.getElementById("stopRunBtn");
      if (runBtn) runBtn.classList.toggle("hidden", !!st.running);
      if (stopBtn) stopBtn.classList.toggle("hidden", !st.running);
      const hdr = document.getElementById("runHeader");
      if (hdr && st.running) {
        hdr.textContent = `▶ Running ${st.project}/${st.path} (pid ${st.pid || "?"}) …`;
      }
    } catch (_) {}
  },

  _onRunStarted(m) {
    this._switchPanelTab("run");
    document.getElementById("bottomPanel").classList.remove("collapsed");
    const hdr = document.getElementById("runHeader");
    if (hdr) hdr.textContent = `▶ Running ${m.project}/${m.path} (pid ${m.pid || "?"}) …`;
    this._run = { project: m.project, path: m.path, running: true };
    this._refreshRunStatus();
  },

  _onRunOutput(m) {
    const el = document.getElementById("runLog");
    if (!el) return;
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 20;
    let text = "";
    if (Array.isArray(m.lines)) {
      text = m.lines.join("\n");
      if (m.lines.length) text += "\n";
    } else if (typeof m.line === "string") {
      text = m.line + "\n";
    }
    if (!text) return;
    el.textContent += text;
    if (el.textContent.length > 500000) {
      el.textContent = "[… trimmed older lines …]\n" + el.textContent.slice(-400000);
    }
    if (atBottom) el.scrollTop = el.scrollHeight;
  },

  _onRunFinished(m) {
    const el = document.getElementById("runLog");
    if (el) {
      el.textContent += `\n[exit code: ${m.exit_code}]\n`;
      el.scrollTop = el.scrollHeight;
    }
    const hdr = document.getElementById("runHeader");
    if (hdr) {
      hdr.textContent =
        `⏹ Finished ${m.project}/${m.path} (exit ${m.exit_code}) · log: ${m.log_name}`;
    }
    this._run.running = false;
    this.log(`⏹ ${m.project}/${m.path} — exit ${m.exit_code}`,
      m.exit_code === 0 ? "success" : "error");
    this._refreshRunStatus();
  },

  // ============================================================ //
  //  PANEL TABS
  // ============================================================ //
  _switchPanelTab(name) {
    document.querySelectorAll(".ptab").forEach(t =>
      t.classList.toggle("active", t.dataset.ptab === name));
    document.querySelectorAll(".panel-pane").forEach(p => p.classList.add("hidden"));
    const el = document.getElementById("pane-" + name);
    if (el) el.classList.remove("hidden");
    if (name === "problems" && window.DiagnosticsUI) {
      window.DiagnosticsUI.renderPanel();
    }
  },

  // ============================================================ //
  //  LOGS MODAL
  // ============================================================ //
  async openLogsModal() {
    const modal = document.getElementById("logsModal");
    modal.classList.remove("hidden");
    const preview = document.getElementById("logPreview");
    if (preview) preview.textContent = "";
    const dlBtn = document.getElementById("downloadLogBtn");
    if (dlBtn) dlBtn.disabled = true;
    await this._refreshLogsList();
  },

  async _refreshLogsList() {
    const list = document.getElementById("logList");
    if (!list) return;
    const project = Explorer.currentProject || "";
    list.innerHTML = "";
    try {
      const res = await API.listLogs(project);
      const logs = res.logs || [];
      if (!logs.length) {
        list.innerHTML = '<li class="log-item-empty">Chưa có log nào</li>';
        return;
      }
      logs.forEach(l => {
        const li = document.createElement("li");
        li.className = "log-item";
        const name = document.createElement("span");
        name.className = "log-name";
        name.textContent = l.name;
        name.title = l.name;
        const meta = document.createElement("span");
        meta.className = "log-meta";
        meta.textContent = `${(l.size / 1024).toFixed(1)} KB`;
        const del = document.createElement("button");
        del.className = "icon-btn small";
        del.textContent = "🗑";
        del.title = "Delete log";
        del.onclick = async (ev) => {
          ev.stopPropagation();
          if (!confirm(`Xoá log "${l.name}"?`)) return;
          try {
            await API.deleteLog(l.name);
            await this._refreshLogsList();
            const preview = document.getElementById("logPreview");
            if (preview) preview.textContent = "";
          } catch (e) { alert(e.message); }
        };
        li.appendChild(name);
        li.appendChild(meta);
        li.appendChild(del);
        li.onclick = () => this._previewLog(l.name);
        list.appendChild(li);
      });
    } catch (e) {
      list.innerHTML = `<li class="log-item-empty">✗ ${e.message}</li>`;
    }
  },

  async _previewLog(name) {
    const preview = document.getElementById("logPreview");
    if (!preview) return;
    try {
      const res = await API.readLog(name);
      preview.textContent = res.content || "";
      preview.scrollTop = preview.scrollHeight;
      const dlBtn = document.getElementById("downloadLogBtn");
      if (dlBtn) {
        dlBtn.onclick = () => {
          const blob = new Blob([res.content || ""], { type: "text/plain;charset=utf-8" });
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = name;
          a.click();
          setTimeout(() => URL.revokeObjectURL(a.href), 1000);
        };
        dlBtn.disabled = false;
      }
    } catch (e) {
      preview.textContent = "✗ " + e.message;
    }
  },

  // ============================================================ //
  //  MODULE BUTTONS
  // ============================================================ //
  async _triggerModuleButton(moduleName, btn) {
    const action = btn.action || "route";
    if (btn.confirm && !confirm(btn.confirm)) return;

    if (action === "run") {
      const p = btn.params || {};
      let project = p.project || Explorer.currentProject;
      let path = p.path;
      if (!project) return alert("Chưa chọn project");
      if (!path) {
        path = await this.prompt("Run file", "Path in project (vd: main.py):");
        if (!path) return;
      }
      return this.runFile(project, path);
    }

    if (action === "open_web") {
      return window.open(`/module/${encodeURIComponent(moduleName)}/`, "_blank");
    }

    if (action === "route") {
      const p = btn.params || {};
      try {
        const r = await API.request(p.path, p.method || "POST", p.body || null);
        this.log(`✓ ${btn.label || btn.id}: ${JSON.stringify(r).slice(0, 200)}`, "success");
      } catch (e) {
        this.log(`✗ ${btn.label || btn.id}: ${e.message}`, "error");
      }
      return;
    }

    if (action === "custom") {
      this.ws.send({
        type: "module_action",
        module: moduleName,
        button_id: btn.id,
        params: btn.params || {},
      });
      return;
    }

    this.log(`✗ Unknown action: ${action}`, "error");
  },

  _onModuleActionResult(m) {
    const tag = `[${m.module}/${m.button_id}]`;
    if (m.ok) {
      const s = typeof m.result === "object"
        ? JSON.stringify(m.result).slice(0, 300)
        : String(m.result || "");
      this.log(`✓ ${tag} ${s}`, "success");
    } else {
      this.log(`✗ ${tag} ${m.error}`, "error");
    }
  },

  // ============================================================ //
  //  PROJECTS
  // ============================================================ //
  async _createProject() {
    const name = document.getElementById("projectNameInput").value.trim();
    const lang = document.getElementById("projectLangSelect").value;
    if (!name) return alert("Enter project name");
    try {
      await API.createProject(name, lang);
      document.getElementById("projectModal").classList.add("hidden");
      document.getElementById("projectNameInput").value = "";
      this.log(`✓ Created project ${name}`, "success");
      await Explorer.loadProjects();
      await Explorer.openProject(name);
    } catch (e) { alert(e.message); }
  },

  async _uploadProjectZip(file) {
    if (!file.name.toLowerCase().endsWith(".zip")) return alert("Chọn file .zip");
    const defName = file.name.replace(/\.zip$/i, "").replace(/[^a-zA-Z0-9_\-]/g, "_");
    const name = (await this.prompt("Upload Project ZIP", "Project name:")) || defName;
    if (!name) return;
    try {
      this.log(`Uploading ${file.name} …`);
      const b64 = await this._fileToBase64(file);
      const res = await API.uploadProject(name, b64);
      const p = res.project || res;
      this.log(`✓ Uploaded ${name} (${p.files_extracted ?? "?"} files)`, "success");
      await Explorer.loadProjects();
      await Explorer.openProject(name);
    } catch (e) {
      this.log(`✗ Upload failed: ${e.message}`, "error");
      alert(e.message);
    }
  },

  async _installModuleZip(file) {
    if (!file.name.toLowerCase().endsWith(".zip")) return alert("Chọn file .zip");
    try {
      this.log(`Installing module ${file.name} …`);
      const b64 = await this._fileToBase64(file);
      const res = await API.installModule(b64);
      const meta = res.module || {};
      this.log(`✓ Module installed: ${meta.name || "?"} v${meta.version || "?"}`, "success");
      await this.loadModules();
    } catch (e) {
      this.log(`✗ Install failed: ${e.message}`, "error");
      alert(e.message);
    }
  },

  _fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const s = String(reader.result || "");
        const i = s.indexOf(",");
        resolve(i >= 0 ? s.slice(i + 1) : s);
      };
      reader.onerror = () => reject(reader.error || new Error("read error"));
      reader.readAsDataURL(file);
    });
  },

  // ============================================================ //
  //  TABS
  // ============================================================ //
  switchTab(name) {
    document.querySelectorAll(".sidebar-tabs .tab").forEach(t =>
      t.classList.toggle("active", t.dataset.tab === name));
    document.querySelectorAll(".tab-body").forEach(b => b.classList.add("hidden"));
    const el = document.getElementById("tab-" + name);
    if (el) el.classList.remove("hidden");
    if (name === "modules") this.loadModules();
    if (name === "projects") Explorer.loadProjects();
  },

  // ============================================================ //
  //  MODULES
  // ============================================================ //
  async loadModules() {
    try {
      const data = await API.request("/api/modules");
      const list = document.getElementById("moduleList");
      const actionsEl = document.getElementById("moduleActions");
      if (!list) return;
      list.innerHTML = "";
      if (actionsEl) actionsEl.innerHTML = "";

      const entries = Object.entries(data || {});
      if (!entries.length) {
        list.innerHTML = '<li class="module-empty">No modules installed</li>';
        return;
      }

      entries.forEach(([name, meta]) => {
        const li = document.createElement("li");
        li.className = "module-item";

        const icon = document.createElement("span");
        icon.textContent = "🧩";
        const label = document.createElement("span");
        label.textContent = name;
        label.style.overflow = "hidden";
        label.style.textOverflow = "ellipsis";
        const ver = document.createElement("span");
        ver.className = "module-version";
        ver.textContent = `v${meta.version || "?"}`;

        const actions = document.createElement("div");
        actions.className = "module-actions";

        if (meta.has_web_ui) {
          const b = document.createElement("button");
          b.className = "icon-btn small";
          b.title = "Open module UI";
          b.textContent = "🌐";
          b.onclick = (ev) => {
            ev.stopPropagation();
            window.open(`/module/${encodeURIComponent(name)}/`, "_blank");
          };
          actions.appendChild(b);
        }

        const reload = document.createElement("button");
        reload.className = "icon-btn small";
        reload.title = "Reload module";
        reload.textContent = "⟳";
        reload.onclick = async (ev) => {
          ev.stopPropagation();
          try {
            await API.reloadModule(name);
            this.log(`✓ Reloaded ${name}`, "success");
            await this.loadModules();
          } catch (e) {
            this.log(`✗ ${e.message}`, "error");
          }
        };
        actions.appendChild(reload);

        const del = document.createElement("button");
        del.className = "icon-btn small";
        del.title = "Uninstall module";
        del.textContent = "🗑";
        del.onclick = async (ev) => {
          ev.stopPropagation();
          if (!confirm(`Uninstall module "${name}"?`)) return;
          try {
            await API.uninstallModule(name);
            this.log(`✓ Uninstalled ${name}`, "success");
            await this.loadModules();
          } catch (e) {
            this.log(`✗ ${e.message}`, "error");
          }
        };
        actions.appendChild(del);

        li.appendChild(icon);
        li.appendChild(label);
        li.appendChild(ver);
        li.appendChild(actions);
        list.appendChild(li);

        const btns = meta.ui_buttons || [];
        if (btns.length && actionsEl) {
          const group = document.createElement("div");
          group.className = "module-actions-group";
          const head = document.createElement("div");
          head.className = "module-actions-head";
          head.textContent = name;
          group.appendChild(head);
          btns.forEach(btn => {
            const b = document.createElement("button");
            b.className = "btn btn-sm" + (btn.color ? " btn-" + btn.color : "");
            b.textContent = (btn.icon ? btn.icon + " " : "") + (btn.label || btn.id);
            b.title = btn.title || btn.confirm || "";
            b.onclick = () => this._triggerModuleButton(name, btn);
            group.appendChild(b);
          });
          actionsEl.appendChild(group);
        }
      });
    } catch (e) {
      this.log(`✗ Load modules: ${e.message}`, "error");
    }
  },

  // ============================================================ //
  //  FILES
  // ============================================================ //
  async openFile(project, path) {
    try {
      const res = await API.readFile(project, path);
      const content = typeof res === "string" ? res : (res.content || "");
      this.editor.open(project, path, content);
      if (window.innerWidth < 768) {
        document.getElementById("sidebar").classList.remove("open");
      }
    } catch (e) {
      this.log(`✗ Open file: ${e.message}`, "error");
    }
  },

  // ============================================================ //
  //  HELPERS
  // ============================================================ //
  prompt(title, placeholder) {
    document.getElementById("promptTitle").textContent = title;
    const inp = document.getElementById("promptInput");
    inp.value = "";
    inp.placeholder = placeholder || "";
    document.getElementById("promptModal").classList.remove("hidden");
    setTimeout(() => inp.focus(), 50);
    return new Promise(resolve => { this._promptResolve = resolve; });
  },

  log(msg, kind) {
    const out = document.getElementById("outputLog");
    if (!out) return;
    const time = new Date().toLocaleTimeString();
    let prefix = "";
    if (kind === "success") prefix = "✓";
    else if (kind === "error") prefix = "✗";
    out.textContent += `[${time}] ${prefix ? prefix + " " : ""}${msg}\n`;
    if (out.textContent.length > 200000) {
      out.textContent = "[… trimmed older lines …]\n" + out.textContent.slice(-150000);
    }
    out.scrollTop = out.scrollHeight;
  },

  _setOnline(online) {
    const dot = document.getElementById("connDot");
    if (!dot) return;
    dot.classList.toggle("online", online);
    dot.classList.toggle("offline", !online);
    dot.title = online ? "Connected" : "Disconnected";
  },
};

window.addEventListener("DOMContentLoaded", () => App.init());