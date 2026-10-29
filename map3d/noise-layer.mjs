// Departure-noise layers for the Map 2 3D studio (local copy; OEJN noise model, ECAC Doc 29, 1 Oct 2026).
// Graded noise surface (green -> red), contour lines, typical flight paths in 3D (median track and median height of
// departure groups), neighbourhood names, and a legend with the residents in each band.
// Scene frame of Map 2: x = km east of data.origin.utm, z = km south of it, y = height (km x vertical emphasis).
import * as THREE from 'three';

const RAMP = ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#e34a33', '#b30000', '#67000d'];
const RWY = {'34C': '#168d9b', '34L': '#bb4b76', '34R': '#aa7519'};
const METRIC = {
  lden: {label: 'Day–night', title: 'Day–night noise level (Lden)', unit: 'dB', stops: [45, 50, 55, 60, 65, 70, 75], fade: 42,
    bands: ['Noticeable · above WHO guideline (45)', 'Moderate', 'Loud · EU mapping threshold (55)', 'Very loud', 'Severe', 'Extreme · beside the runway']},
  lnight: {label: 'Night', title: 'Night noise level (23:00–07:00)', unit: 'dB', stops: [40, 45, 50, 55, 60, 65, 70], fade: 37,
    bands: ['Above WHO night guideline (40)', 'Sleep disturbance for some', 'EU night threshold (50)', 'High sleep disturbance', 'Severe', 'Extreme']},
  n70: {label: 'Loud events', title: 'Departures above 70 dB', unit: 'events', stops: [1, 5, 10, 20, 50, 100, 150], fade: 0.5, log: true,
    bands: ['Occasional', 'Several a day', 'One every 1–2 hours', 'Frequent', 'Very frequent', 'Almost every departure']},
  live: {label: 'Live ▶', title: 'Live: noise under the moving aircraft', unit: 'dB', stops: [60, 65, 70, 75, 80, 85, 90], fade: 55,
    bands: ['Clearly audible outdoors', 'Conversation harder outdoors', 'Interrupts conversation indoors (windows open)', 'Very loud', 'Severe', 'Extreme']},
};
const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const RGB = RAMP.map(hex);
function colorAt(v, m) {
  const S = m.stops, f = m.log ? Math.log : (x => x);
  if (v < m.fade) return null;
  if (v < S[0]) return [...RGB[0], 0.30 * (f(v) - f(m.fade)) / (f(S[0]) - f(m.fade))];
  let i = S.length - 2; for (let k = 0; k < S.length - 1; k++) if (v < S[k + 1]) { i = k; break; }
  const t = Math.min(1, Math.max(0, (f(v) - f(S[i])) / (f(S[i + 1]) - f(S[i]))));
  const a = RGB[i], b = RGB[Math.min(i + 1, RGB.length - 1)];
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, 0.42 + 0.07 * (i + t)];
}
const fmtK = x => x >= 1e4 ? Math.round(x / 1e3) + 'k' : x >= 1e3 ? (x / 1e3).toFixed(1) + 'k' : String(Math.round(x));

function textSprite(text, sub, color = '#14323d') {
  const c = document.createElement('canvas'), dpr = 2, ctx = c.getContext('2d');
  const f1 = `600 ${13 * dpr}px "Segoe UI",Arial,sans-serif`, f2 = `500 ${12 * dpr}px Tahoma,"Segoe UI",sans-serif`;
  ctx.font = f1; const w1 = ctx.measureText(text).width; ctx.font = f2; const w2 = sub ? ctx.measureText(sub).width : 0;
  c.width = Math.ceil(Math.max(w1, w2) + 16 * dpr); c.height = (sub ? 36 : 21) * dpr;
  const g = c.getContext('2d'); g.lineJoin = 'round'; g.lineWidth = 4 * dpr; g.strokeStyle = 'rgba(255,255,255,.92)';
  g.font = f1; g.strokeText(text, 8 * dpr, 15 * dpr); g.fillStyle = color; g.fillText(text, 8 * dpr, 15 * dpr);
  if (sub) { g.font = f2; g.strokeText(sub, 8 * dpr, 31 * dpr); g.fillStyle = '#4b6470'; g.fillText(sub, 8 * dpr, 31 * dpr); }
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({map: tex, depthTest: false, transparent: true}));
  s.center.set(0, 0.5); s.renderOrder = 20; s.userData.px = [c.width / dpr, c.height / dpr];
  return s;
}

