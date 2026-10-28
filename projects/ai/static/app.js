const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const turnInfo = document.getElementById('turn-info');
const actorInfo = document.getElementById('actor-info');
const phaseInfo = document.getElementById('phase-info');
const bulletInfo = document.getElementById('bullet-info');
const statusEl = document.getElementById('status');
const botList = document.getElementById('bot-list');
const leaderboard = document.getElementById('leaderboard');
let currentState = null;

function resizeCanvas() {
  const r = canvas.getBoundingClientRect();
  if (r.width < 1 || r.height < 1) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(r.width * dpr);
  canvas.height = Math.floor(r.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  render();
}
new ResizeObserver(resizeCanvas).observe(canvas.parentElement);

function render() {
  if (!currentState) return;
  const s = currentState;
  const r = canvas.getBoundingClientRect();
  const cw = r.width, ch = r.height;
  const { w: W, h: H } = s.map;
  ctx.clearRect(0, 0, cw, ch);

  const cell = Math.min(cw / W, ch / H);
  const ox = (cw - cell * W) / 2;
  const oy = (ch - cell * H) / 2;

  // Grid
  ctx.strokeStyle = 'rgba(60,60,120,0.1)';
  ctx.lineWidth = 0.5;
  for (let x = 0; x <= W; x++) {
    ctx.beginPath();
    ctx.moveTo(ox + x * cell, oy);
    ctx.lineTo(ox + x * cell, oy + H * cell);
    ctx.stroke();
  }
  for (let y = 0; y <= H; y++) {
    ctx.beginPath();
    ctx.moveTo(ox, oy + y * cell);
    ctx.lineTo(ox + W * cell, oy + y * cell);
    ctx.stroke();
  }

  // Obstacles
  const obs = s.map.obstacles;
  ctx.fillStyle = '#2a1a3a';
  ctx.shadowBlur = 0;
  for (let i = 0; i < obs.length; i += 2) {
    ctx.fillRect(ox + obs[i] * cell, oy + obs[i+1] * cell, cell, cell);
  }

  // ========= LASER BEAMS (polyline) =========
  for (const bl of s.bullets) {
    const owner = s.bots[bl.owner];
    const color = owner ? owner.color : '#ff9900';
    if (!bl.corners || bl.corners.length === 0) continue;

    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(2.5, cell * 0.22);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.shadowBlur = 18;
    ctx.shadowColor = color;
    ctx.globalAlpha = 0.95;

    ctx.beginPath();
    const [x0, y0] = bl.corners[0];
    ctx.moveTo(ox + (x0 + 0.5) * cell, oy + (y0 + 0.5) * cell);
    for (let i = 1; i < bl.corners.length; i++) {
      const [xi, yi] = bl.corners[i];
      ctx.lineTo(ox + (xi + 0.5) * cell, oy + (yi + 0.5) * cell);
    }
    ctx.lineTo(ox + (bl.x + 0.5) * cell, oy + (bl.y + 0.5) * cell);
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;

    // Head glow
    const bx = ox + (bl.x + 0.5) * cell;
    const by = oy + (bl.y + 0.5) * cell;
    ctx.fillStyle = '#ffffff';
    ctx.shadowBlur = 20;
    ctx.shadowColor = color;
    ctx.beginPath();
    ctx.arc(bx, by, Math.max(2.5, cell * 0.28), 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    if (bl.pending) {
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.arc(bx, by, cell * 0.55, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // ========= BOTS =========
  for (const b of s.bots) {
    const cx = ox + (b.x + 0.5) * cell;
    const cy = oy + (b.y + 0.5) * cell;

    if (!b.alive) {
      ctx.globalAlpha = 0.2;
      ctx.fillStyle = b.color;
      ctx.beginPath();
      ctx.arc(cx, cy, cell * 0.35, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
      continue;
    }

    const rad = cell * 0.42;
    const isActor = s.actor_idx === b.id && !s.over;

    if (isActor) {
      ctx.strokeStyle = '#66ccff';
      ctx.lineWidth = 3;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.arc(cx, cy, rad * 1.7, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.shadowBlur = 14;
    ctx.shadowColor = b.color;
    ctx.fillStyle = b.color;
    ctx.beginPath();
    ctx.arc(cx, cy, rad, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    ctx.strokeStyle = b.hp > 2 ? '#4caf50' : (b.hp > 1 ? '#ff9800' : '#f44336');
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(cx, cy, rad * 1.2, -Math.PI / 2,
            -Math.PI / 2 + Math.PI * 2 * (b.hp / b.max_hp));
    ctx.stroke();

    ctx.fillStyle = '#000';
    ctx.font = `bold ${Math.max(10, cell * 0.5)}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(b.id, cx, cy);
  }

  const simS = (s.sim_time_ms / 1000).toFixed(1);
  const maxS = (s.max_sim_time_ms / 1000).toFixed(0);
  turnInfo.textContent = `⏱ ${simS}s / ${maxS}s`;
  const actor = s.bots[s.actor_idx];
  if (!s.over && actor) {
    actorInfo.textContent = `🎯 Bot #${s.actor_idx}`;
  } else {
    actorInfo.textContent = '';
  }
  phaseInfo.textContent = s.phase === 'RESOLVING' ? '⚡ Đang giải đạn...' : '';
  bulletInfo.textContent = `💥 Laser: ${s.bullets.length}`;
  statusEl.textContent = s.over ? `🏁 ${s.result}` : '';
}

function renderLeaderboard() {
  if (!currentState || !currentState.ranking) return;
  const medal = ['🥇','🥈','🥉'];
  leaderboard.innerHTML = currentState.ranking.map(r => {
    const b = currentState.bots[r.id];
    const medalIcon = medal[r.rank - 1] || `#${r.rank}`;
    const topClass = r.rank <= 3 ? `top${r.rank}` : '';
    return `
      <div class="lb-row ${topClass}">
        <span class="rank">${medalIcon}</span>
        <span class="name" style="color:${b.color}">
          Bot #${r.id} ${r.alive ? '' : '☠'}
          <div class="meta">${r.kills}K · ${r.deaths}D · ${r.hits}H</div>
        </span>
        <span class="score">${r.score}</span>
      </div>`;
  }).join('');
}

function renderStats() {
  if (!currentState) return;
  botList.innerHTML = currentState.bots.map(b => {
    const st = b.stats;
    const hpPct = (b.hp / b.max_hp) * 100;
    const mem = (b.memory || []).slice(-2).reverse();
    const isActor = currentState.actor_idx === b.id && b.alive && !currentState.over;
    return `
    <div class="bot-card ${b.alive ? '' : 'dead'} ${isActor ? 'active' : ''}"
         style="border-left-color:${b.color}">
      <div class="name" style="color:${b.color}">
        <span>Bot #${b.id} ${b.alive ? '' : '☠'}</span>
        ${isActor ? '<span class="badge acting">ACTING</span>' : ''}
      </div>
      <div class="hp-bar"><div class="hp-fill"
        style="width:${hpPct}%;background:${b.hp>2?'#4caf50':(b.hp>1?'#ff9800':'#f44336')}"></div></div>
      <div class="row"><span>HP</span><span>${b.hp}/${b.max_hp}</span></div>
      <div class="row"><span>K / H / D</span><span>${st.kills} / ${st.hits} / ${st.deaths}</span></div>
      <div class="row"><span>Shots (curved)</span><span>${st.shots} (${st.curved_shots})</span></div>
      <div class="row"><span>Moves / Wasted</span><span>${st.moves} / ${st.wasted}</span></div>
      <div class="row"><span>Damage taken</span><span>${st.damage_taken}</span></div>
      <div class="row"><span>Rewards</span>
        <span class="${st.rewards >= 0 ? 'reward-pos' : 'reward-neg'}">${st.rewards.toFixed(1)}</span>
      </div>
      <div class="row"><span>Q / ε</span><span>${b.q_size} / ${b.epsilon.toFixed(3)}</span></div>
      ${mem.length ? `<div class="memory">${mem.map(m => `
        <div class="memory-item">
          <span>a=${m.action} s=[${m.state.join(',')}]</span>
          <span class="${m.reward >= 0 ? 'reward-pos' : 'reward-neg'}">r=${m.reward}</span>
        </div>`).join('')}</div>` : ''}
    </div>`;
  }).join('');
}

const es = new EventSource('/api/stream');
es.onmessage = e => {
  currentState = JSON.parse(e.data);
  render();
  renderLeaderboard();
  renderStats();
};

document.querySelectorAll('.speed').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.speed').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    fetch(`/api/speed?m=${btn.dataset.speed}`, { method: 'POST' });
  };
});
document.getElementById('rewind').onclick = () => fetch('/api/rewind', { method: 'POST' });
document.getElementById('reset').onclick = () => fetch('/api/reset', { method: 'POST' });
document.getElementById('pause').onclick = async e => {
  const d = await (await fetch('/api/pause', { method: 'POST' })).json();
  e.target.textContent = d.paused ? '▶ Play' : '⏸ Pause';
};

resizeCanvas();