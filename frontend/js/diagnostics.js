/* ACDV Diagnostics UI — Problems panel + CodeMirror inline markers */
(function () {
  'use strict';

  const state = {
    byFile: {},     // "project/path" -> [diag]
    markers: {},    // "project/path" -> [cm.TextMarker]
  };

  function key(project, path) { return project + '/' + path; }
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
      const [project, ...rest] = k.split('/');
      const path = rest.join('/');
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
      Object.keys(state.markers).forEach(k => clearMarkersFor(...k.split('/')));
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

  // ⭐ v1.3.0: editor.js needs this to re-render markers on tab switch
  function getDiagnostics(project, path) {
    return state.byFile[key(project, path)] || [];
  }

  window.DiagnosticsUI = {
    setFileDiagnostics,
    clearMarkersFor,
    handleWsMessage,
    renderPanel,
    refreshAll,
    getDiagnostics,
  };
})();