export function mountNoise({scene, data, viewport, camera, vertical, noise}) {
  const N = noise, o = data.origin.utm, dx = (N.arp_utm[0] - o[0]) / 1000, dy = (N.arp_utm[1] - o[1]) / 1000;
  const S = (x, y) => [x + dx, -(y + dy)];                        // ARP-km -> scene x, z
  const grids = {};
  for (const k in N.grids) { const s = atob(N.grids[k]), a = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) a[i] = s.charCodeAt(i); grids[k] = a; }
  const root = new THREE.Group(); root.visible = false; scene.add(root);
  // noise surface
  const size = N.n * N.cell_km, [cx, cz] = S(N.x0 - N.cell_km / 2 + size / 2, N.y0 - N.cell_km / 2 + size / 2);
  const mat = new THREE.MeshBasicMaterial({transparent: true, depthWrite: false});
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(size, size), mat);
  plane.rotation.x = -Math.PI / 2; plane.position.set(cx, 0.03, cz); plane.renderOrder = 5; root.add(plane);
  const tex = {};
  function surface(k) {
    if (tex[k]) return tex[k];
    const n = N.n, cv = document.createElement('canvas'); cv.width = n; cv.height = n;
    const c = cv.getContext('2d'), img = c.createImageData(n, n), g = grids[k], m = METRIC[k];
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
      const col = colorAt(g[j * n + i], m), p = ((n - 1 - j) * n + i) * 4;
      if (!col) { img.data[p] = RGB[0][0]; img.data[p + 1] = RGB[0][1]; img.data[p + 2] = RGB[0][2]; img.data[p + 3] = 0; continue; }
      img.data[p] = col[0]; img.data[p + 1] = col[1]; img.data[p + 2] = col[2]; img.data[p + 3] = Math.round(col[3] * 255);
    }
    c.putImageData(img, 0, 0);
    const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearMipmapLinearFilter;
    return (tex[k] = t);
  }
  // contours (one group per metric)
  const contours = {};
  function contourGroup(k) {
    if (contours[k]) return contours[k];
    const grp = new THREE.Group(), m = METRIC[k];
    for (const [lv, lines] of Object.entries(N.contours[k])) {
      const col = RAMP[Math.max(0, m.stops.indexOf(+lv))];
      for (const l of lines) {
        const pts = []; for (let i = 0; i < l.length; i += 2) { const [x, z] = S(l[i], l[i + 1]); pts.push(new THREE.Vector3(x, 0.04, z)); }
        grp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({color: col, transparent: true, opacity: .95})));
      }
    }
    root.add(grp); return (contours[k] = grp);
  }
  // typical paths (3D tubes at the median observed height + dashed ground shadow)
  const paths = new THREE.Group(); root.add(paths);
  const maxN = Math.max(...N.paths.map(p => p.n));
  function buildPaths() {
    for (const c of [...paths.children]) { paths.remove(c); c.geometry?.dispose(); c.material?.map?.dispose(); c.material?.dispose(); }
    const v = vertical();
    for (const p of N.paths) {
      const col = RWY[p.runway] || '#16324a', pts = [], shadow = [];
      p.path.forEach(([x, y], i) => { const [sx, sz] = S(x, y); pts.push(new THREE.Vector3(sx, p.alt_ft[i] * 0.0003048 * v + 0.05, sz)); shadow.push(new THREE.Vector3(sx, 0.045, sz)); });
      const tube = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), Math.max(40, pts.length * 3), 0.035 + 0.11 * p.n / maxN, 8, false),
        new THREE.MeshStandardMaterial({color: col, roughness: .45, metalness: .1, transparent: true, opacity: .92}));
      paths.add(tube);
      const sh = new THREE.Line(new THREE.BufferGeometry().setFromPoints(shadow), new THREE.LineDashedMaterial({color: col, dashSize: .4, gapSize: .25, transparent: true, opacity: .8}));
      sh.computeLineDistances(); paths.add(sh);
      const lab = textSprite(`${p.runway} · ${p.n} departures`, null, col);
      lab.position.copy(pts[Math.min(pts.length - 1, 24)]); lab.position.y += 0.3; paths.add(lab);
    }
  }
  buildPaths();
  document.getElementById('height')?.addEventListener('input', () => setTimeout(buildPaths, 0));
  // names
  const names = new THREE.Group(); root.add(names);
  for (const p of N.places) {
    const s = textSprite(p.city ? 'JEDDAH' : p.en, p.city ? 'جدة' : p.ar);
    const [x, z] = S(p.x, p.y); s.position.set(x, 0.15, z); names.add(s);
  }
  { const s = textSprite('Red Sea', null, '#3f7f9c'), [x, z] = S(-22, -12); s.position.set(x, 0.1, z); names.add(s); }
  // keep label sprites at a constant on-screen size
  const tmp = new THREE.Vector3();
  (function scaleLabels() {
    if (root.visible) {
      const h = viewport.clientHeight || 800;
      root.traverse(ob => { if (!ob.isSprite) return; const d = camera.position.distanceTo(ob.getWorldPosition(tmp)), k = 2 * Math.tan(camera.fov * Math.PI / 360) * d / h; ob.scale.set(ob.userData.px[0] * k, ob.userData.px[1] * k, 1); });
    }
    requestAnimationFrame(scaleLabels);
  })();

  // ---------- live footprint: follows the Map 2 playback aircraft ----------
  // Instantaneous A-weighted level on the ground from the aircraft's current position (NPD LAmax of a typical A320
  // at take-off / climb thrust, Doc 29 lateral attenuation), plus a trail = highest level reached so far this run.
  const L = N.live, n = N.n, cell = N.cell_km;
  const lcv = document.createElement('canvas'); lcv.width = n; lcv.height = n;
  const lctx = lcv.getContext('2d'), limg = lctx.createImageData(n, n), trail = new Float32Array(n * n), now = new Float32Array(n * n);
  const ltex = new THREE.CanvasTexture(lcv); ltex.colorSpace = THREE.SRGBColorSpace; ltex.magFilter = THREE.LinearFilter;
  const lmat = new THREE.MeshBasicMaterial({transparent: true, depthWrite: false, map: ltex});
  const lplane = new THREE.Mesh(plane.geometry, lmat); lplane.rotation.x = -Math.PI / 2; lplane.position.set(cx, 0.032, cz); lplane.renderOrder = 6; lplane.visible = false; root.add(lplane);
  const lx = L.dists_ft.map(Math.log10);
  function npd(P, dft) {
    const d = Math.log10(Math.max(dft, 98.4)), p = Math.max(P, 1), W = L.powers, X = lx;
    let j = X.length - 2; for (let k = 0; k < X.length - 1; k++) if (d < X[k + 1]) { j = k; break; }
    let i = W.length - 2; for (let k = 0; k < W.length - 1; k++) if (p < W[k + 1]) { i = k; break; }
    const at = r => L.lamax[r][j] + (L.lamax[r][j + 1] - L.lamax[r][j]) * (d - X[j]) / (X[j + 1] - X[j]);
    const a = at(i), b = at(i + 1); return a + (b - a) * (p - W[i]) / (W[i + 1] - W[i]);
  }
  function thrust(altFt, casKt) {
    const r = altFt < 1500 ? 'MaxTakeoff' : 'MaxClimb', hi = altFt < 1500 ? 'MaxTkoffHiTemp' : 'MaxClimbHiTemp', T = 30;
    const f = c => c ? c[0] + c[1] * casKt + c[2] * altFt + c[3] * altFt * altFt + c[4] * T : Infinity;
    return Math.min(f(L.jet[r]), f(L.jet[hi]));
  }
  const lateral = (betaDeg, lM) => (lM <= 914 ? 1.089 * (1 - Math.exp(-0.00274 * lM)) : 1) * (betaDeg <= 50 ? 1.137 - 0.0229 * betaDeg + 9.72 * Math.exp(-0.142 * betaDeg) : 0);
  const R = 14, Rc = Math.round(R / cell), Mlive = METRIC.live;
  let boxes = [], lastElapsed = {}, peak = 0;
  const drops = [0, 1, 2].map(() => { const g = new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(6), 3));
    const ln = new THREE.Line(g, new THREE.LineDashedMaterial({color: '#14323d', dashSize: .08, gapSize: .06, transparent: true, opacity: .8})); ln.visible = false; ln.frustumCulled = false; root.add(ln); return ln; });
  function paint(i0, i1, j0, j1) {
    for (let j = Math.max(0, j0); j <= Math.min(n - 1, j1); j++) for (let i = Math.max(0, i0); i <= Math.min(n - 1, i1); i++) {
      const q = j * n + i, p = ((n - 1 - j) * n + i) * 4, cur = colorAt(now[q], Mlive), tr = colorAt(trail[q], Mlive);
      const c = cur || tr; if (!c) { limg.data[p + 3] = 0; continue; }
      limg.data[p] = c[0]; limg.data[p + 1] = c[1]; limg.data[p + 2] = c[2]; limg.data[p + 3] = Math.round((cur ? Math.min(1, c[3] + 0.25) : c[3] * 0.45) * 255);
    }
  }
  function liveStep() {
    if (current === 'live') {
      const st = window.map2?.getState?.() || {}, v = vertical(), newBoxes = [];
      for (const q of boxes) for (let j = q[2]; j <= q[3]; j++) for (let i = q[0]; i <= q[1]; i++) if (i >= 0 && j >= 0 && i < n && j < n) now[j * n + i] = 0;
      peak = 0; let di = 0; drops.forEach(d => d.visible = false);
      for (const [id, a] of Object.entries(st)) {
        if (!a.procedure) continue;
        if ((lastElapsed[id] ?? 0) > a.elapsed + 0.5) trail.fill(0);           // restart or new loop: clear the trail
        lastElapsed[id] = a.elapsed;
        if (!a.elapsed) continue;
        const [sx, sy, sz] = a.position, xa = sx - dx, ya = -sz - dy, alt = Math.max(0, sy / (0.0003048 * v)), P = thrust(alt, alt < 3000 ? 160 : 250);
        const ci = Math.round((xa - N.x0) / cell), cj = Math.round((ya - N.y0) / cell), hkm = alt * 0.0003048;
        if (di < drops.length) { const dl = drops[di++], ar = dl.geometry.attributes.position.array; ar.set([sx, sy, sz, sx, 0.035, sz]); dl.geometry.attributes.position.needsUpdate = true; dl.computeLineDistances(); dl.visible = true; }
        for (let j = cj - Rc; j <= cj + Rc; j++) for (let i = ci - Rc; i <= ci + Rc; i++) {
          if (i < 0 || j < 0 || i >= n || j >= n) continue;
          const gx = N.x0 + i * cell - xa, gy = N.y0 + j * cell - ya, lh = Math.hypot(gx, gy); if (lh > R) continue;
          const d = Math.hypot(lh, hkm), lev = npd(P, d * 3280.84) - lateral(Math.atan2(hkm, Math.max(lh, 1e-3)) * 180 / Math.PI, lh * 1000);
          const q = j * n + i; now[q] = Math.max(now[q], lev); trail[q] = Math.max(trail[q], lev); peak = Math.max(peak, lev);
        }
        newBoxes.push([ci - Rc, ci + Rc, cj - Rc, cj + Rc]);
      }
      for (const q of [...boxes, ...newBoxes]) paint(...q);
      boxes = newBoxes; lctx.putImageData(limg, 0, 0); ltex.needsUpdate = true;
      const out = panel.querySelector('.noise-live'); if (out) out.textContent = newBoxes.length ? `Under the aircraft now: up to ${Math.round(peak)} dB` : 'Press ▶ Play to fly a departure';
    }
    requestAnimationFrame(liveStep);
  }
  requestAnimationFrame(liveStep);

  // ---------- panel ----------
  const panel = document.createElement('div');
  panel.className = 'noise-panel';
  panel.innerHTML = `<div class="noise-head"><small>NOISE · 1 OCT 2026 · LOCAL ONLY</small><button class="noise-more" type="button">Results ↗</button></div>
    <div class="noise-seg" role="group" aria-label="Noise layer">
      <button data-l="off" aria-pressed="true">Off</button>${Object.entries(METRIC).map(([k, m]) => `<button data-l="${k}" aria-pressed="false">${m.label}</button>`).join('')}
    </div>
    <div class="noise-body" hidden>
      <div class="noise-toggles"><label><input type="checkbox" data-t="paths" checked> Paths</label><label><input type="checkbox" data-t="contours" checked> Contours</label><label><input type="checkbox" data-t="names" checked> Names</label></div>
      <b class="noise-title"></b><canvas class="noise-grad" width="230" height="10"></canvas><div class="noise-ticks"></div>
      <b class="noise-live" hidden></b>
      <details><summary>What the colours mean · residents</summary><div class="noise-bands"></div></details>
      <span class="noise-foot">${N.modelled} observed jet departures · ECAC Doc 29 · departures only, one day · Wingbits evaluation data: do not publish</span>
    </div>`;
  viewport.append(panel);
  const dlg = resultsDialog(N);
  panel.querySelector('.noise-more').onclick = () => dlg.showModal();
  const body = panel.querySelector('.noise-body'), show = {paths: true, contours: true, names: true};
  let current = 'off';
  function legend(k) {
    const m = METRIC[k];
    panel.querySelector('.noise-title').textContent = m.title;
    const g = panel.querySelector('.noise-grad').getContext('2d');
    for (let x = 0; x < 230; x++) { const v = m.log ? Math.exp(Math.log(m.stops[0]) + (Math.log(m.stops[5]) - Math.log(m.stops[0])) * x / 229) : m.stops[0] + (m.stops[5] - m.stops[0]) * x / 229; const c = colorAt(v, m); g.fillStyle = `rgb(${c.slice(0, 3).map(Math.round).join(',')})`; g.fillRect(x, 0, 1, 10); }
    panel.querySelector('.noise-ticks').innerHTML = m.stops.slice(0, 6).map(s => `<span>${s}</span>`).join('') + `<span>${m.unit}</span>`;
    const cum = N.pop[k] || [], band = cum.map((v, i) => v - (cum[i + 1] || 0));
    panel.querySelector('.noise-bands').innerHTML = m.bands.map((b, i) => `<div><i style="background:${RAMP[i]}"></i><span>${i === 5 ? '≥ ' + m.stops[i] : m.stops[i] + '–' + m.stops[i + 1]} · ${b}</span><em>${cum.length ? fmtK(band[i]) : ''}</em></div>`).reverse().join('');
    panel.querySelector('details summary').textContent = k === 'live' ? 'What the colours mean' : 'What the colours mean · residents';
    panel.querySelector('.noise-live').hidden = k !== 'live';
    panel.querySelector('.noise-foot').textContent = k === 'live'
      ? `Illustrative: follows Map 2's concept playback on the published procedure (demo heights), using a typical ${L.acft} (${L.npd_id} noise curve) at full take-off / climb thrust. Bright = now, faded = loudest so far.`
      : `${N.modelled} observed jet departures · ECAC Doc 29 · departures only, one day · Wingbits evaluation data: do not publish`;
  }
  function apply() {
    root.visible = current !== 'off'; body.hidden = current === 'off';
    if (current !== 'off') {
      const liveMode = current === 'live';
      plane.visible = !liveMode; lplane.visible = liveMode;
      for (const g of Object.values(contours)) g.visible = false;
      if (!liveMode) { mat.map = surface(current); mat.needsUpdate = true; contourGroup(current).visible = show.contours; }
      paths.visible = show.paths; names.visible = show.names;
      legend(current);
    }
    place();
  }
  panel.querySelectorAll('[data-l]').forEach(b => b.onclick = () => {
    const was = current; current = b.dataset.l; panel.querySelectorAll('[data-l]').forEach(x => x.setAttribute('aria-pressed', x === b));
    const pc = panel.querySelector('[data-t="paths"]');                  // typical-path tubes clutter the live view: off by default there
    if (current === 'live' && was !== 'live') { show.paths = false; pc.checked = false; }
    if (was === 'live' && current !== 'live') { show.paths = true; pc.checked = true; }
    apply();
  });
  panel.querySelectorAll('[data-t]').forEach(c => c.onchange = () => { show[c.dataset.t] = c.checked; apply(); });
  // never overlap the flight card: the panel may only use the space above it (scrolls inside if needed)
  function place() {
    const card = viewport.querySelector('.flight-card'), pr = panel.getBoundingClientRect(), vr = viewport.getBoundingClientRect();
    const limit = (card ? card.getBoundingClientRect().top : vr.bottom) - pr.top - 10;
    panel.style.maxHeight = Math.max(110, limit) + 'px';
  }
  new ResizeObserver(place).observe(viewport); panel.querySelector('details').addEventListener('toggle', place);
  return {set: l => panel.querySelector(`[data-l="${l}"]`)?.click(), root};
}


