/* ACDV Diagnostics UI — Problems panel + CodeMirror inline markers
 * v2.0.1: C9 — key dùng separator '\0' thay vì '/' để an toàn với nested path.
 */
(function () {
  'use strict';

  const SEP = '\u0000';  // ⭐ C9: không bao giờ xuất hiện trong project/path

  const state = {
    byFile: {},
    markers: {},
  };

  function key(project, path) { return project + SEP + path; }

  function parseKey(k) {
    const i = k.indexOf(SEP);
    if (i < 0) return [k, ''];
    return [k.substring(0, i), k.substring(i + 1)];
  }

  function cmForPath(project, path) {
    if (window.AppEditor && typeof window.AppEditor.getCm === 'function') {
      return window.AppEditor.getCm(project, path);
    }
    return null;
  }

  function sevClass(sev) { return 'acdv-diag-' + (sev || 'info'); }
  function sevIcon(s) {
    if (s === 'error') return '✖';
    if (s === 'warning') return '⚠';
    if (s === 'hint') return '💡';
    return 'ℹ';
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function setFileDiagnostics(project, path, diags) {
    state.byFile[key(project, path)] = Array.isArray(diags) ? diags : [];
    renderMarkers(project, path);
    renderPanel();
    updateBadge();
  }

  function renderMarkers(project, path) {
    const k = key(project, path);
    const cm = cmForPath(project, path);
    if (!cm) return;
    (state.markers[k] || []).forEach(m => { try { m.clear(); } catch (e) {} });
    state.markers[k] = [];
    const diags = state.byFile[k] || [];
    for (const d of diags) {
      try {
        const line = Math.max(0, (d.line || 1) - 1);
        const ch = Math.max(0, (d.column || 1) - 1);
        const endLine = Math.max(line, (d.end_line || d.line || 1) - 1);
        const endCh = Math.max(0, (d.end_column || d.column || 1) - 1);
        let from = { line, ch };
        let to = { line: endLine, ch: endCh };
        if (from.line === to.line && to.ch <= from.ch) {
          const ln = cm.getLine(line) || '';
          to = { line, ch: ln.length };
        }
        const m = cm.markText(from, to, {
          className: sevClass(d.severity),
          title: d.message,
          clearWhenEmpty: false,
        });
        state.markers[k].push(m);
      } catch (e) { /* ignore */ }
    }
  }

  function clearMarkersFor(project, path) {
    const k = key(project, path);
    (state.markers[k] || []).forEach(m => { try { m.clear(); } catch (e) {} });
    state.markers[k] = [];
  }

  function updateBadge() {
    const total = Object.values(state.byFile)
      .reduce((a, b) => a + b.length, 0);
    const errors = Object.values(state.byFile)
      .reduce((a, b) => a + b.filter(d => d.severity === 'error').length, 0);
    const btn = document.getElementById('problemsBtn');
    if (!btn) return;
    let badge = btn.querySelector('.badge');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'badge';
      btn.appendChild(badge);
    }
    badge.textContent = total;
    badge.style.display = total > 0 ? 'inline-block' : 'none';
    badge.className = 'badge ' + (errors > 0 ? 'badge-error' : 'badge-warn');
  }

  function renderPanel() {
    const container = document.getElementById('problemsList');
    if (!container) return;
    container.innerHTML = '';
    const keys = Object.keys(state.byFile).sort();
    let hasAny = false;
    for (const k of keys) {
      const diags = state.byFile[k];
      if (!diags.length) continue;
      hasAny = true;
      const [project, path] = parseKey(k);
      const group = document.createElement('div');
      group.className = 'problem-group';
      const header = document.createElement('div');
      header.className = 'problem-group-header';
      header.textContent = `${project} / ${path} (${diags.length})`;
      group.appendChild(header);
      for (const d of diags) {
        const row = document.createElement('div');
        row.className = 'problem-row ' + sevClass(d.severity);
        row.innerHTML = `
          <span class="problem-sev">${sevIcon(d.severity)}</span>
          <span class="problem-msg">${escapeHtml(d.message)}</span>
          <span class="problem-loc">${d.line}:${d.column}</span>
          <span class="problem-src">${escapeHtml(d.source || '')}</span>
        `;
        row.addEventListener('click', () => jumpTo(project, path, d));
        group.appendChild(row);
      }
      container.appendChild(group);
    }
    if (!hasAny) {
      container.innerHTML = '<div class="problems-empty">✓ No problems detected</div>';
    }
  }

  function jumpTo(project, path, d) {
    if (window.AppEditor && typeof window.AppEditor.openFileAtLine === 'function') {
      window.AppEditor.openFileAtLine(project, path, d.line, d.column);
    }
  }

  function handleWsMessage(msg) {
    if (!msg || !msg.type) return;
    if (msg.type === 'diagnostics_update') {
      setFileDiagnostics(msg.project, msg.path, msg.diagnostics);
    } else if (msg.type === 'diagnostics_cleared') {
      // ⭐ C9: dùng parseKey — không split('/')
      Object.keys(state.markers).forEach(k => {
        const [proj, path] = parseKey(k);
        clearMarkersFor(proj, path);
      });
      state.byFile = {};
      state.markers = {};
      renderPanel();
      updateBadge();
    }
  }

  function refreshAll() {
    fetch('/api/diagnostics/all')
      .then(r => r.json())
      .then(res => {
        if (!res || !res.ok) return;
        state.byFile = {};
        for (const d of res.diagnostics) {
          const k = key(d.project, d.path);
          (state.byFile[k] = state.byFile[k] || []).push(d);
        }
        renderPanel();
        updateBadge();
      })
      .catch(() => {});
  }

  function getDiagnostics(project, path) {
    return state.byFile[key(project, path)] || [];
  }

  /** Xoá diags của module cụ thể (khi module reload). */
  function clearBySource(sourceName) {
    for (const k of Object.keys(state.byFile)) {
      const filtered = state.byFile[k].filter(d => d.source !== sourceName);
      if (filtered.length) state.byFile[k] = filtered;
      else delete state.byFile[k];
    }
    renderPanel();
    updateBadge();
  }

  window.DiagnosticsUI = {
    setFileDiagnostics,
    clearMarkersFor,
    clearBySource,
    handleWsMessage,
    renderPanel,
    refreshAll,
    getDiagnostics,
  };
})();