class EditorManager {
  constructor() {
    this.cm = null;
    this.tabs = [];
    this.activeIdx = -1;
    this.globalSettings = null;
    this._loadedThemes = new Set(["dracula"]);
    this._lastMerge = 0;
    this.els = {
      container: document.getElementById("editor"),
      tabs: document.getElementById("editorTabs"),
      empty: document.getElementById("editorEmpty"),
    };
  }

  init() {
    const ua = navigator.userAgent || "";
    const isAndroid = /Android/i.test(ua);

    // ⭐ v1.4.1: extraKeys + foldGutter config
    const cmOpts = {
      lineNumbers: true,
      theme: "dracula",
      matchBrackets: true,
      autoCloseBrackets: true,
      styleActiveLine: true,
      indentUnit: 4,
      tabSize: 4,
      lineWrapping: false,
      viewportMargin: Infinity,
      autofocus: false,

      foldGutter: true,
      gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
      extraKeys: {
        "Ctrl-Q": (cm) => cm.foldCode(cm.getCursor()),
        "Ctrl-Shift-[": () => this.foldAll(),
        "Ctrl-Shift-]": () => this.unfoldAll(),
      },
    };

    if (isAndroid) {
      cmOpts.inputStyle = "contenteditable";
      cmOpts.spellcheck = false;
      cmOpts.autocorrect = "off";
      cmOpts.autocapitalize = "off";
      cmOpts.electricChars = false;
    }

    this.cm = CodeMirror.fromTextArea(this.els.container, cmOpts);
    this.cm.getWrapperElement().style.display = "none";

    this._applyInputAttributes(isAndroid);

    if (isAndroid) {
      this._fixAndroidLineMerge();
    }

    this.loadSettings();

    const foldBtn = document.getElementById("foldBtn");
    if (foldBtn) {
      foldBtn.addEventListener("click", () => this.toggleFoldAll());
    }

    this.cm.on("change", () => {
      if (this.activeIdx >= 0) {
        const tab = this.tabs[this.activeIdx];
        const current = this.cm.getValue();
        const isDirty = current !== tab.content;
        if (tab.dirty !== isDirty) {
          tab.dirty = isDirty;
          this.renderTabs();
        }
      }
      this._updateUndoRedoButtons();
    });

    this.cm.on("cursorActivity", () => this._updateUndoRedoButtons());

    this._updateUndoRedoButtons();
  }

  // ⭐ v1.4.1: Chọn fold range finder theo mode hiện tại
  _getFoldRangeFinder() {
    const mode = (this.cm && this.cm.getMode() && this.cm.getMode().name) || "";
    const fold = (window.CodeMirror && window.CodeMirror.fold) || {};
    if (mode.indexOf("python") >= 0 && fold.indent) return fold.indent;
    if (mode.indexOf("javascript") >= 0 && fold.brace) return fold.brace;
    if (mode.indexOf("css") >= 0 && fold.brace) return fold.brace;
    if (mode.indexOf("htmlmixed") >= 0 && fold.brace) return fold.brace;
    if (mode.indexOf("xml") >= 0 && fold.brace) return fold.brace;
    if (fold.brace) return fold.brace;
    if (fold.indent) return fold.indent;
    return null;
  }

  // ⭐ v1.4.1 FIX: Fold từ CUỐI về ĐẦU để line index không bị shift
  foldAll() {
    if (!this.cm) return;
    const cm = this.cm;
    const total = cm.lineCount();
    const finder = this._getFoldRangeFinder();

    cm.operation(() => {
      for (let i = total - 1; i >= 0; i--) {
        try {
          if (finder) {
            cm.foldCode({ line: i, ch: 0 }, finder, "fold");
          } else {
            cm.foldCode({ line: i, ch: 0 });
          }
        } catch (e) { /* skip line không fold được */ }
      }
    });
    setTimeout(() => { try { cm.refresh(); } catch (e) {} }, 30);
  }

