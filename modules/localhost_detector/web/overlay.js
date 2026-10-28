/**
 * modules/localhost_detector/web/overlay.js
 * Overlay v2.0 — ACDV.register + cleanup registry.
 *
 * Nút nổi "🌐 localhost:PORT" — bấm để mở tab mới, KHÔNG đổi tab editor.
 */
(function (ACDV) {
  'use strict';

  var MODULE = 'localhost_detector';

  ACDV.register(MODULE, function (ctx) {
    // port (number) -> { port, url, framework, confidence, source }
    var servers = new Map();
    var root = null;
    var menuOpen = false;

    // ─── DOM ─────────────────────────────────────────
    function ensureRoot() {
      if (root && document.body.contains(root)) return root;
      root = document.createElement('div');
      root.id = 'acdv-localhost_detector-root';
      root.className = 'acdv-localhost_detector-root';
      ctx.append(document.body, root);
      return root;
    }

    function render() {
      var r = ensureRoot();
      r.innerHTML = '';

      if (servers.size === 0) {
        r.style.display = 'none';
        menuOpen = false;
        return;
      }
      r.style.display = 'flex';

      var list = Array.from(servers.values()).sort(function (a, b) {
        return a.port - b.port;
      });

      var mainBtn = document.createElement('button');
      mainBtn.type = 'button';
      mainBtn.className = 'acdv-localhost_detector-btn';
      mainBtn.title = 'Mở localhost server (tab mới, không đổi tab editor)';

      if (list.length === 1) {
        mainBtn.textContent = '🌐 localhost:' + list[0].port;
        mainBtn.addEventListener('click', function () {
          window.open(list[0].url, '_blank', 'noopener');
        });
      } else {
        mainBtn.textContent = '🌐 localhost (' + list.length + ')';
        mainBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          menuOpen = !menuOpen;
          render();
        });
      }
      r.appendChild(mainBtn);

      if (menuOpen && list.length > 1) {
        r.appendChild(buildMenu(list));
      }

      var closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = 'acdv-localhost_detector-close';
      closeBtn.textContent = '✕';
      closeBtn.title = 'Ẩn (sẽ hiện lại khi run sau)';
      closeBtn.addEventListener('click', function () {
        servers.clear();
        render();
      });
      r.appendChild(closeBtn);
    }

    function buildMenu(list) {
      var menu = document.createElement('div');
      menu.className = 'acdv-localhost_detector-menu';
      list.forEach(function (srv) {
        var item = document.createElement('button');
        item.type = 'button';
        item.className = 'acdv-localhost_detector-item';

        var urlEl = document.createElement('span');
        urlEl.className = 'acdv-localhost_detector-item-url';
        urlEl.textContent = srv.url;

        var fwEl = document.createElement('span');
        fwEl.className = 'acdv-localhost_detector-item-fw';
        fwEl.textContent = srv.framework + ' · ' + srv.source;

        item.appendChild(urlEl);
        item.appendChild(fwEl);

        item.addEventListener('click', function () {
          window.open(srv.url, '_blank', 'noopener');
          menuOpen = false;
          render();
        });
        menu.appendChild(item);
      });
      return menu;
    }

    // ─── Server registry ─────────────────────────────
    function upsertServer(srv, source) {
      if (!srv || !srv.port) return false;
      var port = Number(srv.port);
      if (!(port >= 1 && port <= 65535)) return false;

      var prev = servers.get(port);
      // Ưu tiên high confidence; nếu đã high thì không ghi đè bằng medium/low
      if (prev && prev.confidence === 'high' && srv.confidence !== 'high') {
        return false;
      }
      servers.set(port, {
        port: port,
        url: srv.url || ('http://127.0.0.1:' + port),
        framework: srv.framework || 'server',
        confidence: srv.confidence || 'low',
        source: source || 'static',
      });
      return true;
    }

    // ─── Runtime parser ──────────────────────────────
    var URL_RE =
      /https?:\/\/(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\]|\[::\]):(\d{2,5})/gi;
    var PORT_RE = /\bport\s+(\d{2,5})\b/gi;
    var LISTEN_RE = /\b(?:listening|running|serving)\b[^\d]{0,20}(\d{2,5})\b/gi;

    function guessFw(line) {
      var l = line.toLowerCase();
      if (l.indexOf('flask') !== -1) return 'flask';
      if (l.indexOf('uvicorn') !== -1) return 'uvicorn';
      if (l.indexOf('fastapi') !== -1) return 'fastapi';
      if (l.indexOf('django') !== -1) return 'django';
      if (l.indexOf('aiohttp') !== -1) return 'aiohttp';
      if (l.indexOf('bottle') !== -1) return 'bottle';
      if (l.indexOf('gradio') !== -1) return 'gradio';
      if (l.indexOf('streamlit') !== -1) return 'streamlit';
      if (l.indexOf('serving http') !== -1 || l.indexOf('http.server') !== -1)
        return 'http.server';
      return 'server';
    }

    function parseOutputLines(lines) {
      if (!lines || !lines.length) return false;
      var added = false;
      for (var i = 0; i < lines.length; i++) {
        var line = String(lines[i] || '');
        var m;

        URL_RE.lastIndex = 0;
        while ((m = URL_RE.exec(line)) !== null) {
          var p = parseInt(m[1], 10);
          if (p >= 1 && p <= 65535) {
            if (
              upsertServer(
                { port: p, framework: guessFw(line), confidence: 'high' },
                'runtime'
              )
            )
              added = true;
          }
        }

        PORT_RE.lastIndex = 0;
        while ((m = PORT_RE.exec(line)) !== null) {
          var pp = parseInt(m[1], 10);
          if (pp >= 1 && pp <= 65535) {
            if (
              upsertServer(
                { port: pp, framework: guessFw(line), confidence: 'medium' },
                'runtime'
              )
            )
              added = true;
          }
        }

        LISTEN_RE.lastIndex = 0;
        while ((m = LISTEN_RE.exec(line)) !== null) {
          var ppp = parseInt(m[1], 10);
          if (ppp >= 1 && ppp <= 65535) {
            if (
              upsertServer(
                { port: ppp, framework: guessFw(line), confidence: 'medium' },
                'runtime'
              )
            )
              added = true;
          }
        }
      }
      return added;
    }

    // ─── Static scan ─────────────────────────────────
    async function staticScan(project, path) {
      if (!project || !path || !path.endsWith('.py')) return;
      try {
        var res = await ctx.fetch('/api/localhost_detector/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project: project, path: path }),
        });
        if (!res.ok) return;
        var data = await res.json();
        if (data && data.ok && Array.isArray(data.servers) && data.servers.length) {
          var changed = false;
          data.servers.forEach(function (s) {
            if (upsertServer(s, 'static')) changed = true;
          });
          if (changed) render();
        }
      } catch (e) {
        ctx.log(
          '[localhost_detector] static scan failed: ' +
            (e && e.message ? e.message : e)
        );
      }
    }

    // ─── WS hooks (tất cả auto-cleanup qua ctx.wsOn) ──
    ctx.wsOn('run_started', function (msg) {
      servers.clear();
      menuOpen = false;
      render();
      if (msg && msg.project && msg.path) {
        staticScan(msg.project, msg.path);
      }
    });

    ctx.wsOn('run_output', function (msg) {
      if (!msg || !Array.isArray(msg.lines)) return;
      if (parseOutputLines(msg.lines)) render();
    });

    ctx.wsOn('settings_changed', function (msg) {
      // Tôn trọng setting enabled
      var s = (msg && msg.settings) || {};
      var modCfg = (s.modules && s.modules[MODULE]) || {};
      if (modCfg.enabled === false) {
        servers.clear();
        render();
      }
    });

    ctx.log('localhost_detector overlay ready');
  });
})(window.ACDV);