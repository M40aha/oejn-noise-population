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

  // ---------- panel ----------
  const panel = document.createElement('div');
  panel.className = 'noise-panel';
  panel.innerHTML = `<small>NOISE · 1 OCT 2026 · LOCAL ONLY</small>
    <div class="noise-seg" role="group" aria-label="Noise layer">
      <button data-l="off" aria-pressed="true">Off</button>${Object.entries(METRIC).map(([k, m]) => `<button data-l="${k}" aria-pressed="false">${m.label}</button>`).join('')}
    </div>
    <div class="noise-body" hidden>
      <div class="noise-toggles"><label><input type="checkbox" data-t="paths" checked> Paths</label><label><input type="checkbox" data-t="contours" checked> Contours</label><label><input type="checkbox" data-t="names" checked> Names</label></div>
      <b class="noise-title"></b><canvas class="noise-grad" width="230" height="10"></canvas><div class="noise-ticks"></div>
      <details><summary>What the colours mean · residents</summary><div class="noise-bands"></div></details>
      <span class="noise-foot">${N.modelled} observed jet departures · ECAC Doc 29 · departures only, one day · Wingbits evaluation data: do not publish</span>
    </div>`;
  viewport.append(panel);
  const body = panel.querySelector('.noise-body'), show = {paths: true, contours: true, names: true};
  let current = 'off';
  function legend(k) {
    const m = METRIC[k];
    panel.querySelector('.noise-title').textContent = m.title;
    const g = panel.querySelector('.noise-grad').getContext('2d');
    for (let x = 0; x < 230; x++) { const v = m.log ? Math.exp(Math.log(m.stops[0]) + (Math.log(m.stops[5]) - Math.log(m.stops[0])) * x / 229) : m.stops[0] + (m.stops[5] - m.stops[0]) * x / 229; const c = colorAt(v, m); g.fillStyle = `rgb(${c.slice(0, 3).map(Math.round).join(',')})`; g.fillRect(x, 0, 1, 10); }
    panel.querySelector('.noise-ticks').innerHTML = m.stops.slice(0, 6).map(s => `<span>${s}</span>`).join('') + `<span>${m.unit}</span>`;
    const cum = N.pop[k], band = cum.map((v, i) => v - (cum[i + 1] || 0));
    panel.querySelector('.noise-bands').innerHTML = m.bands.map((b, i) => `<div><i style="background:${RAMP[i]}"></i><span>${i === 5 ? '≥ ' + m.stops[i] : m.stops[i] + '–' + m.stops[i + 1]} · ${b}</span><em>${fmtK(band[i])}</em></div>`).reverse().join('');
  }
  function apply() {
    root.visible = current !== 'off'; body.hidden = current === 'off';
    if (current !== 'off') {
      mat.map = surface(current); mat.needsUpdate = true;
      for (const g of Object.values(contours)) g.visible = false;
      contourGroup(current).visible = show.contours;
      paths.visible = show.paths; names.visible = show.names;
      legend(current);
    }
    place();
  }
  panel.querySelectorAll('[data-l]').forEach(b => b.onclick = () => { current = b.dataset.l; panel.querySelectorAll('[data-l]').forEach(x => x.setAttribute('aria-pressed', x === b)); apply(); });
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
