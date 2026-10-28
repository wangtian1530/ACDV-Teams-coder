const MODE_SCRIPTS = {
  "python":                  "python/python",
  "javascript":              "javascript/javascript",
  "htmlmixed":               "htmlmixed/htmlmixed",
  "css":                     "css/css",
  "markdown":                "markdown/markdown",
  "xml":                     "xml/xml",
  "text/typescript":         "javascript/typescript",
  "text/x-scss":             "css/scss",
  "text/x-less":             "css/less",
  "sass":                    "sass/sass",
  "stylus":                  "stylus/stylus",
  "yaml":                    "yaml/yaml",
  "toml":                    "toml/toml",
  "properties":              "properties/properties",
  "dockerfile":              "dockerfile/dockerfile",
  "text/x-sql":              "sql/sql",
  "text/x-vue":              "vue/vue",
  "text/x-pug":              "pug/pug",
  "coffeescript":            "coffeescript/coffeescript",
  "powershell":              "powershell/powershell",
  "application/x-httpd-php": "php/php",
  "ruby":                    "ruby/ruby",
  "perl":                    "perl/perl",
  "lua":                     "lua/lua",
  "r":                       "r/r",
  "text/x-csrc":             "clike/clike",
  "text/x-c++src":           "clike/clike",
  "text/x-objectivec":       "clike/clike",
  "text/x-java":             "clike/clike",
  "text/x-kotlin":           "clike/clike",
  "text/x-csharp":           "clike/clike",
  "text/x-scala":            "clike/clike",
  "dart":                    "dart/dart",
  "swift":                   "swift/swift",
  "text/x-go":               "go/go",
  "text/x-rustsrc":          "rust/rust",
  "clojure":                 "clojure/clojure",
  "haskell":                 "haskell/haskell",
  "shell":                   "shell/shell",
  "groovy":                  "groovy/groovy",
  "julia":                   "julia/julia",
  "scheme":                  "scheme/scheme",
  "tcl":                     "tcl/tcl",
  "verilog":                 "verilog/verilog",
  "vhdl":                    "vhdl/vhdl",
  "smalltalk":               "smalltalk/smalltalk",
  "pascal":                  "pascal/pascal",
  "haxe":                    "haxe/haxe",
  "erlang":                  "erlang/erlang",
  "fortran":                 "fortran/fortran",
  "gherkin":                 "gherkin/gherkin",
};

const CM_CDN = "https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/";


class EditorManager {
  constructor() {
    this.cm = null;
    this.tabs = [];
    this.activeIdx = -1;
    this.globalSettings = null;
    this._loadedThemes = new Set(["dracula"]);
    this._lastMerge = 0;

    this._loadedModeScripts = new Set([
      "python/python", "javascript/javascript", "htmlmixed/htmlmixed",
      "css/css", "xml/xml", "markdown/markdown",
    ]);
    this._loadingModeScripts = {};

    this.els = {
      container: document.getElementById("editor"),
      tabs: document.getElementById("editorTabs"),
      empty: document.getElementById("editorEmpty"),
    };
  }

