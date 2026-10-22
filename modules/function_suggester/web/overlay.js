(function () {
  'use strict';

  const API = '/api/function_suggester';

  // ─── Panel ──────────────────────────────────────────
  function ensurePanel() {
    let p = document.getElementById('fs-panel');
    if (p) return p;

    p = document.createElement('div');
    p.id = 'fs-panel';
    p.className = 'fs-panel';
    p.innerHTML = `
      <div class="fs-header">
        <span>💡 Function Suggestions</span>
        <span class="fs-close" title="Đóng">✕</span>
      </div>
      <div class="fs-body" id="fs-body">
        <div class="fs-hint">Ctrl+Shift+Space để load suggestions</div>
      </div>
    `;
    document.body.appendChild(p);
    p.querySelector('.fs-close').onclick = () => p.style.display = 'none';
    return p;
  }

  function getCtx() {
    return {
      project: window.currentProject
        || (window.app && window.app.currentProject)
        || (window.state && window.state.project)
        || localStorage.getItem('acdv.currentProject')
        || null,
      path: window.currentFile
        || (window.app && window.app.currentFile)
        || (window.state && window.state.path)
        || localStorage.getItem('acdv.currentFile')
        || null,
    };
  }

  async function loadSuggestions() {
    const panel = ensurePanel();
    const body  = panel.querySelector('#fs-body');
    panel.style.display = 'block';

    const ctx = getCtx();
    if (!ctx.project || !ctx.path) {
      body.innerHTML = `
        <div class="fs-warn">⚠ Không xác định được project/file đang mở.</div>
        <div class="fs-form">
          <input id="fs-p" placeholder="project name" />
          <input id="fs-f" placeholder="file path (e.g. main.py)" />
          <button id="fs-go">Load</button>
        </div>`;
      body.querySelector('#fs-go').onclick = () => {
        const p = body.querySelector('#fs-p').value.trim();
        const f = body.querySelector('#fs-f').value.trim();
        if (p && f) {
          window.currentProject = p;
          window.currentFile    = f;
          loadSuggestions();
        }
      };
      return;
    }

    body.innerHTML = '<div class="fs-hint">Loading…</div>';
    try {
      const r = await fetch(API + '/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project: ctx.project, path: ctx.path }),
      });
      const data = await r.json();
      if (!data.ok) {
        body.innerHTML = `<div class="fs-err">Error: ${esc(data.error || 'unknown')}</div>`;
        return;
      }
      if (!data.suggestions.length) {
        body.innerHTML = `<div class="fs-hint">Không có hàm ${esc(data.lang)} nào khác để gợi ý.</div>`;
        return;
      }
      body.innerHTML = `
        <div class="fs-meta">Ngôn ngữ: <b>${esc(data.lang)}</b> · ${data.count} gợi ý</div>
        ${data.suggestions.map(s => `
          <div class="fs-item" data-call="${esc(s.sample_call)}">
            <div class="fs-name">${esc(s.name)}</div>
            <div class="fs-sig">${esc(s.signature)}</div>
            <div class="fs-src">
              📁 <span class="fs-file">${esc(s.file)}</span>
              <span class="fs-dot">·</span>${esc(s.project)}
              <span class="fs-dot">·</span>L${s.line}
            </div>
            <div class="fs-call">▶ ${esc(s.sample_call)}</div>
          </div>`).join('')}
      `;
      body.querySelectorAll('.fs-item').forEach(el => {
        el.onclick = () => insertToEditor(el.getAttribute('data-call'));
      });
    } catch (e) {
      body.innerHTML = `<div class="fs-err">Fetch error: ${esc(e.message)}</div>`;
    }
  }

  function insertToEditor(text) {
    const cmEl = document.querySelector('.CodeMirror');
    if (cmEl && cmEl.CodeMirror) {
      cmEl.CodeMirror.replaceSelection(text);
      cmEl.CodeMirror.focus();
      return;
    }
    const ta = document.querySelector('textarea');
    if (ta) {
      const s = ta.selectionStart, e = ta.selectionEnd;
      ta.value = ta.value.slice(0, s) + text + ta.value.slice(e);
      ta.selectionStart = ta.selectionEnd = s + text.length;
      ta.focus();
      return;
    }
    navigator.clipboard?.writeText(text);
    alert('Copied: ' + text);
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }

  // ─── Hotkey ─────────────────────────────────────────
  document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.shiftKey && e.code === 'Space') {
      e.preventDefault();
      loadSuggestions();
    }
  });

  window.functionSuggester = { load: loadSuggestions };
  console.log('[function_suggester] ready — Ctrl+Shift+Space');
})();