  // ⭐ v1.4.1 FIX: Unfold toàn bộ bằng cách clear tất cả fold marks
  unfoldAll() {
    if (!this.cm) return;
    const cm = this.cm;
    cm.operation(() => {
      const marks = cm.getAllMarks();
      for (const m of marks) {
        const cls = (m.widgetNode && m.widgetNode.className) || "";
        if (cls.indexOf("CodeMirror-foldmarker") >= 0) {
          try { m.clear(); } catch (e) {}
        }
      }
      // Fallback: quét từng line
      try {
        for (let i = 0; i < cm.lineCount(); i++) {
          const marksAtLine = cm.findMarksAt({ line: i, ch: 0 });
          for (const m of marksAtLine) {
            const cls = (m.widgetNode && m.widgetNode.className) || "";
            if (cls.indexOf("CodeMirror-foldmarker") >= 0) {
              try { m.clear(); } catch (e) {}
            }
          }
        }
      } catch (e) { /* ignore */ }
    });
    setTimeout(() => { try { cm.refresh(); } catch (e) {} }, 30);
  }

  toggleFoldAll() {
    if (!this.cm) return;
    const cm = this.cm;
    const marks = cm.getAllMarks();
    let hasFold = false;
    for (const m of marks) {
      const cls = (m.widgetNode && m.widgetNode.className) || "";
      if (cls.indexOf("CodeMirror-foldmarker") >= 0) {
        hasFold = true;
        break;
      }
    }
    if (hasFold) this.unfoldAll();
    else this.foldAll();
  }

  // ============================================================== //
  //  Undo / Redo
  // ============================================================== //
  undo() {
    if (!this.cm) return;
    try { this.cm.undo(); } catch (e) { /* ignore */ }
    this._updateUndoRedoButtons();
  }

  redo() {
    if (!this.cm) return;
    try { this.cm.redo(); } catch (e) { /* ignore */ }
    this._updateUndoRedoButtons();
  }

  canUndo() {
    if (!this.cm) return false;
    try { return this.cm.historySize().undo > 0; } catch (e) { return false; }
  }

  canRedo() {
    if (!this.cm) return false;
    try { return this.cm.historySize().redo > 0; } catch (e) { return false; }
  }

  _updateUndoRedoButtons() {
    const undoBtn = document.getElementById("undoBtn");
    const redoBtn = document.getElementById("redoBtn");
    if (undoBtn) undoBtn.disabled = !this.canUndo();
    if (redoBtn) redoBtn.disabled = !this.canRedo();
  }

  _applyInputAttributes(isAndroid) {
    try {
      const input = this.cm.getInputField && this.cm.getInputField();
      if (!input) return;
      input.setAttribute("autocomplete", "off");
      if (isAndroid) {
        input.setAttribute("autocorrect", "off");
        input.setAttribute("autocapitalize", "off");
        input.setAttribute("spellcheck", "false");
        try { input.style.fontSize = "16px"; } catch (e) {}
      }
    } catch (e) { /* ignore */ }
  }

  _fixAndroidLineMerge() {
    const cm = this.cm;
    const input = cm.getInputField && cm.getInputField();
    if (!input) return;

    const now = () => (window.performance && performance.now) ? performance.now() : Date.now();

    const mergeBackward = (e) => {
      if (e.defaultPrevented) return;
      const t = now();
      if (t - this._lastMerge < 100) return;
      const sels = cm.listSelections();
      if (sels.length !== 1 || !sels[0].empty) return;
      const cur = cm.getCursor();
      if (cur.ch === 0 && cur.line > 0) {
        e.preventDefault();
        this._lastMerge = t;
        try { cm.execCommand("delCharBefore"); } catch (err) { /* ignore */ }
      }
    };

    const mergeForward = (e) => {
      if (e.defaultPrevented) return;
      const t = now();
      if (t - this._lastMerge < 100) return;
      const sels = cm.listSelections();
      if (sels.length !== 1 || !sels[0].empty) return;
      const cur = cm.getCursor();
      const lineText = cm.getLine(cur.line) || "";
      if (cur.ch >= lineText.length && cur.line < cm.lineCount() - 1) {
        e.preventDefault();
        this._lastMerge = t;
        try {
          cm.replaceRange(
            "",
            { line: cur.line, ch: lineText.length },
            { line: cur.line + 1, ch: 0 }
          );
        } catch (err) { /* ignore */ }
      }
    };

    if ("onbeforeinput" in input) {
      input.addEventListener("beforeinput", (e) => {
        if (!e.inputType) return;
        if (e.inputType === "deleteContentBackward") mergeBackward(e);
        else if (e.inputType === "deleteContentForward") mergeForward(e);
      }, true);
    }

    input.addEventListener("keydown", (e) => {
      if (e.isComposing) return;
      const isBackspace = e.key === "Backspace" || e.keyCode === 8;
      const isDelete = e.key === "Delete" || e.keyCode === 46;
      if (isBackspace) mergeBackward(e);
      else if (isDelete) mergeForward(e);
    }, true);
  }

