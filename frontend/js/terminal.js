/* ACDV Terminal UI — xterm.js wrapper over WS terminal protocol. */
const TerminalUI = {
  term: null,
  fitAddon: null,
  termId: null,
  ready: false,
  pendingInput: '',

  init() {
    if (this.term) return;
    if (typeof Terminal === 'undefined') {
      console.warn('[Terminal] xterm.js not loaded');
      return;
    }

    this.term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: '"SF Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace',
      theme: {
        background: '#1e1e1e', foreground: '#cccccc',
        cursor: '#4af', selectionBackground: '#3c3c3c',
        black: '#000000', red: '#cd3131', green: '#0dbc79',
        yellow: '#e5e510', blue: '#2472c8', magenta: '#bc3fbc',
        cyan: '#11a8cd', white: '#e5e5e5',
        brightBlack: '#666666', brightRed: '#f14c4c',
        brightGreen: '#23d18b', brightYellow: '#f5f543',
        brightBlue: '#3b8eea', brightMagenta: '#d670d6',
        brightCyan: '#29b8db', brightWhite: '#e5e5e5',
      },
      scrollback: 5000,
      convertEol: true,
      allowProposedApi: true,
    });

    if (typeof FitAddon !== 'undefined') {
      this.fitAddon = new FitAddon.FitAddon();
      this.term.loadAddon(this.fitAddon);
    }
    if (typeof WebLinksAddon !== 'undefined') {
      try {
        this.term.loadAddon(new WebLinksAddon.WebLinksAddon());
      } catch (e) { /* ignore */ }
    }

    const el = document.getElementById('terminalContainer');
    if (!el) return;
    this.term.open(el);

    this.term.onData((data) => {
      if (!this.termId) return;
      if (!this.ready) { this.pendingInput += data; return; }
      if (window.App && App.ws) {
        App.ws.send({ type: 'terminal_input', id: this.termId, data });
      }
    });

    this.term.onResize(({ cols, rows }) => {
      if (this.termId && window.App && App.ws) {
        App.ws.send({ type: 'terminal_resize', id: this.termId, cols, rows });
      }
    });

    this._updateStatus('idle');
    setTimeout(() => this.fit(), 60);
    window.addEventListener('resize', () => this.fit());
  },

  fit() {
    if (!this.fitAddon) return;
    try { this.fitAddon.fit(); } catch (e) { /* ignore */ }
  },

  openSession() {
    if (!this.term) this.init();
    if (!this.term || this.termId) return;
    if (!window.App || !App.ws) return;

    this.termId = 't_' + Math.random().toString(36).slice(2, 10) + '_' + Date.now();
    this.ready = false;
    this.pendingInput = '';

    this.fit();
    let cols = 80, rows = 24;
    if (this.fitAddon) {
      try {
        const d = this.fitAddon.proposeDimensions();
        if (d) { cols = d.cols; rows = d.rows; }
      } catch (e) { /* ignore */ }
    }

    let cwd = null;
    if (window.Explorer && Explorer.currentProject) {
      cwd = 'projects/' + Explorer.currentProject;
    }

    App.ws.send({ type: 'terminal_open', id: this.termId, cols, rows, cwd });
    this._updateStatus('connecting');
  },

  closeSession() {
    if (!this.termId) return;
    if (window.App && App.ws) {
      App.ws.send({ type: 'terminal_close', id: this.termId });
    }
    this.termId = null;
    this.ready = false;
    this.pendingInput = '';
    this._updateStatus('idle');
  },

  restart() {
    this.closeSession();
    if (this.term) this.term.clear();
    setTimeout(() => this.openSession(), 100);
  },

  handleMessage(msg) {
    if (!this.term) return;
    if (msg.type === 'terminal_opened') {
      if (msg.id !== this.termId) return;
      this.ready = true;
      this._updateStatus('online');
      if (this.pendingInput) {
        if (window.App && App.ws) {
          App.ws.send({ type: 'terminal_input', id: this.termId, data: this.pendingInput });
        }
        this.pendingInput = '';
      }
      this.term.focus();
    } else if (msg.type === 'terminal_output') {
      if (msg.id !== this.termId) return;
      this.term.write(msg.data || '');
    } else if (msg.type === 'terminal_exit') {
      if (msg.id !== this.termId) return;
      this.term.writeln('\r\n\x1b[33m[process exited with code ' + msg.code + ']\x1b[0m');
      this.termId = null;
      this.ready = false;
      this._updateStatus('exited');
    } else if (msg.type === 'terminal_error') {
      if (msg.id !== this.termId) return;
      this.term.writeln('\r\n\x1b[31m[error: ' + (msg.error || 'unknown') + ']\x1b[0m');
      this.termId = null;
      this.ready = false;
      this._updateStatus('offline');
    }
  },

  _updateStatus(state) {
    const el = document.getElementById('terminalStatus');
    if (!el) return;
    if (state === 'online') {
      el.textContent = '● Connected';
      el.className = 'terminal-status online';
    } else if (state === 'connecting') {
      el.textContent = '◌ Connecting…';
      el.className = 'terminal-status connecting';
    } else if (state === 'exited') {
      el.textContent = '○ Session ended';
      el.className = 'terminal-status offline';
    } else {
      el.textContent = '● Not connected';
      el.className = 'terminal-status offline';
    }
  },

  show() {
    if (!this.term) this.init();
    setTimeout(() => {
      this.fit();
      if (!this.termId) this.openSession();
      if (this.term) this.term.focus();
    }, 60);
  },

  onReconnect() {
    if (this.termId) {
      this.termId = null;
      this.ready = false;
      if (this.term) {
        this.term.writeln('\r\n\x1b[33m[WebSocket reconnected — session may have ended]\x1b[0m');
      }
      this._updateStatus('idle');
    }
  },

  clear() {
    if (this.term) this.term.clear();
  },
};

document.addEventListener('DOMContentLoaded', () => {
  const rb = document.getElementById('terminalRestartBtn');
  if (rb) rb.onclick = () => TerminalUI.restart();
  const kb = document.getElementById('terminalKillBtn');
  if (kb) kb.onclick = () => {
    TerminalUI.closeSession();
    if (TerminalUI.term) TerminalUI.term.writeln('\r\n\x1b[33m[killed by user]\x1b[0m');
  };
});

window.TerminalUI = TerminalUI;