// ---------- results dialog: the headline findings, how they were calculated, and the limits ----------
function resultsDialog(N) {
  const R = N.stats, c = R.coverage, k = R.kpi, d = document.createElement('dialog');
  d.className = 'noise-dialog';
  const bar = (v, max, col, label) => { const f = 100 * v / max;
    return `<div class="nd-bar"><span style="width:${f.toFixed(1)}%;background:${col}"></span><em class="${f > 55 ? 'in' : ''}" style="${f > 55 ? '' : `left:calc(${f.toFixed(1)}% + 6px)`}">${label}</em></div>`; };
  const cum = (arr, i) => arr[i] - (arr[i + 1] || 0);
  const ldenRows = [45, 50, 55, 60, 65, 70].map((t, i) => [t, cum(N.pop.lden, i)]), nightRows = [40, 45, 50, 55, 60, 65].map((t, i) => [t, cum(N.pop.lnight, i)]);
  const maxBand = Math.max(...ldenRows.map(r => r[1]), ...nightRows.map(r => r[1]));
  const band = (rows) => rows.map(([t, v], i) => `<div class="nd-row"><i style="background:${RAMP[i]}"></i><span>${i === 5 ? '≥ ' + t : t + '–' + (t + 5)} dB</span>${bar(v, maxBand, RAMP[i], fmtK(v))}</div>`).reverse().join('');
  const sMax = Math.max(...R.same_type.flatMap(x => [x['34C_l65'], x['34L_l65']]));
  const same = R.same_type.map(x => `<div class="nd-pair"><b>${x.type}</b>${bar(x['34C_l65'], sMax, RWY['34C'], `34C · ${fmtK(x['34C_l65'])} (n=${x['34C_n']})`)}${bar(x['34L_l65'], sMax, RWY['34L'], `34L · ${fmtK(x['34L_l65'])} (n=${x['34L_n']})`)}</div>`).join('');
  const T = R.types.filter(t => t.n >= 2), tMax = Math.max(...T.map(t => t.l70));
  const types = T.map(t => `<div class="nd-row nd-type"><b>${t.type}</b>${bar(t.l70, tMax, t.pending ? '#fdae61' : t.cls === 'widebody' ? '#b30000' : '#fc8d59', `${fmtK(t.l70)} · n=${t.n}${t.pending ? ' · proxy, Δ pending' : ''}`)}</div>`).join('');
  const a320 = R.types.find(t => t.type === 'A320'), neo = R.types.find(t => t.type === 'A20N');
  d.innerHTML = `<button class="nd-close" aria-label="Close">×</button>
  <small>DEPARTURE NOISE · JEDDAH OEJN · 1 OCTOBER 2026</small>
  <h2>Who heard Jeddah's departures</h2>
  <div class="nd-kpis">
    <div><b>${c.modelled}</b><span>departures modelled, of ${c.in_scope} observed</span></div>
    <div><b>${fmtK(k.lden55)}</b><span>people above 55 dB day–night (EU mapping threshold)</span></div>
    <div><b>${fmtK(k.lnight50)}</b><span>people above 50 dB at night</span></div>
    <div><b>${fmtK(k.n70_10)}</b><span>people who heard 10+ departures above 70 dB</span></div>
  </div>
  <h3>How many people, how loud</h3>
  <div class="nd-two"><div><p class="nd-cap">Day–night level (Lden)</p>${band(ldenRows)}</div><div><p class="nd-cap">Night level (23:00–07:00)</p>${band(nightRows)}</div></div>
  <p>WHO recommends aircraft noise below 45 dB Lden and 40 dB at night. Applying the WHO 2018 exposure–response curves to this single day gives about <b>${fmtK(R.who.ha)}</b> people highly annoyed and <b>${fmtK(R.who.hsd)}</b> highly sleep-disturbed. This is indicative only: those curves describe long-term exposure to all flights.</p>
  <h3>Same aircraft, two runways</h3>
  <p>Median residents reached by 65 dB or more per departure. For the same aircraft the two runways are close. Runway 34C dominates the day because it carries ${c.by_runway['34C']} of the ${c.modelled} departures and almost all large jets: alone it puts ${fmtK(R.rwy_alone['34C'][55])} people above 55 dB, against ${fmtK(R.rwy_alone['34L'][55])} for 34L.</p>
  <div class="nd-pairs">${same}</div>
  <h3>The aircraft matters most</h3>
  <p>Average residents reached by 70 dB or more per departure. An A320neo reached about ${fmtK(neo.l70)} people, against ${fmtK(a320.l70)} for the older A320.</p>
  <div class="nd-types">${types}</div>
  <h3>How it was calculated</h3>
  <ul>
    <li><b>Method:</b> ECAC Doc 29, 5th edition (2026), the European standard for airport noise contours. Every observed departure is split into segments; each segment's noise at each point uses the aircraft's noise–power–distance curves (EASA ANP 2.3) with corrections for speed, engine position, ground attenuation, segment length and start of roll.</li>
    <li><b>Flights:</b> real tracks from the A2 reconstruction (Wingbits ADS-B), with take-off point, height and speed from the data; engine thrust from the Doc 29 performance equations; weather (temperature, humidity, pressure) from the OEJN METAR at take-off.</li>
    <li><b>Aircraft:</b> type from the OpenSky aircraft database; noise data substituted with the EASA tables where the exact type is not in ANP.</li>
    <li><b>People:</b> WorldPop 2026 residents per 100 m cell (3.8 million inside the 80 × 80 km map); each cell takes the noise level at its location.</li>
    <li><b>Checked:</b> the model reproduces all official Doc 29 test cases: ${R.validation.b2_rows.toLocaleString()} segments within ${R.validation.b2_max_db} dB, events within ${R.validation.b1_max_db} dB, all ${R.validation.d2_points} thrust points, and an observed-track test within ${R.validation.e2e_max_db} dB.</li>
  </ul>
  <h3>Read with care</h3>
  <ul>
    <li>Departures only, one day: no arrivals or ground noise; not annual noise contours.</li>
    <li>Not modelled: ${c.no_type} departures without a known aircraft type, ${c.unmapped} helicopters or light aircraft, and ${c.path_failed} whose take-off was not recorded near the runway.</li>
    <li>Full take-off power and the noisier engine option are assumed where unknown, so levels near the runway are an upper estimate. ${c.proxy} departures (B78X, A339) use substitute noise data without a correction yet.</li>
    <li>Flight paths on the map are typical (median) tracks of groups of departures, never individual flights. Wingbits data are for evaluation only: keep this map local.</li>
  </ul>
  <p class="nd-foot">Release ${R.release}. Full tables: docs/noise/results_2026-10-01.md and data/noise/processed in the oejn-noise-population repository.</p>`;
  document.body.append(d);
  d.querySelector('.nd-close').onclick = () => d.close();
  d.addEventListener('click', e => { if (e.target === d) d.close(); });
  return d;
}