  init() {
    const ua = navigator.userAgent || "";
    const isAndroid = /Android/i.test(ua);

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

  _mode(path) {
    const p = (path || "").toLowerCase();
    const base = p.split("/").pop() || "";
    if (base === "dockerfile" || base === "containerfile") return "dockerfile";
    if (/\.(py|pyw|pyi)$/.test(p)) return "python";
    if (/\.(js|mjs|cjs|jsx)$/.test(p)) return "javascript";
    if (/\.(ts|tsx)$/.test(p)) return "text/typescript";
    if (/\.(html|htm|xhtml)$/.test(p)) return "htmlmixed";
    if (/\.vue$/.test(p)) return "text/x-vue";
    if (/\.(pug|jade)$/.test(p)) return "text/x-pug";
    if (/\.css$/.test(p)) return "css";
    if (/\.scss$/.test(p)) return "text/x-scss";
    if (/\.sass$/.test(p)) return "sass";
    if (/\.less$/.test(p)) return "text/x-less";
    if (/\.styl(us)?$/.test(p)) return "stylus";
    if (/\.(md|markdown|mdown|mkd)$/.test(p)) return "markdown";
    if (/\.(json|jsonc|json5)$/.test(p)) return "javascript";
    if (/\.(xml|xsl|xslt|svg|rss|atom|plist|dtd)$/.test(p)) return "xml";
    if (/\.(yaml|yml)$/.test(p)) return "yaml";
    if (/\.toml$/.test(p)) return "toml";
    if (/\.(ini|cfg|conf|properties|env)$/.test(p)) return "properties";
    if (/\.(sql|ddl|dml)$/.test(p)) return "text/x-sql";
    if (/\.(sh|bash|zsh|ksh|fish)$/.test(p)) return "shell";
    if (/\.coffee$/.test(p)) return "coffeescript";
    if (/\.(ps1|psm1|psd1)$/.test(p)) return "powershell";
    if (/\.(php|phtml|php3|php4|php5|phps)$/.test(p)) return "application/x-httpd-php";
    if (/\.(rb|rake|gemspec|ru)$/.test(p)) return "ruby";
    if (/\.(pl|pm|pod|t)$/.test(p)) return "perl";
    if (/\.lua$/.test(p)) return "lua";
    if (/\.(r|rmd)$/.test(p)) return "r";
    if (/\.jl$/.test(p)) return "julia";
    if (/\.(c|h)$/.test(p)) return "text/x-csrc";
    if (/\.(cpp|cc|cxx|c\+\+|hpp|hxx|hh|h\+\+)$/.test(p)) return "text/x-c++src";
    if (/\.(m|mm)$/.test(p)) return "text/x-objectivec";
    if (/\.java$/.test(p)) return "text/x-java";
    if (/\.(kt|kts)$/.test(p)) return "text/x-kotlin";
    if (/\.cs$/.test(p)) return "text/x-csharp";
    if (/\.(scala|sc)$/.test(p)) return "text/x-scala";
    if (/\.dart$/.test(p)) return "dart";
    if (/\.swift$/.test(p)) return "swift";
    if (/\.go$/.test(p)) return "text/x-go";
    if (/\.rs$/.test(p)) return "text/x-rustsrc";
    if (/\.(clj|cljs|cljc|edn)$/.test(p)) return "clojure";
    if (/\.(hs|lhs)$/.test(p)) return "haskell";
    if (/\.(scm|ss)$/.test(p)) return "scheme";
    if (/\.(groovy|gradle)$/.test(p)) return "groovy";
    if (/\.(tcl|tk)$/.test(p)) return "tcl";
    if (/\.(v|sv|svh)$/.test(p)) return "verilog";
    if (/\.(vhd|vhdl)$/.test(p)) return "vhdl";
    if (/\.st$/.test(p)) return "smalltalk";
    if (/\.(pas|pp|dpr)$/.test(p)) return "pascal";
    if (/\.(hx|hxml)$/.test(p)) return "haxe";
    if (/\.(erl|hrl)$/.test(p)) return "erlang";
    if (/\.(f|for|f90|f95|f03)$/.test(p)) return "fortran";
    if (/\.feature$/.test(p)) return "gherkin";
    return "null";
  }

  _isModeLoaded(mode) {
    if (!mode || mode === "null") return true;
    if (!window.CodeMirror) return false;
    try {
      let modeName = mode;
      const mimes = CodeMirror.mimeModes || {};
      if (mimes[modeName]) {
        const r = mimes[modeName];
        modeName = typeof r === "string" ? r : (r && r.name) || modeName;
      }
      return !!(CodeMirror.modes && CodeMirror.modes[modeName]);
    } catch (e) {
      return false;
    }
  }

  _loadModeScript(scriptPath) {
    if (!scriptPath) return Promise.reject(new Error("no script path"));
    if (this._loadedModeScripts.has(scriptPath)) return Promise.resolve();
    if (this._loadingModeScripts[scriptPath]) return this._loadingModeScripts[scriptPath];

    const url = CM_CDN + scriptPath + ".min.js";
    console.info("[Editor] Loading mode script:", scriptPath);
    const p = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = url;
      s.async = true;
      s.onload = () => {
        this._loadedModeScripts.add(scriptPath);
        delete this._loadingModeScripts[scriptPath];
        console.info("[Editor] ✓ Mode loaded:", scriptPath);
        resolve();
      };
      s.onerror = () => {
        delete this._loadingModeScripts[scriptPath];
        console.warn("[Editor] ✗ Mode load failed:", scriptPath, url);
        reject(new Error("Failed to load CodeMirror mode: " + scriptPath));
      };
      document.head.appendChild(s);
    });
    this._loadingModeScripts[scriptPath] = p;
    return p;
  }

  // ⭐ C7+C8: preserve dirty + re-render diagnostics
  _recreateDocWithMode(tab, mode) {
    const wasActive = this.activeIdx >= 0 && this.tabs[this.activeIdx] === tab;
    const isCurrent = wasActive && this.cm.getDoc() === tab.doc;
    const val = isCurrent ? this.cm.getValue() : (tab.doc ? tab.doc.getValue() : tab.content);
    const cursor = isCurrent ? this.cm.getCursor() : null;
    const scrollInfo = isCurrent ? this.cm.getScrollInfo() : null;

    // ⭐ C7: GIỮ dirty flag — KHÔNG reset tab.content khi đang dirty
    const wasDirty = !!tab.dirty;

    const newDoc = CodeMirror.Doc(val, mode);
    tab.doc = newDoc;
    // Chỉ update content khi chưa dirty (content là bản "saved trên disk")
    if (!wasDirty) {
      tab.content = val;
    }
    tab.dirty = wasDirty;

    if (isCurrent) {
      this.cm.swapDoc(newDoc);
      if (cursor) {
        try { this.cm.setCursor(cursor); } catch (e) {}
      }
      if (scrollInfo) {
        try { this.cm.scrollTo(scrollInfo.left, scrollInfo.top); } catch (e) {}
      }
      setTimeout(() => { try { this.cm.refresh(); } catch (e) {} }, 20);

      // ⭐ C8: re-render diagnostics markers sau khi doc bị swap
      setTimeout(() => {
        if (window.DiagnosticsUI && this.activeIdx >= 0) {
          const t = this.tabs[this.activeIdx];
          if (t === tab) {
            const diags = window.DiagnosticsUI.getDiagnostics(t.project, t.path);
            window.DiagnosticsUI.setFileDiagnostics(t.project, t.path, diags);
          }
        }
      }, 60);
    }

    // Cập nhật tab UI (dirty marker)
    this.renderTabs();
  }

  _getFoldRangeFinder() {
    const mode = (this.cm && this.cm.getMode() && this.cm.getMode().name) || "";
    const fold = (window.CodeMirror && window.CodeMirror.fold) || {};
    if (mode.indexOf("python") >= 0 && fold.indent) return fold.indent;
    if (mode.indexOf("javascript") >= 0 && fold.brace) return fold.brace;
    if (mode.indexOf("css") >= 0 && fold.brace) return fold.brace;
    if (mode.indexOf("htmlmixed") >= 0 && fold.brace) return fold.brace;
    if (mode.indexOf("xml") >= 0 && fold.brace) return fold.brace;
    if (mode.indexOf("yaml") >= 0 && fold.indent) return fold.indent;
    if (mode.indexOf("shell") >= 0 && fold.brace) return fold.brace;
    if (fold.brace) return fold.brace;
    if (fold.indent) return fold.indent;
    return null;
  }

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
        } catch (e) {}
      }
    });
    setTimeout(() => { try { cm.refresh(); } catch (e) {} }, 30);
  }

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
      } catch (e) {}
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

  undo() {
    if (!this.cm) return;
    try { this.cm.undo(); } catch (e) {}
    this._updateUndoRedoButtons();
  }

  redo() {
    if (!this.cm) return;
    try { this.cm.redo(); } catch (e) {}
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
    } catch (e) {}
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
        try { cm.execCommand("delCharBefore"); } catch (err) {}
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
        } catch (err) {}
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
      } catch (e) {}
    }
    try {
      this.cm.setOption("theme", theme);
    } catch (e) {}
  }

  open(project, path, content) {
    const existing = this.tabs.findIndex(t => t.project === project && t.path === path);
    if (existing >= 0) {
      this.activate(existing);
      return;
    }

    const mode = this._mode(path);
    const scriptPath = MODE_SCRIPTS[mode];
    const modeLoaded = this._isModeLoaded(mode);
    const effMode = modeLoaded ? mode : "null";

    const tab = {
      project, path,
      name: path.split("/").pop(),
      content: content || "",
      doc: CodeMirror.Doc(content || "", effMode),
      dirty: false,
      _pendingMode: modeLoaded ? null : mode,
    };

    this.tabs.push(tab);
    this.activeIdx = this.tabs.length - 1;
    this._load();
    this.renderTabs();

    if (!modeLoaded && scriptPath) {
      this._loadModeScript(scriptPath).then(() => {
        if (!this.tabs.includes(tab)) return;
        tab._pendingMode = null;
        if (!this._isModeLoaded(mode)) {
          console.warn("[Editor] Mode script loaded but mode not registered:", mode);
          return;
        }
        this._recreateDocWithMode(tab, mode);
      }).catch(e => {
        console.warn("[Editor] Mode load failed, staying plaintext:", mode, e.message);
        tab._pendingMode = null;
      });
    }
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
      const mode = this._mode(tab.path);
      const modeLoaded = this._isModeLoaded(mode);
      tab.doc = CodeMirror.Doc(tab.content || "", modeLoaded ? mode : "null");
      if (!modeLoaded) {
        const sp = MODE_SCRIPTS[mode];
        if (sp) {
          this._loadModeScript(sp).then(() => {
            if (this.tabs.includes(tab) && this._isModeLoaded(mode)) {
              this._recreateDocWithMode(tab, mode);
            }
          }).catch(e => console.warn("[Editor] Mode load failed:", mode, e.message));
        }
      }
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

  /** Đóng tất cả tab của 1 file cụ thể (dùng khi file/project bị xoá). */
  closeByPath(project, path) {
    const idx = this.tabs.findIndex(t => t.project === project && t.path === path);
    if (idx < 0) return;
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

  /** Đóng tất cả tab của 1 project (dùng khi project bị xoá). */
  closeByProject(project) {
    const before = this.tabs.length;
    this.tabs = this.tabs.filter(t => t.project !== project);
    if (this.tabs.length === before) return;
    if (this.tabs.length === 0) {
      this.activeIdx = -1;
    } else if (this.activeIdx >= this.tabs.length) {
      this.activeIdx = this.tabs.length - 1;
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