  async loadSettings() {
    try {
      const res = await fetch("/api/settings").then(r => r.json());
      if (res && res.ok) {
        this.globalSettings = res.settings;
        this.applySettings();
      }
    } catch (e) {
      console.warn("[Editor] settings load failed", e);
    }
  }

  onSettingsChanged(newSettings) {
    if (!newSettings || typeof newSettings !== "object") return;
    this.globalSettings = newSettings;
    this.applySettings();
  }

  applySettings() {
    if (!this.cm || !this.globalSettings) return;
    const ed = this.globalSettings.editor || {};
    if (typeof ed.font_size === "number") {
      this.cm.getWrapperElement().style.fontSize = ed.font_size + "px";
    }
    if (typeof ed.tab_size === "number") {
      this.cm.setOption("tabSize", ed.tab_size);
      this.cm.setOption("indentUnit", ed.tab_size);
    }
    if (typeof ed.line_wrap === "boolean") {
      this.cm.setOption("lineWrapping", ed.line_wrap);
    }
    const theme = this.globalSettings.theme || "dracula";
    this._applyTheme(theme);
    setTimeout(() => {
      try { if (this.cm) this.cm.refresh(); } catch (e) {}
    }, 30);
  }

  _applyTheme(name) {
    if (!this.cm) return;
    const known = ["default", "dracula", "material", "monokai", "solarized", "eclipse"];
    let theme = String(name || "dracula").toLowerCase();
    if (!known.includes(theme)) theme = "dracula";

    if (theme !== "default" && !this._loadedThemes.has(theme)) {
      try {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href =
          "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/" +
          theme + ".min.css";
        link.dataset.cmTheme = theme;
        link.onload = () => {
          try { this.cm && this.cm.refresh(); } catch (e) {}
        };
        document.head.appendChild(link);
        this._loadedThemes.add(theme);
      } catch (e) { /* ignore */ }
    }
    try {
      this.cm.setOption("theme", theme);
    } catch (e) { /* ignore */ }
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
    const doc = CodeMirror.Doc(content || "", this._mode(path));
    this.tabs.push({
      project, path,
      name: path.split("/").pop(),
      content: content || "",
      doc: doc,
      dirty: false,
    });
    this.activeIdx = this.tabs.length - 1;
    this._load();
    this.renderTabs();
  }

  activate(idx) {
    if (idx < 0 || idx >= this.tabs.length || idx === this.activeIdx) return;
    this.activeIdx = idx;
    this._load();
    this.renderTabs();
  }

  _load() {
    if (this.activeIdx < 0) {
      this.cm.getWrapperElement().style.display = "none";
      this.els.empty.classList.remove("hidden");
      this._updateUndoRedoButtons();
      return;
    }
    this.els.empty.classList.add("hidden");
    this.cm.getWrapperElement().style.display = "";
    const tab = this.tabs[this.activeIdx];

    if (!tab.doc) {
      tab.doc = CodeMirror.Doc(tab.content || "", this._mode(tab.path));
    }
    this.cm.swapDoc(tab.doc);

    setTimeout(() => this.cm.refresh(), 20);
    this._updateUndoRedoButtons();

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
      this._updateUndoRedoButtons();
      App.log(`✓ Saved ${tab.path}`, "success");
    } catch (e) {
      App.log(`✗ Save failed: ${e.message}`, "error");
    }
  }

  currentTab() {
    return this.activeIdx >= 0 ? this.tabs[this.activeIdx] : null;
  }

  getCm(project, path) {
    const tab = this.currentTab();
    if (!tab) return null;
    if (tab.project === project && tab.path === path) return this.cm;
    return null;
  }

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
      } catch (e) {}
    }, 50);
  }
}