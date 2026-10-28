(() => {
  'use strict';

  /* ============ CFG ============ */
  const WORLD = { w: 4200, h: 4200 };
  const CFG = {
    baseSpeed:     2.2,
    boostSpeed:    4.4,
    baseRadius:    10,
    startSegments: 24,
    minSegments:   15,
    maxSegments:   500,
    segmentFactor: 0.7,
    foodCount:     420,
    botCount:      8,
    turnRate:      0.12,
    botTurnRate:   0.075,
    zoomMin:       0.50,
    zoomMax:       1.15,

    boostDuration:  4.0,
    boostCooldown:  5.0,
    boostDrainRate: 0.5,

    radiusGrowth: 0.004,
    radiusMax:    3.0,
  };

  const TAU = Math.PI * 2;
  const rand = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

  const F_MAI = 0, F_DAO = 1, F_LIXI = 2, F_XU = 3, F_BANH = 4, F_PHAO = 5, F_CHUA = 6;

  const SNAKE_PALETTE = [
    { hue: 45,  name: 'Kim' },
    { hue: 0,   name: 'Hỏa' },
    { hue: 340, name: 'Đào' },
    { hue: 20,  name: 'Cam' },
    { hue: 280, name: 'Tím' },
    { hue: 160, name: 'Lộc' },
    { hue: 195, name: 'Thủy' },
    { hue: 300, name: 'Mận' },
  ];

  /* ============ CANVAS ============ */
  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
  let W = 0, H = 0, DPR = 1;
  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth; H = window.innerHeight;
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }
  window.addEventListener('resize', resize);
  resize();

  /* ============ FOOD SPRITES ============ */
  const foodSprites = [];
  const SP = 32, hcx = SP / 2, hcy = SP / 2;
  function newSprite(fn) {
    const c = document.createElement('canvas');
    c.width = c.height = SP;
    fn(c.getContext('2d'));
    foodSprites.push(c);
  }

  newSprite(g => {
    g.shadowColor = 'rgba(255, 190, 40, 0.9)'; g.shadowBlur = 6;
    g.fillStyle = '#ffd700';
    for (let i = 0; i < 5; i++) {
      const a = i * TAU / 5 - Math.PI / 2;
      g.beginPath();
      g.arc(hcx + Math.cos(a) * SP * 0.18, hcy + Math.sin(a) * SP * 0.18, SP * 0.15, 0, TAU);
      g.fill();
    }
    g.shadowBlur = 0;
    g.fillStyle = '#ff8c00';
    g.beginPath(); g.arc(hcx, hcy, SP * 0.095, 0, TAU); g.fill();
    g.fillStyle = '#fff8e7';
    g.beginPath(); g.arc(hcx - 1.2, hcy - 1.2, SP * 0.04, 0, TAU); g.fill();
  });

  newSprite(g => {
    g.shadowColor = 'rgba(255, 140, 180, 0.85)'; g.shadowBlur = 6;
    g.fillStyle = '#ff8fb1';
    for (let i = 0; i < 5; i++) {
      const a = i * TAU / 5 - Math.PI / 2;
      g.beginPath();
      g.arc(hcx + Math.cos(a) * SP * 0.18, hcy + Math.sin(a) * SP * 0.18, SP * 0.15, 0, TAU);
      g.fill();
    }
    g.shadowBlur = 0;
    g.fillStyle = '#ffcc44';
    g.beginPath(); g.arc(hcx, hcy, SP * 0.095, 0, TAU); g.fill();
    g.fillStyle = '#fff2c4';
    g.beginPath(); g.arc(hcx - 1.2, hcy - 1.2, SP * 0.04, 0, TAU); g.fill();
  });

  newSprite(g => {
    const w = SP * 0.56, h = SP * 0.74;
    const x = (SP - w) / 2, y = (SP - h) / 2;
    g.shadowColor = 'rgba(255, 50, 60, 0.9)'; g.shadowBlur = 6;
    g.fillStyle = '#c8232c'; g.fillRect(x, y, w, h);
    g.shadowBlur = 0;
    g.strokeStyle = '#ffd700'; g.lineWidth = 2;
    g.strokeRect(x + 1, y + 1, w - 2, h - 2);
    g.fillStyle = '#ffd700';
    g.font = `bold ${SP * 0.24}px serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('福', hcx, hcy + 1);
  });

  newSprite(g => {
    const r = SP * 0.35;
    g.shadowColor = 'rgba(255, 210, 60, 1)'; g.shadowBlur = 7;
    g.fillStyle = '#ffd700';
    g.beginPath(); g.arc(hcx, hcy, r, 0, TAU); g.fill();
    g.shadowBlur = 0;
    g.strokeStyle = '#b8860b'; g.lineWidth = 2;
    g.beginPath(); g.arc(hcx, hcy, r * 0.76, 0, TAU); g.stroke();
    g.fillStyle = 'rgba(255, 255, 220, 0.55)';
    g.beginPath(); g.arc(hcx - r * 0.35, hcy - r * 0.35, r * 0.22, 0, TAU); g.fill();
    g.fillStyle = '#1a0508';
    const hw = r * 0.32;
    g.fillRect(hcx - hw, hcy - hw, hw * 2, hw * 2);
  });

  newSprite(g => {
    const size = SP * 0.68;
    const x = (SP - size) / 2, y = (SP - size) / 2;
    g.shadowColor = 'rgba(80, 180, 80, 0.7)'; g.shadowBlur = 6;
    g.fillStyle = '#1f5a1f'; g.fillRect(x, y, size, size);
    g.shadowBlur = 0;
    g.fillStyle = '#2d7a2d'; g.fillRect(x + 2, y + 2, size - 4, size - 4);
    g.fillStyle = '#3fa83f'; g.fillRect(x + 4, y + 4, size - 8, size - 8);
    g.strokeStyle = '#d4c45a'; g.lineWidth = 2;
    g.beginPath();
    g.moveTo(x, y + size / 2); g.lineTo(x + size, y + size / 2);
    g.moveTo(x + size / 2, y); g.lineTo(x + size / 2, y + size);
    g.stroke();
  });

  newSprite(g => {
    const w = SP * 0.35, h = SP * 0.7;
    const x = (SP - w) / 2, y = (SP - h) / 2;
    g.shadowColor = 'rgba(255, 80, 40, 0.9)'; g.shadowBlur = 8;
    g.fillStyle = '#cc1a1a'; g.fillRect(x, y + h * 0.15, w, h * 0.7);
    g.shadowBlur = 0;
    g.fillStyle = '#ffd700';
    g.fillRect(x, y + h * 0.15, w, h * 0.15);
    g.fillRect(x, y + h * 0.7, w, h * 0.15);
    g.strokeStyle = '#ff8c00'; g.lineWidth = 2;
    g.beginPath();
    g.moveTo(x + w / 2, y + h * 0.15);
    g.quadraticCurveTo(x + w / 2 + 4, y + h * 0.05, x + w / 2 + 2, y);
    g.stroke();
  });

  newSprite(g => {
    g.shadowColor = 'rgba(255, 215, 0, 1)'; g.shadowBlur = 15;
    g.strokeStyle = '#ffd700'; g.lineWidth = 2.5;
    g.beginPath(); g.arc(hcx, hcy, SP * 0.42, 0, TAU); g.stroke();
    g.shadowBlur = 10;
    g.fillStyle = '#ffd700';
    g.font = `900 ${SP * 0.6}px serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('A', hcx, hcy + 2);
  });

  /* ============ GRID (gold tint) ============ */
  const GRID_STEP = 130;
  const gridPattern = (() => {
    const c = document.createElement('canvas');
    c.width = c.height = GRID_STEP;
    const g = c.getContext('2d');
    g.strokeStyle = 'rgba(255, 200, 80, 0.055)';
    g.lineWidth = 1;
    g.beginPath();
    g.moveTo(0.5, 0); g.lineTo(0.5, GRID_STEP);
    g.moveTo(0, 0.5); g.lineTo(GRID_STEP, 0.5);
    g.stroke();
    g.fillStyle = 'rgba(255, 180, 60, 0.10)';
    g.beginPath(); g.arc(0, 0, 1.6, 0, TAU); g.fill();
    return ctx.createPattern(c, 'repeat');
  })();

  /* ============ FOOD ============ */
  let foods = [];
  let foodDirty = false;

  function pickFoodType() {
    const r = Math.random() * 100;
    if (r < 30) return F_MAI;
    if (r < 52) return F_DAO;
    if (r < 67) return F_LIXI;
    if (r < 77) return F_XU;
    if (r < 92) return F_BANH;
    if (r < 98) return F_PHAO;
    return F_CHUA;
  }
  function foodValue(t) {
    if (t === F_LIXI) return 2;
    if (t === F_XU)   return 3;
    if (t === F_BANH) return 3;
    if (t === F_PHAO) return 5;
    if (t === F_CHUA) return 0;
    return 1;
  }
  function foodRadiusFor(t) {
    if (t === F_XU)   return 7.5;
    if (t === F_BANH) return 8;
    if (t === F_PHAO) return 8;
    if (t === F_CHUA) return 11;
    return 7;
  }
  function makeFood(x, y, type, r, value) {
    return {
      x, y,
      r: r != null ? r : foodRadiusFor(type),
      type,
      value: value != null ? value : foodValue(type),
      pulse: Math.random() * TAU,
      eaten: false,
    };
  }
  function spawnRandomFood() {
    foods.push(makeFood(rand(20, WORLD.w - 20), rand(20, WORLD.h - 20), pickFoodType()));
  }

  /* ============ BRAIN ============ */
  const BRAIN_KEY = 'tet2027_snake_brain_v3';
  let brain = { gen: 1, hunt: 0.4, avoid: 0.9, playerKills: 0, botDeaths: 0, botKills: 0 };
  (function loadBrain() {
    try {
      const s = localStorage.getItem(BRAIN_KEY);
      if (s) { const b = JSON.parse(s); if (b && typeof b.hunt === 'number') brain = { ...brain, ...b }; }
    } catch (e) {}
  })();
  function saveBrain() {
    try { localStorage.setItem(BRAIN_KEY, JSON.stringify(brain)); } catch (e) {}
  }

  /* ============ SNAKE ============ */
  class Snake {
    constructor(opts) {
      this.color = opts.color;
      this.color2 = opts.color2;
      this.colorDark = opts.colorDark;
      this.isPlayer = !!opts.isPlayer;
      this.name = opts.name || 'Rắn';
      this.angle = opts.angle !== undefined ? opts.angle : rand(0, TAU);
      this.segments = CFG.startSegments;
      this.radius = CFG.baseRadius;
      this.alive = true;
      this.boosting = false;

      this.energy = CFG.boostDuration;
      this.cooldown = 0;
      this.boostDrainTimer = 0;

      this.points = [];
      const sp = this.radius * CFG.segmentFactor;
      const ca = Math.cos(this.angle), sa = Math.sin(this.angle);
      for (let i = 0; i < this.segments; i++) {
        this.points.push({ x: opts.x - ca * sp * i, y: opts.y - sa * sp * i });
      }
      this.aiTimer = 0;
      this.aiTarget = null;
      this._hunting = false;
      this._killer = null;
      this.bbMinX = this.bbMaxX = this.points[0].x;
      this.bbMinY = this.bbMaxY = this.points[0].y;
    }
    get head() { return this.points[0]; }

    updateBBox() {
      const pts = this.points;
      let minX = pts[0].x, maxX = pts[0].x;
      let minY = pts[0].y, maxY = pts[0].y;
      for (let i = 1; i < pts.length; i++) {
        const p = pts[i];
        if (p.x < minX) minX = p.x; else if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y; else if (p.y > maxY) maxY = p.y;
      }
      this.bbMinX = minX; this.bbMaxX = maxX;
      this.bbMinY = minY; this.bbMaxY = maxY;
    }

    update(dt, targetAngle, wantsBoost) {
      if (targetAngle != null) {
        let diff = targetAngle - this.angle;
        while (diff >  Math.PI) diff -= TAU;
        while (diff < -Math.PI) diff += TAU;
        const rate = this.isPlayer ? CFG.turnRate : CFG.botTurnRate;
        this.angle += diff * Math.min(1, rate * dt);
      }

      const sec = dt / 60;
      const canBoost = this.segments > CFG.minSegments;
      let isBoosting = false;

      if (wantsBoost && canBoost && this.energy > 0 && this.cooldown <= 0) {
        isBoosting = true;
        this.energy -= sec;
        if (this.energy <= 0) {
          this.energy = 0;
          isBoosting = false;
          this.cooldown = CFG.boostCooldown;
        }
      } else {
        if (this.cooldown > 0) {
          this.cooldown -= sec;
          if (this.cooldown <= 0) {
            this.cooldown = 0;
            this.energy = CFG.boostDuration;
          }
        }
      }
      this.boosting = isBoosting;

      if (isBoosting) {
        this.boostDrainTimer += sec;
        if (this.boostDrainTimer >= CFG.boostDrainRate) {
          this.boostDrainTimer -= CFG.boostDrainRate;
          if (this.segments > CFG.minSegments) {
            this.segments -= 1;
            const t = this.points[this.points.length - 1];
            foods.push(makeFood(t.x + rand(-7, 7), t.y + rand(-7, 7), F_XU, 5, 1));
          }
        }
      } else {
        this.boostDrainTimer = 0;
      }

      const speed = isBoosting ? CFG.boostSpeed : CFG.baseSpeed;

      this.radius = CFG.baseRadius * Math.min(
        CFG.radiusMax,
        1 + Math.max(0, this.segments - CFG.startSegments) * CFG.radiusGrowth
      );

      const pts = this.points;
      while (pts.length < this.segments) {
        const t = pts[pts.length - 1];
        pts.push({ x: t.x, y: t.y });
      }
      while (pts.length > this.segments) pts.pop();

      const h = pts[0];
      h.x += Math.cos(this.angle) * speed * dt;
      h.y += Math.sin(this.angle) * speed * dt;
      const m = this.radius;
      if (h.x < m) h.x = m; else if (h.x > WORLD.w - m) h.x = WORLD.w - m;
      if (h.y < m) h.y = m; else if (h.y > WORLD.h - m) h.y = WORLD.h - m;

      const sp = this.radius * CFG.segmentFactor;
      const sp2 = sp * sp;
      for (let i = 1; i < pts.length; i++) {
        const p = pts[i], pv = pts[i - 1];
        const dx = pv.x - p.x, dy = pv.y - p.y;
        const d2 = dx * dx + dy * dy;
        if (d2 > sp2) {
          const d = Math.sqrt(d2);
          const t = (d - sp) / d;
          p.x += dx * t;
          p.y += dy * t;
        }
      }
    }
  }

  /* ============ STATE ============ */
  let player = null;
  let snakes = [];
  let camera = { x: WORLD.w / 2, y: WORLD.h / 2, zoom: 1 };
  let running = false;
  let pendingWheel = false;
  const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
  const input = { boost: false };

  /* ============ PARTICLES ============ */
  let particles = [];
  function spawnFireworks(x, y) {
    const colors = ['#ffd700', '#ff4d6d', '#ff8c42', '#ffffff', '#ff66cc', '#66ffcc', '#ffaa33'];
    for (let i = 0; i < 60; i++) {
      const angle = Math.random() * TAU;
      const speed = 1.5 + Math.random() * 6;
      particles.push({
        x, y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 1,
        decay: 0.01 + Math.random() * 0.02,
        color: colors[(Math.random() * colors.length) | 0],
        size: 2 + Math.random() * 3.5,
      });
    }
  }
  function updateParticles(dt) {
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vy += 0.09 * dt;
      p.vx *= 0.985; p.vy *= 0.985;
      p.life -= p.decay * dt;
      if (p.life <= 0) particles.splice(i, 1);
    }
  }
  function drawParticles() {
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      ctx.globalAlpha = p.life;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * p.life, 0, TAU);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  /* ============ INIT ============ */
  function spawnBot() {
    let x = 0, y = 0, tries = 0;
    do {
      x = rand(250, WORLD.w - 250);
      y = rand(250, WORLD.h - 250);
      tries++;
    } while (player && Math.hypot(x - player.head.x, y - player.head.y) < 650 && tries < 40);
    const p = SNAKE_PALETTE[1 + ((Math.random() * (SNAKE_PALETTE.length - 1)) | 0)];
    const bot = new Snake({
      x, y,
      color:     `hsl(${p.hue}, 85%, 58%)`,
      color2:    `hsl(${p.hue}, 95%, 78%)`,
      colorDark: `hsl(${p.hue}, 75%, 22%)`,
      name:      'Rắn ' + p.name,
      angle:     rand(0, TAU),
    });
    bot.updateBBox();
    snakes.push(bot);
  }

  function resetGame() {
    snakes = [];
    foods = [];
    particles = [];
    foodDirty = false;
    pendingWheel = false;

    player = new Snake({
      x: WORLD.w / 2, y: WORLD.h / 2,
      color:     'hsl(45, 95%, 60%)',
      color2:    'hsl(45, 100%, 82%)',
      colorDark: 'hsl(40, 80%, 22%)',
      isPlayer:  true,
      name:      'Bạn',
      angle:     rand(0, TAU),
    });
    player.updateBBox();
    snakes.push(player);

    for (let i = 0; i < CFG.botCount; i++) spawnBot();
    for (let i = 0; i < CFG.foodCount; i++) spawnRandomFood();

    camera.x = player.head.x;
    camera.y = player.head.y;
    camera.zoom = CFG.zoomMax;
  }

  /* ============ BOT AI ============ */
  function botThink(bot, dt) {
    const h = bot.head;
    bot.aiTimer -= dt;
    bot._hunting = false;
    let wantBoost = false;

    if (player && player.alive && brain.hunt > 0.15) {
      const distToPlayer = Math.hypot(player.head.x - h.x, player.head.y - h.y);
      const advantage = bot.segments / Math.max(1, player.segments);

      if (advantage > 1.15 && distToPlayer < 700) {
        const relAngle = Math.atan2(h.y - player.head.y, h.x - player.head.x);
        let angleDiff = relAngle - player.angle;
        while (angleDiff >  Math.PI) angleDiff -= TAU;
        while (angleDiff < -Math.PI) angleDiff += TAU;

        if (Math.abs(angleDiff) < Math.PI * 0.7) {
          bot._hunting = true;
          const leadFrames = 20 + distToPlayer * 0.06;
          const futureX = player.head.x + Math.cos(player.angle) * CFG.baseSpeed * leadFrames;
          const futureY = player.head.y + Math.sin(player.angle) * CFG.baseSpeed * leadFrames;
          let targetAngle = Math.atan2(futureY - h.y, futureX - h.x);
          wantBoost = bot.segments > 40 && distToPlayer < 500 && bot.energy > 1.2;

          const look = 60;
          const cx2 = h.x + Math.cos(targetAngle) * look;
          const cy2 = h.y + Math.sin(targetAngle) * look;
          let wouldHit = false;
          const ppts = player.points;
          for (let i = 2; i < ppts.length; i += 2) {
            const p = ppts[i];
            const dx = p.x - cx2, dy = p.y - cy2;
            const rr = player.radius * 2 + bot.radius;
            if (dx * dx + dy * dy < rr * rr) { wouldHit = true; break; }
          }
          if (wouldHit) targetAngle += Math.PI / 3 * (Math.random() < 0.5 ? 1 : -1);
          return { angle: targetAngle, boost: wantBoost };
        }
      }
    }

    if (bot.aiTimer <= 0) {
      bot.aiTimer = rand(18, 45);
      let best = null, bestD = Infinity;
      for (let i = 0; i < foods.length; i++) {
        const f = foods[i];
        if (f.eaten) continue;
        const w = f.value > 1 ? 0.4 : 1;
        const d = ((f.x - h.x) ** 2 + (f.y - h.y) ** 2) * w;
        if (d < bestD) { bestD = d; best = f; }
      }
      bot.aiTarget = best;
    }

    let target = bot.angle;
    if (bot.aiTarget) target = Math.atan2(bot.aiTarget.y - h.y, bot.aiTarget.x - h.x);

    const margin = 280;
    if (h.x < margin)                target = 0;
    else if (h.x > WORLD.w - margin) target = Math.PI;
    if (h.y < margin)                target = Math.PI / 2;
    else if (h.y > WORLD.h - margin) target = -Math.PI / 2;

    let danger = null, dangerD = 160 * 160 * brain.avoid;
    for (let s = 0; s < snakes.length; s++) {
      const o = snakes[s];
      if (o === bot || !o.alive) continue;
      if (h.x < o.bbMinX - 160 || h.x > o.bbMaxX + 160 ||
          h.y < o.bbMinY - 160 || h.y > o.bbMaxY + 160) continue;
      const pts = o.points;
      for (let i = 0; i < pts.length; i += 3) {
        const p = pts[i];
        const d = (p.x - h.x) ** 2 + (p.y - h.y) ** 2;
        if (d < dangerD) { dangerD = d; danger = p; }
      }
    }
    if (danger) target = Math.atan2(h.y - danger.y, h.x - danger.x);

    wantBoost = bot.segments > 40 && bot.energy > 2 && Math.random() < 0.003;
    return { angle: target, boost: wantBoost };
  }

  /* ============ EAT ============ */
  function eatFood(s) {
    const h = s.head;
    const R = s.radius + 14, R2 = R * R;
    for (let i = 0; i < foods.length; i++) {
      const f = foods[i];
      if (f.eaten) continue;
      const dx = f.x - h.x, dy = f.y - h.y;
      if (dx * dx + dy * dy < R2) {
        f.eaten = true;
        foodDirty = true;
        if (f.type === F_PHAO) spawnFireworks(f.x, f.y);
        if (f.type === F_CHUA) {
          if (s.isPlayer) pendingWheel = true;
        } else {
          s.segments = Math.min(CFG.maxSegments, s.segments + f.value);
        }
      }
    }
  }

  /* ============ COLLISIONS ============ */
  function handleCollisions() {
    const dead = [];
    for (let a = 0; a < snakes.length; a++) {
      const s = snakes[a];
      if (!s.alive) continue;
      const h = s.head;
      const sr = s.radius * 0.55;
      for (let b = 0; b < snakes.length; b++) {
        if (a === b) continue;
        const o = snakes[b];
        if (!o.alive) continue;
        if (h.x < o.bbMinX - sr || h.x > o.bbMaxX + sr ||
            h.y < o.bbMinY - sr || h.y > o.bbMaxY + sr) continue;
        const pts = o.points;
        const rr = o.radius * 0.92 + sr;
        const rr2 = rr * rr;
        for (let i = 4; i < pts.length; i += 2) {
          const p = pts[i];
          const dx = h.x - p.x, dy = h.y - p.y;
          if (dx * dx + dy * dy < rr2) {
            s.alive = false;
            s._killer = o;
            dead.push(s);
            break;
          }
        }
        if (!s.alive) break;
      }
    }

    let changed = false;
    for (const s of dead) {
      if (s.isPlayer) {
        if (s._killer && !s._killer.isPlayer) {
          brain.hunt = Math.min(2, brain.hunt + 0.08);
          brain.playerKills++;
          brain.gen++;
          changed = true;
        }
      } else {
        if (s._killer && s._killer.isPlayer) {
          brain.avoid = Math.min(2.5, brain.avoid + 0.03);
          brain.botDeaths++;
          changed = true;
        } else if (s._killer) {
          brain.botKills++;
          changed = true;
        }
      }
      for (let i = 0; i < s.points.length; i += 2) {
        const p = s.points[i];
        foods.push(makeFood(p.x + rand(-9, 9), p.y + rand(-9, 9), F_XU, rand(5, 8), 2));
      }
      if (s.isPlayer) showGameOver();
    }
    if (changed) saveBrain();
    if (dead.length) snakes = snakes.filter(s => s.alive);
  }

  /* ============ UPDATE ============ */
  let hudTick = 0;
  function update(dt) {
    for (let i = 0; i < foods.length; i++) foods[i].pulse += 0.07 * dt;
    updateParticles(dt);

    if (player && player.alive) {
      const ta = Math.atan2(mouse.y - H / 2, mouse.x - W / 2);
      player.update(dt, ta, input.boost);
    }
    for (let i = 0; i < snakes.length; i++) {
      const s = snakes[i];
      if (s.isPlayer || !s.alive) continue;
      const r = botThink(s, dt);
      s.update(dt, r.angle, r.boost);
    }
    for (let i = 0; i < snakes.length; i++) snakes[i].updateBBox();
    for (let i = 0; i < snakes.length; i++) if (snakes[i].alive) eatFood(snakes[i]);

    if (foodDirty) { foods = foods.filter(f => !f.eaten); foodDirty = false; }

    handleCollisions();

    let botCount = 0;
    for (let i = 0; i < snakes.length; i++) if (!snakes[i].isPlayer) botCount++;
    while (botCount < CFG.botCount) { spawnBot(); botCount++; }
    while (foods.length < CFG.foodCount) spawnRandomFood();

    if (player) {
      const tz = clamp(
        CFG.zoomMax - (player.radius - CFG.baseRadius) * 0.025,
        CFG.zoomMin, CFG.zoomMax
      );
      camera.zoom += (tz - camera.zoom) * Math.min(1, 0.06 * dt);
      if (player.alive) {
        camera.x += (player.head.x - camera.x) * Math.min(1, 0.22 * dt);
        camera.y += (player.head.y - camera.y) * Math.min(1, 0.22 * dt);
      }
    }

    hudTick += dt;
    if (hudTick >= 8) { hudTick = 0; updateHUD(); }
    updateEnergyBar();

    if (pendingWheel) { pendingWheel = false; showWheel(); }
  }

  /* ============ RENDER ============ */
  function drawGrid(cam) {
    const halfW = W / (2 * cam.zoom), halfH = H / (2 * cam.zoom);
    ctx.fillStyle = gridPattern;
    ctx.fillRect(cam.x - halfW, cam.y - halfH, halfW * 2, halfH * 2);
  }
  function drawWorldBorder(cam) {
    const halfW = W / (2 * cam.zoom), halfH = H / (2 * cam.zoom);
    const left = cam.x - halfW, right = cam.x + halfW;
    const top = cam.y - halfH, bottom = cam.y + halfH;
    ctx.beginPath();
    if (top < 0)          { ctx.moveTo(0, 0);       ctx.lineTo(WORLD.w, 0); }
    if (bottom > WORLD.h) { ctx.moveTo(0, WORLD.h); ctx.lineTo(WORLD.w, WORLD.h); }
    if (left < 0)         { ctx.moveTo(0, 0);       ctx.lineTo(0, WORLD.h); }
    if (right > WORLD.w)  { ctx.moveTo(WORLD.w, 0); ctx.lineTo(WORLD.w, WORLD.h); }
    ctx.strokeStyle = 'rgba(150, 90, 20, 0.75)'; ctx.lineWidth = 10; ctx.stroke();
    ctx.strokeStyle = 'rgba(255, 215, 0, 0.9)';  ctx.lineWidth = 4;  ctx.stroke();
  }
  function drawFoods(cam) {
    const pad = 40;
    const halfW = W / (2 * cam.zoom) + pad, halfH = H / (2 * cam.zoom) + pad;
    const left = cam.x - halfW, right = cam.x + halfW;
    const top = cam.y - halfH, bottom = cam.y + halfH;
    for (let i = 0; i < foods.length; i++) {
      const f = foods[i];
      if (f.x < left || f.x > right || f.y < top || f.y > bottom) continue;
      const sprite = foodSprites[f.type];
      const pulseAmt = f.type === F_CHUA ? 0.30 : 0.16;
      const r = f.r * (1 + Math.sin(f.pulse) * pulseAmt);
      const ds = r * 2.6;
      ctx.drawImage(sprite, f.x - ds * 0.5, f.y - ds * 0.5, ds, ds);
    }
  }
  function drawSnake(s, cam) {
    const pts = s.points;
    if (pts.length < 2) return;
    const pad = s.radius + 30;
    const halfW = W / (2 * cam.zoom) + pad, halfH = H / (2 * cam.zoom) + pad;
    if (s.bbMaxX < cam.x - halfW || s.bbMinX > cam.x + halfW ||
        s.bbMaxY < cam.y - halfH || s.bbMinY > cam.y + halfH) return;

    const r = s.radius;

    if (s._hunting) {
      const h = pts[0];
      const pulse = 1 + Math.sin(performance.now() * 0.008) * 0.15;
      ctx.strokeStyle = 'rgba(255, 77, 109, 0.8)';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(h.x, h.y, r * 1.9 * pulse, 0, TAU);
      ctx.stroke();
    }
    if (s.boosting) {
      const h = pts[0];
      const pulse = 1 + Math.sin(performance.now() * 0.02) * 0.15;
      ctx.strokeStyle = s.color2;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(h.x, h.y, r * 1.4 * pulse, 0, TAU);
      ctx.stroke();
    }

    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
    ctx.strokeStyle = s.colorDark; ctx.lineWidth = r * 2 + 4; ctx.stroke();
    ctx.strokeStyle = s.color;     ctx.lineWidth = r * 2;     ctx.stroke();
    ctx.strokeStyle = s.color2;    ctx.lineWidth = r * 0.75;
    ctx.globalAlpha = 0.45; ctx.stroke(); ctx.globalAlpha = 1;

    const h = pts[0];
    ctx.save();
    ctx.translate(h.x, h.y);
    ctx.rotate(s.angle);
    ctx.beginPath(); ctx.arc(0, 0, r * 1.05, 0, TAU);
    ctx.fillStyle = s.color; ctx.fill();
    ctx.strokeStyle = s.colorDark; ctx.lineWidth = 1.5; ctx.stroke();

    const er = r * 0.34, ex = r * 0.32, ey = r * 0.5;
    ctx.beginPath();
    ctx.arc(ex, -ey, er, 0, TAU); ctx.arc(ex, ey, er, 0, TAU);
    ctx.fillStyle = '#fff'; ctx.fill();
    ctx.beginPath();
    ctx.arc(ex + er * 0.4, -ey, er * 0.55, 0, TAU);
    ctx.arc(ex + er * 0.4,  ey, er * 0.55, 0, TAU);
    ctx.fillStyle = '#1a0508'; ctx.fill();
    ctx.restore();
  }
  function drawMinimap() {
    const size = 150, pad = 22;
    const x = W - size - pad, y = H - size - pad;
    const sc = size / WORLD.w;
    ctx.globalAlpha = 0.92;
    ctx.fillStyle = 'rgba(30, 4, 8, 0.88)'; ctx.fillRect(x, y, size, size);
    ctx.strokeStyle = 'rgba(255, 200, 60, 0.55)'; ctx.lineWidth = 1.5;
    ctx.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1);
    for (let i = 0; i < snakes.length; i++) {
      const s = snakes[i];
      const h = s.head;
      ctx.beginPath();
      ctx.arc(x + h.x * sc, y + h.y * sc, s.isPlayer ? 4 : 2.6, 0, TAU);
      ctx.fillStyle = s.isPlayer ? '#ffd700' : s.color;
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  function render() {
    ctx.fillStyle = '#1a0508'; ctx.fillRect(0, 0, W, H);
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(camera.zoom, camera.zoom);
    ctx.translate(-camera.x, -camera.y);
    drawGrid(camera);
    drawWorldBorder(camera);
    drawFoods(camera);
    for (let i = 0; i < snakes.length; i++) drawSnake(snakes[i], camera);
    drawParticles();
    ctx.restore();
    drawMinimap();
  }

  /* ============ WHEEL (Tết palette) ============ */
  const WHEEL_PRIZES = [
    { label: '+30 đốt',  value: 30,  color: '#ffd700' },
    { label: '+100 đốt', value: 100, color: '#ff4d6d' },
    { label: '+50 đốt',  value: 50,  color: '#ff8fb1' },
    { label: '+150 đốt', value: 150, color: '#ffb347' },
    { label: '+75 đốt',  value: 75,  color: '#ff8c42' },
    { label: '+200 đốt', value: 200, color: '#ffd700' },
    { label: '+20 đốt',  value: 20,  color: '#69db7c' },
    { label: '+120 đốt', value: 120, color: '#ff4d6d' },
  ];
  let wheelAngle = 0;
  let wheelSpinning = false;

  function drawWheel() {
    const wc = document.getElementById('wheelCanvas');
    if (!wc) return;
    const g = wc.getContext('2d');
    const wcx = 200, wcy = 200, r = 180;
    g.clearRect(0, 0, 400, 400);
    const sa = TAU / WHEEL_PRIZES.length;
    for (let i = 0; i < WHEEL_PRIZES.length; i++) {
      const start = i * sa + wheelAngle;
      const end = start + sa;
      g.beginPath();
      g.moveTo(wcx, wcy); g.arc(wcx, wcy, r, start, end); g.closePath();
      g.fillStyle = WHEEL_PRIZES[i].color; g.fill();
      g.strokeStyle = '#1a0508'; g.lineWidth = 3; g.stroke();
      g.save();
      g.translate(wcx, wcy); g.rotate(start + sa / 2);
      g.textAlign = 'right'; g.textBaseline = 'middle';
      g.fillStyle = '#4a0508';
      g.font = 'bold 16px "Courier New", monospace';
      g.fillText(WHEEL_PRIZES[i].label, r - 22, 0);
      g.restore();
    }
    g.beginPath(); g.arc(wcx, wcy, 30, 0, TAU);
    g.fillStyle = '#ffd700'; g.fill();
    g.strokeStyle = '#1a0508'; g.lineWidth = 3; g.stroke();
  }

  function showWheel() {
    if (!player || !player.alive) return;
    running = false;
    input.boost = false;
    wheelSpinning = false;
    wheelAngle = 0;
    const ov = document.getElementById('wheelOverlay');
    if (!ov) return;
    ov.classList.remove('hidden');
    document.getElementById('wheelResult').textContent = '';
    const btn = document.getElementById('spinBtn');
    btn.disabled = false;
    btn.textContent = 'QUAY NGAY 🎁';
    drawWheel();
  }

  function spinWheel() {
    if (wheelSpinning) return;
    wheelSpinning = true;
    const btn = document.getElementById('spinBtn');
    btn.disabled = true;
    btn.textContent = 'ĐANG QUAY...';
    document.getElementById('wheelResult').textContent = '';

    const sa = TAU / WHEEL_PRIZES.length;
    const targetIdx = Math.floor(Math.random() * WHEEL_PRIZES.length);
    const startWa = wheelAngle;
    const desiredWa = -Math.PI / 2 - (targetIdx + 0.5) * sa;
    let delta = desiredWa - startWa;
    delta = ((delta % TAU) + TAU) % TAU;
    const spins = 5 + Math.floor(Math.random() * 3);
    const targetWa = startWa + delta + TAU * spins;

    const duration = 4000;
    const start = performance.now();

    function animate(now) {
      const t = Math.min(1, (now - start) / duration);
      const ease = 1 - Math.pow(1 - t, 4);
      wheelAngle = startWa + (targetWa - startWa) * ease;
      drawWheel();
      if (t < 1) {
        requestAnimationFrame(animate);
      } else {
        wheelSpinning = false;
        const prize = WHEEL_PRIZES[targetIdx];
        document.getElementById('wheelResult').textContent = `🎉 Bạn nhận được ${prize.label}!`;
        if (player && player.alive) {
          player.segments = Math.min(CFG.maxSegments, player.segments + prize.value);
          if (player.head) spawnFireworks(player.head.x, player.head.y);
        }
        setTimeout(() => {
          document.getElementById('wheelOverlay').classList.add('hidden');
          running = true;
          updateHUD();
        }, 2200);
      }
    }
    requestAnimationFrame(animate);
  }

  /* ============ HUD ============ */
  const scoreValEl = document.getElementById('scoreVal');
  const lbListEl = document.getElementById('lbList');
  const overlayEl = document.getElementById('overlay');
  const overTextEl = document.getElementById('overText');
  const startBtn = document.getElementById('startBtn');
  const fpsEl = document.getElementById('fps');
  const brainGenEl = document.getElementById('brainGen');
  const brainKillsEl = document.getElementById('brainKills');
  const brainHuntEl = document.getElementById('brainHunt');
  const energyFill = document.getElementById('energyFill');
  const energyStatus = document.getElementById('energyStatus');

  let _hudHtml = '';
  function updateHUD() {
    if (player) scoreValEl.textContent = player.segments;
    const sorted = [...snakes].sort((a, b) => b.segments - a.segments).slice(0, 6);
    let html = '';
    for (let i = 0; i < sorted.length; i++) {
      const s = sorted[i];
      html += `<li class="${s.isPlayer ? 'me' : ''}">
        <span><span class="dot" style="background:${s.color};color:${s.color}"></span>${s.isPlayer ? 'Bạn' : 'Rắn ' + s.name.split(' ').pop()}</span>
        <span>${s.segments}</span>
      </li>`;
    }
    if (html !== _hudHtml) { _hudHtml = html; lbListEl.innerHTML = html; }

    if (brainGenEl)   brainGenEl.textContent = brain.gen;
    if (brainKillsEl) brainKillsEl.textContent = brain.playerKills;
    if (brainHuntEl)  brainHuntEl.textContent = Math.round(Math.min(1, brain.hunt) * 100) + '%';
  }

  function updateEnergyBar() {
    if (!player || !energyFill || !energyStatus) return;
    if (player.cooldown > 0) {
      const pct = (1 - player.cooldown / CFG.boostCooldown) * 100;
      energyFill.style.width = pct + '%';
      energyFill.classList.add('cooldown');
      energyStatus.textContent = 'HỒI: ' + player.cooldown.toFixed(1) + 's';
    } else {
      const pct = (player.energy / CFG.boostDuration) * 100;
      energyFill.style.width = pct + '%';
      energyFill.classList.remove('cooldown');
      energyStatus.textContent = '';
    }
  }

  function showGameOver() {
    running = false;
    input.boost = false;
    overTextEl.innerHTML = `Bạn đạt <b style="color:#ffd700">${player.segments}</b> đốt!<br>Chúc Xuân Đinh Mùi 2027 an khang thịnh vượng 🧧`;
    startBtn.textContent = '🧧 CHƠI LẠI';
    overlayEl.classList.remove('hidden');
  }

  /* ============ INPUT ============ */
  window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
  window.addEventListener('mousedown', e => { if (e.button === 0) input.boost = true; });
  window.addEventListener('mouseup',   e => { if (e.button === 0) input.boost = false; });
  window.addEventListener('blur', () => { input.boost = false; });
  window.addEventListener('keydown', e => {
    if (e.code === 'Space') { e.preventDefault(); input.boost = true; }
  });
  window.addEventListener('keyup', e => {
    if (e.code === 'Space') input.boost = false;
  });
  window.addEventListener('touchmove', e => {
    const t = e.touches[0];
    if (t) { mouse.x = t.clientX; mouse.y = t.clientY; }
    e.preventDefault();
  }, { passive: false });
  window.addEventListener('touchstart', e => {
    const t = e.touches[0];
    if (t) { mouse.x = t.clientX; mouse.y = t.clientY; }
  }, { passive: true });

  document.getElementById('spinBtn').addEventListener('click', spinWheel);

  startBtn.addEventListener('click', (e) => {
    if (e.shiftKey) {
      brain = { gen: 1, hunt: 0.4, avoid: 0.9, playerKills: 0, botDeaths: 0, botKills: 0 };
      saveBrain(); updateHUD();
      overTextEl.innerHTML = '🧠 <b>AI brain đã reset!</b>';
      return;
    }
    overlayEl.classList.add('hidden');
    document.getElementById('wheelOverlay').classList.add('hidden');
    resetGame(); updateHUD();
    running = true;
    input.boost = false;
    mouse.x = W / 2; mouse.y = H / 2;
  });

  /* ============ LOOP ============ */
  const FRAME_MS = 1000 / 62;
  let lastTs = 0, accum = 0;
  let fpsFrames = 0, fpsTime = 0;

  function loop(ts) {
    requestAnimationFrame(loop);
    if (lastTs === 0) { lastTs = ts; return; }
    accum += ts - lastTs;
    lastTs = ts;
    if (accum < FRAME_MS) return;
    let dt = accum / 16.6667;
    if (dt > 3) dt = 3;
    accum -= FRAME_MS;
    if (accum > 100) accum = 0;

    fpsFrames++;
    fpsTime += dt * 16.6667;
    if (fpsTime >= 1000) {
      if (fpsEl) fpsEl.textContent = Math.round(fpsFrames * 1000 / fpsTime) + ' FPS';
      fpsFrames = 0; fpsTime = 0;
    }

    if (running && player) {
      update(dt);
    } else if (player) {
      for (let i = 0; i < snakes.length; i++) {
        const s = snakes[i];
        if (s.isPlayer || !s.alive) continue;
        const r = botThink(s, dt);
        s.update(dt, r.angle, r.boost);
      }
      for (let i = 0; i < snakes.length; i++) snakes[i].updateBBox();
      updateParticles(dt);
    }
    render();
  }

  resetGame();
  updateHUD();
  requestAnimationFrame(loop);

})();