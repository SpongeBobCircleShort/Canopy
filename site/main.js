/* Canopy landing — point-cloud tree, signal annotations, cursor light. */

(() => {
  const hero = document.querySelector('.hero');
  const scene = document.getElementById('scene');
  const veil = document.getElementById('veil');
  const cardsHost = document.getElementById('cards');
  const cursorEl = document.getElementById('cursor');
  const hintEl = document.getElementById('hint');
  const ctx = scene.getContext('2d');
  const vctx = veil.getContext('2d');

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let W = 0, H = 0, DPR = 1, U = 0;
  let points = [];          // {x,y,r,col,a,ph,amp,sp}
  let tips = [];            // branch endpoints, candidate anchors
  let groundPts = [];
  let patches = [];         // red anomaly spots {x,y}
  let treeCenter = { x: 0, y: 0 };
  let treeTop = 0;
  let cards = [];
  let rings = [];
  let motes = [];
  let sonar = null;
  let lastSonar = 0;

  const mouse = { x: 0, y: 0, seen: false, lastMove: -1e9, travelled: 0 };
  const light = { x: 0, y: 0 };

  const rand = (a, b) => a + Math.random() * (b - a);
  const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) * 0.8;
  const lerp = (a, b, t) => a + (b - a) * t;

  /* ---------------- signal card data ---------------- */

  const SIGNALS = [
    { id: '02', name: 'HORNBILL CALL',    conf: 'CONF 0.94', time: 'T 05:12 IST', date: 'D 14.07.26', coord: '27.2911 N · 95.4103 E', site: 'DEHING PATKAI', kind: 'bio' },
    { id: '07', name: 'GIBBON DUET',      conf: 'CONF 0.91', time: 'T 06:03 IST', date: 'D 16.07.26', coord: '26.6810 N · 94.3535 E', site: 'HOLLONGAPAR', kind: 'bio' },
    { id: '11', name: 'CICADA CHORUS',    conf: 'CONF 0.88', time: 'T 18:41 IST', date: 'D 12.07.26', coord: '26.5775 N · 93.1711 E', site: 'KAZIRANGA', kind: 'bio' },
    { id: '19', name: 'UNKNOWN IMPULSE',  conf: 'FLAGGED',   time: 'T 02:26 IST', date: 'D 17.07.26', coord: '21.8642 N · 84.0290 E', site: 'REVIEW QUEUE', kind: 'anomaly' },
    { id: '23', name: 'CHAINSAW MATCH',   conf: 'CONF 0.97', time: 'T 03:44 IST', date: 'D 17.07.26', coord: '21.8637 N · 84.0301 E', site: 'ALERT SENT', kind: 'anomaly' },
    { id: '05', name: 'RAIN FRONT',       conf: 'CONF 0.99', time: 'T 22:10 IST', date: 'D 15.07.26', coord: '13.5026 N · 75.0900 E', site: 'AGUMBE', kind: 'bio' },
    { id: '31', name: 'NDVI DROP 0.4 HA', conf: 'S2 PASS',   time: 'T 10:30 UTC', date: 'D 13.07.26', coord: '21.8650 N · 84.0287 E', site: 'CROSS-CHECK', kind: 'sat' },
    { id: '09', name: 'NIGHTJAR',         conf: 'CONF 0.86', time: 'T 01:37 IST', date: 'D 16.07.26', coord: '24.4622 N · 92.9377 E', site: 'BARAK VALLEY', kind: 'bio' },
    { id: '14', name: 'AMBIENT BASELINE', conf: 'CONF 0.99', time: 'T CONT',      date: 'D LIVE',     coord: '27.2903 N · 95.4111 E', site: 'STATION 04', kind: 'bio' },
  ];

  const SLOTS = [
    { x: 0.055, y: 0.30 }, { x: 0.045, y: 0.55 }, { x: 0.10, y: 0.76 },
    { x: 0.815, y: 0.28 }, { x: 0.845, y: 0.52 }, { x: 0.78, y: 0.74 },
    { x: 0.06, y: 0.135 }, { x: 0.79, y: 0.135 }, { x: 0.315, y: 0.865 },
  ];

  /* ---------------- tree generation ---------------- */

  function barkColor(depth) {
    if (Math.random() < 0.12 && depth < 5) {
      const g = rand(130, 170);
      return q(rand(95, 130), g, rand(85, 110));   // moss on bark
    }
    const b = rand(170, 240);
    return q(b, b * 0.93, b * 0.82);               // warm pale bark
  }

  function q(r, g, b) {
    return `rgb(${r & ~15},${g & ~15},${b & ~15})`;
  }

  function addPoint(x, y, col, a, r, amp) {
    points.push({
      x, y, col, a,
      r: r || (Math.random() < 0.12 ? 1.6 : 1),
      ph: Math.random() * Math.PI * 2,
      amp: amp !== undefined ? amp : 0.5,
      sp: rand(0.6, 1.6),
    });
  }

  function branch(x, y, angle, len, width, depth, maxDepth) {
    const steps = Math.max(3, Math.round(len / 13));
    let px = x, py = y, a = angle;
    for (let i = 0; i < steps; i++) {
      a += rand(-0.09, 0.09);
      const nx = px + Math.cos(a) * (len / steps);
      const ny = py + Math.sin(a) * (len / steps);
      const density = Math.max(2, Math.round(width * 2.2));
      for (let k = 0; k < density; k++) {
        const t = Math.random();
        addPoint(
          lerp(px, nx, t) + gauss() * width * 0.55,
          lerp(py, ny, t) + gauss() * width * 0.55,
          barkColor(depth),
          rand(0.65, 1.0),
          undefined,
          0.25 + depth * 0.16
        );
      }
      px = nx; py = ny;
    }
    if (depth >= maxDepth || width < 1.1 || len < U * 0.012) {
      tips.push({ x: px, y: py });
      foliage(px, py, len * 1.9);
      return;
    }
    const kids = depth === 0 ? 4 + (Math.random() < 0.5 ? 1 : 0) : (Math.random() < 0.72 ? 2 : 3);
    for (let c = 0; c < kids; c++) {
      let na;
      if (depth === 0) {
        na = -Math.PI / 2 + lerp(-1.3, 1.3, kids === 1 ? 0.5 : c / (kids - 1)) + rand(-0.12, 0.12);
      } else {
        na = a + rand(-0.72, 0.72);
        na = lerp(na, -Math.PI / 2, 0.08);        // slight upward bias
      }
      branch(px, py, na, len * rand(0.7, 0.84), width * rand(0.5, 0.64), depth + 1, maxDepth);
    }
  }

  function foliage(x, y, radius) {
    const n = Math.round(radius * 1.1);
    for (let i = 0; i < n; i++) {
      const th = Math.random() * Math.PI * 2;
      const rr = Math.sqrt(Math.random()) * radius;
      const g = rand(120, 175);
      addPoint(
        x + Math.cos(th) * rr * 1.25,
        y + Math.sin(th) * rr * 0.8,
        q(rand(90, 140), g, rand(80, 115)),
        rand(0.35, 0.75),
        1,
        rand(0.9, 1.7)
      );
    }
  }

  function buildGround(cx, gy) {
    const rx = U * 0.30, ry = U * 0.052;
    const mossSpots = Array.from({ length: 7 }, () => ({
      x: cx + gauss() * rx * 0.8,
      y: gy + gauss() * ry * 0.8,
      r: rand(U * 0.03, U * 0.08),
    }));
    const n = Math.round(U * 1.35);
    for (let i = 0; i < n; i++) {
      const th = Math.random() * Math.PI * 2;
      const rr = Math.sqrt(Math.random());
      const x = cx + Math.cos(th) * rx * rr;
      const y = gy + Math.sin(th) * ry * rr;
      let col, a;
      const nearMoss = mossSpots.some(m => (x - m.x) ** 2 + ((y - m.y) * 3) ** 2 < m.r ** 2);
      if (nearMoss || Math.random() < 0.3) {
        const g = rand(120, 180);
        col = q(rand(85, 130), g, rand(75, 110));
        a = rand(0.3, 0.7);
      } else {
        const b = rand(110, 180);
        col = q(b, b * 0.95, b * 0.85);
        a = rand(0.15, 0.45);
      }
      addPoint(x, y, col, a * (1.2 - rr * 0.6), 1, 0.15);
      groundPts.push({ x, y });
    }
  }

  function buildRoots(cx, gy) {
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 2 + rand(-1.1, 1.1);
      branchSimple(cx + rand(-6, 6), gy - 2, a, U * rand(0.03, 0.055), 3.4);
    }
  }

  function branchSimple(x, y, angle, len, width) {
    const steps = 5;
    let px = x, py = y, a = angle;
    for (let i = 0; i < steps; i++) {
      a += rand(-0.2, 0.2);
      const nx = px + Math.cos(a) * (len / steps);
      const ny = py + Math.sin(a) * (len / steps) * 0.5;
      for (let k = 0; k < Math.round(width); k++) {
        const t = Math.random();
        const b = rand(120, 190);
        addPoint(
          lerp(px, nx, t) + gauss() * width * 0.6,
          lerp(py, ny, t) + gauss() * width * 0.4,
          q(b, b * 0.93, b * 0.82),
          rand(0.2, 0.55), 1, 0.15
        );
      }
      px = nx; py = ny;
      width *= 0.75;
    }
  }

  function paintAnomalies() {
    patches = [];
    const candidates = points.filter(p => p.y < treeCenter.y + U * 0.1 && p.y > treeTop + U * 0.08);
    for (let i = 0; i < 3 && candidates.length; i++) {
      const c = candidates[(Math.random() * candidates.length) | 0];
      patches.push({ x: c.x, y: c.y });
      const rr = U * 0.022;
      for (const p of points) {
        if ((p.x - c.x) ** 2 + (p.y - c.y) ** 2 < rr * rr && Math.random() < 0.6) {
          p.col = q(rand(195, 235), rand(70, 100), rand(50, 70));
          p.a = Math.min(0.9, p.a + 0.2);
        }
      }
    }
  }

  function buildScene() {
    points = []; tips = []; groundPts = []; rings = []; motes = [];
    const cx = W * 0.5;
    const gy = H * 0.80;
    U = Math.min(W * 0.95, H * 1.05);
    const trunkLen = U * 0.165;
    const maxDepth = W < 760 ? 6 : 7;

    branch(cx, gy, -Math.PI / 2, trunkLen, U * 0.024, 0, maxDepth);
    treeTop = Math.min(...tips.map(t => t.y));
    treeCenter = { x: cx, y: (gy + treeTop) / 2 };
    buildGround(cx, gy + 6);
    buildRoots(cx, gy);
    paintAnomalies();

    // cap + sort by colour so fillStyle changes rarely
    const cap = W < 760 ? 6000 : 13500;
    if (points.length > cap) {
      points = points.filter(() => Math.random() < cap / points.length);
    }
    points.sort((a, b) => (a.col < b.col ? -1 : 1));

    for (let i = 0; i < (W < 760 ? 16 : 34); i++) motes.push(newMote(true));
  }

  function newMote(scatter) {
    const t = tips[(Math.random() * tips.length) | 0] || treeCenter;
    return {
      x: t.x + rand(-8, 8),
      y: t.y + rand(-8, 8) - (scatter ? rand(0, U * 0.12) : 0),
      vy: rand(-16, -7) / 1000,
      ph: Math.random() * Math.PI * 2,
      life: rand(6000, 11000),
      age: scatter ? rand(0, 5000) : 0,
    };
  }

  /* ---------------- cards ---------------- */

  function buildCards() {
    cardsHost.innerHTML = '';
    cards = SIGNALS.map((sig, i) => {
      const el = document.createElement('div');
      el.className = 'sig-card' + (sig.kind === 'anomaly' ? ' anomaly' : '');
      el.dataset.slot = i;
      el.innerHTML =
        `<canvas class="spec" width="160" height="24"></canvas>` +
        `<div class="r1">ID ${sig.id} · ${sig.name}</div>` +
        `<div>${sig.conf} · ${sig.time} · ${sig.date}</div>` +
        `<div>${sig.coord} [${sig.site}]</div>`;
      cardsHost.appendChild(el);
      const spec = el.querySelector('.spec');
      return {
        sig, el, spec,
        sctx: spec.getContext('2d'),
        specH: rand(0.2, 0.7),
        lastSpec: 0,
        rect: null, anchor: null,
        alpha: 0, on: Math.random() < 0.6,
        nextFlip: performance.now() + rand(1500, 9000),
        nextPulse: 0,
        pulses: [],
      };
    });
    layoutCards();
  }

  function layoutCards() {
    const anchorsUsed = new Set();
    let anomalyIdx = 0;
    cards.forEach((card, i) => {
      const slot = SLOTS[i];
      const w = 178;
      const x = Math.min(Math.max(slot.x * W, 8), W - w - 8);
      const y = slot.y * H;
      card.el.style.left = x + 'px';
      card.el.style.top = y + 'px';
      const r = card.el.getBoundingClientRect();
      card.rect = { x, y, w: r.width || w, h: r.height || 86 };
      card.visible = card.el.offsetWidth > 0;   // media queries hide some slots

      if (card.sig.kind === 'anomaly' && patches.length) {
        card.anchor = patches[anomalyIdx++ % patches.length];
      } else if (card.sig.kind === 'sat' && groundPts.length) {
        let best = null, bd = 1e18;
        for (let k = 0; k < groundPts.length; k += 7) {
          const g = groundPts[k];
          const d = (g.x - x) ** 2 + (g.y - y) ** 2;
          if (d < bd) { bd = d; best = g; }
        }
        card.anchor = best;
      } else {
        const sx = x + card.rect.w / 2, sy = y + card.rect.h / 2;
        const dx = sx - treeCenter.x, sl = Math.hypot(dx, sy - treeCenter.y) || 1;
        let best = null, bs = -1e18;
        tips.forEach((t, ti) => {
          if (anchorsUsed.has(ti)) return;
          const tx = t.x - treeCenter.x, ty = t.y - treeCenter.y;
          const tl = Math.hypot(tx, ty) || 1;
          const dot = (tx * dx + ty * (sy - treeCenter.y)) / (tl * sl);
          const score = dot + (tl / (U * 0.4)) * 0.25;
          if (score > bs) { bs = score; best = ti; }
        });
        if (best != null) { anchorsUsed.add(best); card.anchor = tips[best]; }
        else card.anchor = treeCenter;
      }
    });
  }

  function cardCorner(card) {
    const { x, y, w, h } = card.rect;
    const a = card.anchor;
    return {
      x: a.x < x + w / 2 ? x : x + w,
      y: a.y < y + h / 2 ? y : y + h,
    };
  }

  function stepSpec(card, now) {
    if (now - card.lastSpec < 90) return;
    card.lastSpec = now;
    const c = card.sctx, cw = card.spec.width, ch = card.spec.height;
    c.drawImage(card.spec, -3, 0);
    c.clearRect(cw - 3, 0, 3, ch);
    card.specH += rand(-0.16, 0.16);
    if (card.sig.kind === 'anomaly' && Math.random() < 0.08) card.specH = rand(0.85, 1);
    card.specH = Math.min(1, Math.max(0.08, card.specH));
    const h = card.specH * (ch - 3);
    c.fillStyle = card.sig.kind === 'anomaly' ? 'rgba(224,90,58,0.85)' : 'rgba(148,168,120,0.8)';
    c.fillRect(cw - 3, ch - h, 2, h);
    c.fillStyle = 'rgba(255,255,255,0.9)';
    c.fillRect(cw - 3, ch - h, 2, 1);
  }

  /* ---------------- input ---------------- */

  function onMove(cx, cy) {
    const r = hero.getBoundingClientRect();
    const x = cx - r.left, y = cy - r.top;
    if (y < 0 || y > r.height) return;
    if (mouse.seen) mouse.travelled += Math.hypot(x - mouse.x, y - mouse.y);
    mouse.x = x; mouse.y = y;
    mouse.seen = true;
    mouse.lastMove = performance.now();
    if (mouse.travelled > 500) hintEl.classList.add('gone');
  }

  window.addEventListener('mousemove', e => onMove(e.clientX, e.clientY), { passive: true });
  document.documentElement.addEventListener('mouseleave', () => {
    mouse.lastMove = performance.now() - 3000;   // resume the idle drift quickly
  });
  window.addEventListener('touchmove', e => {
    if (e.touches[0]) onMove(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });

  /* ---------------- render ---------------- */

  function drawScene(t, dt, now) {
    ctx.clearRect(0, 0, W, H);

    // sonar ellipse from the trunk base
    if (now - lastSonar > 6200) { lastSonar = now; sonar = { p: 0 }; }
    if (sonar) {
      sonar.p += dt / 4200;
      if (sonar.p >= 1) sonar = null;
      else {
        ctx.strokeStyle = `rgba(232,228,218,${0.16 * (1 - sonar.p)})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.ellipse(W * 0.5, H * 0.80 + 6, U * 0.32 * sonar.p, U * 0.056 * sonar.p, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    // point cloud
    let prevCol = null;
    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      if (p.col !== prevCol) { ctx.fillStyle = p.col; prevCol = p.col; }
      ctx.globalAlpha = p.a * (0.72 + 0.28 * Math.sin(t * p.sp + p.ph));
      ctx.fillRect(
        p.x + Math.sin(t * 0.4 + p.ph) * p.amp,
        p.y + Math.cos(t * 0.33 + p.ph * 1.3) * p.amp * 0.6,
        p.r, p.r
      );
    }
    ctx.globalAlpha = 1;

    // rising motes
    for (const m of motes) {
      m.age += dt;
      if (m.age > m.life) Object.assign(m, newMote(false));
      m.y += m.vy * dt;
      const fade = Math.min(m.age / 900, 1 - m.age / m.life, 1);
      ctx.globalAlpha = Math.max(0, fade * 0.7);
      ctx.fillStyle = 'rgb(240,236,214)';
      ctx.fillRect(m.x + Math.sin(t * 0.8 + m.ph) * 6, m.y, 1, 1);
    }
    ctx.globalAlpha = 1;

    // signal lines, pulses, cards
    for (const card of cards) {
      const visible = !!(card.rect && card.visible);
      if (now > card.nextFlip) {
        card.on = !card.on;
        card.nextFlip = now + (card.on ? rand(7000, 12000) : rand(3000, 6500));
        if (card.on) card.nextPulse = now + 200;
      }
      const target = card.on && visible ? 1 : 0;
      card.alpha += (target - card.alpha) * Math.min(1, dt / 300);
      card.el.style.opacity = card.alpha.toFixed(3);
      if (card.alpha < 0.02 || !visible) { card.pulses.length = 0; continue; }

      stepSpec(card, now);

      const a = card.anchor, c = cardCorner(card);
      ctx.strokeStyle = `rgba(232,228,218,${0.30 * card.alpha})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(c.x, c.y);
      ctx.stroke();

      const ember = card.sig.kind === 'anomaly';
      ctx.fillStyle = ember ? `rgba(224,90,58,${0.9 * card.alpha})` : `rgba(232,228,218,${0.85 * card.alpha})`;
      ctx.beginPath();
      ctx.arc(a.x, a.y, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = card.alpha;
      ctx.strokeStyle = ember ? 'rgba(224,90,58,0.7)' : 'rgba(232,228,218,0.6)';
      ctx.strokeRect(c.x - 2.5, c.y - 2.5, 5, 5);
      ctx.globalAlpha = 1;

      if (now > card.nextPulse) {
        card.nextPulse = now + rand(2300, 3800);
        card.pulses.push({ t: 0 });
        rings.push({ x: a.x, y: a.y, r: 2, a: 0.5, ember });
      }
      card.pulses = card.pulses.filter(p => {
        p.t += dt / 900;
        if (p.t >= 1) return false;
        const px = lerp(a.x, c.x, p.t), py = lerp(a.y, c.y, p.t);
        ctx.fillStyle = ember ? 'rgba(255,140,100,0.95)' : 'rgba(255,250,230,0.95)';
        ctx.globalAlpha = card.alpha;
        ctx.beginPath();
        ctx.arc(px, py, 1.6, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
        return true;
      });
    }

    // expanding rings at anchors
    rings = rings.filter(r => {
      r.r += dt * 0.022;
      r.a *= Math.pow(0.998, dt);
      if (r.a < 0.02 || r.r > 60) return false;
      ctx.strokeStyle = r.ember
        ? `rgba(224,90,58,${r.a})`
        : `rgba(232,228,218,${r.a})`;
      ctx.beginPath();
      ctx.arc(r.x, r.y, r.r, 0, Math.PI * 2);
      ctx.stroke();
      return true;
    });
  }

  function drawVeil(t) {
    vctx.clearRect(0, 0, W, H);
    vctx.fillStyle = 'rgba(2,2,2,0.93)';
    vctx.fillRect(0, 0, W, H);

    const R = Math.min(W, H) * 0.38 * (1 + 0.045 * Math.sin(t * 1.6));
    vctx.globalCompositeOperation = 'destination-out';
    let g = vctx.createRadialGradient(light.x, light.y, 0, light.x, light.y, R);
    g.addColorStop(0, 'rgba(0,0,0,1)');
    g.addColorStop(0.55, 'rgba(0,0,0,0.82)');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    vctx.fillStyle = g;
    vctx.fillRect(light.x - R, light.y - R, R * 2, R * 2);

    vctx.globalCompositeOperation = 'lighter';
    g = vctx.createRadialGradient(light.x, light.y, 0, light.x, light.y, R * 0.8);
    g.addColorStop(0, 'rgba(255,232,190,0.05)');
    g.addColorStop(1, 'rgba(255,232,190,0)');
    vctx.fillStyle = g;
    vctx.fillRect(light.x - R, light.y - R, R * 2, R * 2);
    vctx.globalCompositeOperation = 'source-over';
  }

  let heroOnScreen = true;
  new IntersectionObserver(entries => {
    heroOnScreen = entries[0].isIntersecting;
  }).observe(hero);

  let lastT = 0;
  function frame(ms) {
    if (!heroOnScreen) {           // skip work while the hero is scrolled away
      lastT = ms;
      requestAnimationFrame(frame);
      return;
    }
    const dt = Math.min(50, ms - lastT || 16);
    lastT = ms;
    const t = ms / 1000;
    const now = ms;

    // light target: cursor, or a slow drift when idle
    let tx, ty;
    if (mouse.seen && now - mouse.lastMove < 3500) {
      tx = mouse.x; ty = mouse.y;
    } else {
      tx = W * 0.5 + Math.sin(t * 0.13) * W * 0.24;
      ty = treeCenter.y + Math.cos(t * 0.09) * H * 0.2;
    }
    const k = mouse.seen && now - mouse.lastMove < 3500 ? 0.16 : 0.03;
    light.x = lerp(light.x, tx, k);
    light.y = lerp(light.y, ty, k);
    cursorEl.style.transform = `translate3d(${light.x}px,${light.y}px,0)`;

    drawScene(t, dt, now);
    drawVeil(t);
    requestAnimationFrame(frame);
  }

  /* ---------------- static fallback ---------------- */

  function renderStatic() {
    ctx.clearRect(0, 0, W, H);
    let prevCol = null;
    for (const p of points) {
      if (p.col !== prevCol) { ctx.fillStyle = p.col; prevCol = p.col; }
      ctx.globalAlpha = p.a;
      ctx.fillRect(p.x, p.y, p.r, p.r);
    }
    ctx.globalAlpha = 1;
    veil.style.display = 'none';
    cursorEl.style.display = 'none';
    for (const card of cards) {
      card.el.style.opacity = 1;
      if (!card.anchor || !card.rect) continue;
      const c = cardCorner(card);
      ctx.strokeStyle = 'rgba(232,228,218,0.3)';
      ctx.beginPath();
      ctx.moveTo(card.anchor.x, card.anchor.y);
      ctx.lineTo(c.x, c.y);
      ctx.stroke();
    }
  }

  /* ---------------- sizing ---------------- */

  function size() {
    const r = hero.getBoundingClientRect();
    W = Math.round(r.width);
    H = Math.round(r.height);
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    for (const c of [scene, veil]) {
      c.width = W * DPR;
      c.height = H * DPR;
    }
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    vctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    light.x = W * 0.5;
    light.y = H * 0.55;
    buildScene();
    buildCards();
    if (reduced) renderStatic();
  }

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(size, 180);
  });

  /* ---------------- film grain tile ---------------- */

  (() => {
    const g = document.createElement('canvas');
    g.width = g.height = 160;
    const gc = g.getContext('2d');
    const img = gc.createImageData(160, 160);
    for (let i = 0; i < img.data.length; i += 4) {
      const v = (Math.random() * 255) | 0;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
      img.data[i + 3] = 255;
    }
    gc.putImageData(img, 0, 0);
    const grain = document.querySelector('.grain');
    if (grain) grain.style.backgroundImage = `url(${g.toDataURL()})`;
  })();

  /* ---------------- scroll reveals ---------------- */

  const io = new IntersectionObserver(entries => {
    for (const e of entries) if (e.isIntersecting) e.target.classList.add('in');
  }, { threshold: 0.2 });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));

  /* ---------------- go ---------------- */

  size();
  if (!reduced) requestAnimationFrame(frame);
})();
