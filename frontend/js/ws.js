/* WSClient v2.0.1
 * - H4: tự động gửi ping mỗi 90s để tránh server timeout 5 phút.
 * - Queue khi chưa OPEN — không silent drop.
 * - on() trả unsubscribe để overlay cleanup.
 * - off/once/removeAll.
 */
class WSClient {
  constructor() {
    this.socket = null;
    this.handlers = new Map();
    this.reconnectDelay = 1000;
    this.maxDelay = 10000;
    this.allowReconnect = true;
    this.url = (location.protocol === "https:" ? "wss://" : "ws://") + location.host;
    this.queue = [];
    this.maxQueue = 200;
    this._wasOpen = false;

    // ⭐ H4: heartbeat
    this._heartbeatInterval = 90 * 1000;   // 90s
    this._heartbeatTimer = null;
    this._lastPongAt = 0;
  }

  connect() {
    if (!this.allowReconnect) return;
    try {
      this.socket = new WebSocket(this.url);
    } catch (e) { console.error("[WS] construct failed:", e); return; }

    this.socket.onopen = () => {
      this.reconnectDelay = 1000;
      this._wasOpen = true;
      this._lastPongAt = Date.now();
      this._startHeartbeat();
      this._flushQueue();
      this._emit("open");
    };
    this.socket.onclose = () => {
      this._wasOpen = false;
      this._stopHeartbeat();
      this._emit("close");
      if (!this.allowReconnect) return;
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
    };
    this.socket.onerror = (e) => this._emit("error", e);
    this.socket.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg && msg.type === "pong") {
          this._lastPongAt = Date.now();
        }
        this._emit("message", msg);
        if (msg.type) this._emit(msg.type, msg);
      } catch (e) { /* ignore malformed */ }
    };
  }

  disconnect() {
    this.allowReconnect = false;
    this._stopHeartbeat();
    try { if (this.socket) this.socket.close(); } catch (e) {}
  }

  // ⭐ H4: heartbeat — giữ kết nối sống qua proxy/timeout
  _startHeartbeat() {
    this._stopHeartbeat();
    this._heartbeatTimer = setInterval(() => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
      // Nếu quá 3 phút không nhận pong → coi như mất kết nối, force close để reconnect
      if (this._lastPongAt && Date.now() - this._lastPongAt > 3 * 60 * 1000) {
        console.warn("[WS] no pong for 3min — force reconnect");
        try { this.socket.close(); } catch (e) {}
        return;
      }
      this.send({ type: "ping", time: Date.now() });
    }, this._heartbeatInterval);
  }

  _stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
  }

  send(obj) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(JSON.stringify(obj));
        return true;
      } catch (e) {
        console.error("[WS] send failed:", e);
      }
    }
    if (this.queue.length < this.maxQueue) {
      this.queue.push(obj);
      return false;
    }
    console.warn("[WS] queue full, dropping:", obj && obj.type);
    return false;
  }

  _flushQueue() {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
    const q = this.queue;
    this.queue = [];
    for (const msg of q) {
      try { this.socket.send(JSON.stringify(msg)); }
      catch (e) { console.error("[WS] flush failed:", e); }
    }
  }

  on(evt, cb) {
    if (!this.handlers.has(evt)) this.handlers.set(evt, []);
    const list = this.handlers.get(evt);
    if (!list.includes(cb)) list.push(cb);
    return () => this.off(evt, cb);
  }

  off(evt, cb) {
    const list = this.handlers.get(evt);
    if (!list) return;
    const i = list.indexOf(cb);
    if (i >= 0) list.splice(i, 1);
  }

  once(evt, cb) {
    const wrapper = (data) => {
      this.off(evt, wrapper);
      try { cb(data); } catch (e) { console.error("[WS]", evt, e); }
    };
    this.on(evt, wrapper);
    return () => this.off(evt, wrapper);
  }

  removeAll(evt) {
    if (evt) this.handlers.delete(evt);
    else this.handlers.clear();
  }

  _emit(evt, data) {
    const list = this.handlers.get(evt) || [];
    for (const cb of [...list]) {
      try { cb(data); } catch (e) { console.error("[WS]", evt, e); }
    }
  }
}