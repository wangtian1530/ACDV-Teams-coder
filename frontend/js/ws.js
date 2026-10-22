class WSClient {
  constructor() {
    this.socket = null;
    this.handlers = new Map();
    this.reconnectDelay = 1000;
    this.maxDelay = 10000;
    this.allowReconnect = true;   // ⭐ v1.3.5: set false để dừng auto-reconnect (khi shutdown)
    this.url = (location.protocol === "https:" ? "wss://" : "ws://") + location.host;
  }

  connect() {
    if (!this.allowReconnect) return;
    try {
      this.socket = new WebSocket(this.url);
    } catch (e) { console.error(e); return; }

    this.socket.onopen = () => {
      this.reconnectDelay = 1000;
      this._emit("open");
    };
    this.socket.onclose = () => {
      this._emit("close");
      if (!this.allowReconnect) return;
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
    };
    this.socket.onerror = (e) => this._emit("error", e);
    this.socket.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        this._emit("message", msg);
        if (msg.type) this._emit(msg.type, msg);
      } catch (e) { /* ignore */ }
    };
  }

  disconnect() {
    this.allowReconnect = false;
    try { if (this.socket) this.socket.close(); } catch (e) {}
  }

  send(obj) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(obj));
    }
  }

  on(evt, cb) {
    if (!this.handlers.has(evt)) this.handlers.set(evt, []);
    this.handlers.get(evt).push(cb);
  }

  _emit(evt, data) {
    const list = this.handlers.get(evt) || [];
    list.forEach(cb => { try { cb(data); } catch (e) { console.error(e); } });
  }
}