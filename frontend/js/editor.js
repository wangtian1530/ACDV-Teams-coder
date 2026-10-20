class EditorManager {
  constructor() {
    this.cm = null;
    this.tabs = [];           // {project, path, name, content, dirty}
    this.activeIdx = -1;
    this.els = {
      container: document.getElementById("editor"),
      tabs: document.getElementById("editorTabs"),
      empty: document.getElementById("editorEmpty"),
    };
  }

  init() {
    this.cm = CodeMirror.fromTextArea(this.els.container, {
      lineNumbers: true,
      theme: "dracula",
      matchBrackets: true,
      autoCloseBrackets: true,
      styleActiveLine: true,
      indentUnit: 4,
      tabSize: 4,
      lineWrapping: true,
      viewportMargin: Infinity,
    });
    this.cm.getWrapperElement().style.display = "none";

    this.cm.on("change", () => {
      if (this.activeIdx < 0) return;
      const tab = this.tabs[this.activeIdx];
      if (!tab.dirty) {
        tab.dirty = true;
        this.renderTabs();
      }
    });
  }

  _mode(path) {
    const p = (path || "").toLowerCase();
    if (p.endsWith(".py")) return "python";
    if (p.endsWith(".js")) return "javascript";
    if (p.endsWith(".html")) return "htmlmixed";
    if (p.endsWith(".css")) return "css";
    if (p.endsWith(".md")) return "markdown";
    if (p.endsWith(".xml")) return "xml";
    return "null";
  }

  open(project, path, content) {
    const existing = this.tabs.findIndex(t => t.project === project && t.path === path);
    if (existing >= 0) {
      this.activate(existing);
      return;
    }
    this.tabs.push({
      project, path,
      name: path.split("/").pop(),
      content: content || "",
      dirty: false,
    });
    this.activeIdx = this.tabs.length - 1;
    this._load();
    this.renderTabs();
  }

  activate(idx) {
    if (idx < 0 || idx >= this.tabs.length || idx === this.activeIdx) return;
    if (this.activeIdx >= 0) {
      this.tabs[this.activeIdx].content = this.cm.getValue();
    }
    this.activeIdx = idx;
    this._load();
    this.renderTabs();
  }

  _load() {
    if (this.activeIdx < 0) {
      this.cm.getWrapperElement().style.display = "none";
      this.els.empty.classList.remove("hidden");
      return;
    }
    this.els.empty.classList.add("hidden");
    this.cm.getWrapperElement().style.display = "";
    const tab = this.tabs[this.activeIdx];
    this.cm.setOption("mode", this._mode(tab.path));
    this.cm.setValue(tab.content || "");
    this.cm.clearHistory();
    setTimeout(() => this.cm.refresh(), 20);

    // ⭐ v1.3.0: re-render diagnostics markers for the newly active file
    setTimeout(() => {
      if (window.DiagnosticsUI && this.activeIdx >= 0) {
        const t = this.tabs[this.activeIdx];
        const diags = window.DiagnosticsUI.getDiagnostics(t.project, t.path);
        window.DiagnosticsUI.setFileDiagnostics(t.project, t.path, diags);
      }
    }, 60);
  }

  close(idx) {
    if (idx < 0 || idx >= this.tabs.length) return;
    const tab = this.tabs[idx];
    if (tab.dirty) {
      if (!confirm(`Close ${tab.name}? Unsaved changes will be lost.`)) return;
    }
    this.tabs.splice(idx, 1);
    if (this.tabs.length === 0) {
      this.activeIdx = -1;
    } else if (this.activeIdx >= this.tabs.length) {
      this.activeIdx = this.tabs.length - 1;
    } else if (this.activeIdx > idx) {
      this.activeIdx--;
    }
    this._load();
    this.renderTabs();
  }

  renderTabs() {
    this.els.tabs.innerHTML = "";
    this.tabs.forEach((tab, i) => {
      const el = document.createElement("div");
      el.className = "editor-tab"
        + (i === this.activeIdx ? " active" : "")
        + (tab.dirty ? " dirty" : "");
      const label = document.createElement("span");
      label.textContent = tab.name;
      const closeBtn = document.createElement("span");
      closeBtn.className = "close";
      closeBtn.textContent = "×";
      if (tab.dirty) closeBtn.textContent = "";
      closeBtn.title = "Close";
      closeBtn.onclick = (e) => { e.stopPropagation(); this.close(i); };
      el.appendChild(label);
      el.appendChild(closeBtn);
      el.onclick = () => this.activate(i);
      this.els.tabs.appendChild(el);
    });
  }

  async save() {
    if (this.activeIdx < 0) return;
    const tab = this.tabs[this.activeIdx];
    const content = this.cm.getValue();
    try {
      await API.writeFile(tab.project, tab.path, content);
      tab.content = content;
      tab.dirty = false;
      this.renderTabs();
      App.log(`✓ Saved ${tab.path}`, "success");
    } catch (e) {
      App.log(`✗ Save failed: ${e.message}`, "error");
    }
  }

  currentTab() {
    return this.activeIdx >= 0 ? this.tabs[this.activeIdx] : null;
  }

  // ⭐ v1.3.0: for DiagnosticsUI.cmForPath()
  getCm(project, path) {
    const tab = this.currentTab();
    if (!tab) return null;
    if (tab.project === project && tab.path === path) return this.cm;
    return null;
  }

  // ⭐ v1.3.0: for DiagnosticsUI.jumpTo()
  async openFileAtLine(project, path, line, column) {
    let idx = this.tabs.findIndex(t => t.project === project && t.path === path);
    if (idx < 0) {
      try {
        const res = await API.readFile(project, path);
        const content = typeof res === "string" ? res : (res.content || "");
        this.open(project, path, content);
        idx = this.tabs.length - 1;
      } catch (e) {
        if (window.App) App.log(`✗ Cannot open file: ${e.message}`, "error");
        return;
      }
    } else {
      this.activate(idx);
    }

    const cm = this.cm;
    if (!cm) return;
    setTimeout(() => {
      const ln = Math.max(0, (line || 1) - 1);
      const ch = Math.max(0, (column || 1) - 1);
      try {
        cm.setCursor({ line: ln, ch });
        cm.focus();
        cm.scrollIntoView({ line: ln, ch }, 80);
        cm.addLineClass(ln, "background", "cm-flash-line");
        setTimeout(() => cm.removeLineClass(ln, "background", "cm-flash-line"), 900);
      } catch (e) { /* ignore */ }
    }, 50);
  }
}