// Departure-noise ground overlay for the Map 2 3D studio (local copy, OEJN noise model, 1 Oct 2026).
// Layers: Lden, N70 (departures with LAmax >= 70 dB) and flown-departure density, drawn as a translucent
// texture on the ground plane. Scene frame of Map 2: x = km east of data.origin.utm, z = km south of it.
import * as THREE from 'three';

const LAYERS = {
  lden: {key: 'lden', steps: [45, 50, 55, 60, 65, 70], unit: 'dB', title: 'Day–night level (Lden)',
         colors: ['#efe3fa', '#d2b0ee', '#ad74da', '#8a45c4', '#64209e', '#3d0d66']},
  n70: {key: 'n70', steps: [1, 5, 10, 20, 50, 100], unit: 'departures', title: 'Loud events (LAmax ≥ 70 dB)',
        colors: ['#efe3fa', '#d2b0ee', '#ad74da', '#8a45c4', '#64209e', '#3d0d66']},
  dens: {key: 'dens', steps: [1, 5, 10, 25, 50, 100], unit: 'departures per 250 m cell', title: 'Where the departures flew',
         colors: ['#cdeef1', '#9bdbe1', '#5fc0c9', '#2b9ea9', '#13808b', '#0a5c64']},
};

function texture(N, layer) {
  const L = LAYERS[layer], n = N.n, cv = document.createElement('canvas');
  cv.width = n; cv.height = n;
  const ctx = cv.getContext('2d'), img = ctx.createImageData(n, n), vals = N[L.key];
  const rgb = L.colors.map(h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)));
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
    const v = vals[j * n + i];                       // row j = northing index (south -> north)
    let k = -1; L.steps.forEach((t, s) => { if (v >= t) k = s; });
    const p = ((n - 1 - j) * n + i) * 4;              // canvas row 0 = north
    if (k < 0) { img.data[p] = rgb[0][0]; img.data[p + 1] = rgb[0][1]; img.data[p + 2] = rgb[0][2]; img.data[p + 3] = 0; continue; }  // no dark fringe when filtered
    img.data[p] = rgb[k][0]; img.data[p + 1] = rgb[k][1]; img.data[p + 2] = rgb[k][2]; img.data[p + 3] = 150 + k * 18;
  }
  ctx.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(cv);
  t.magFilter = THREE.LinearFilter; t.minFilter = THREE.LinearFilter; t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function mountNoise({scene, data, viewport, noise}) {
  const N = noise, o = data.origin.utm, size = N.n * N.cell_m / 1000;
  const cx = (N.x0 - N.cell_m / 2) / 1000 + size / 2 - o[0] / 1000;
  const cz = -((N.y0 - N.cell_m / 2) / 1000 + size / 2 - o[1] / 1000);
  const mat = new THREE.MeshBasicMaterial({transparent: true, depthWrite: false, opacity: 0.85});
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(size, size), mat);
  plane.rotation.x = -Math.PI / 2; plane.position.set(cx, 0.03, cz); plane.renderOrder = 5; plane.visible = false;
  scene.add(plane);
  const cache = {};

  const panel = document.createElement('div');
  panel.className = 'noise-panel';
  panel.innerHTML = `<small>NOISE · 1 OCT 2026 · LOCAL ONLY</small>
    <div class="noise-seg" role="group" aria-label="Noise layer">
      <button data-l="off" aria-pressed="true">Off</button><button data-l="lden" aria-pressed="false">Lden</button><button data-l="n70" aria-pressed="false">N70</button><button data-l="dens" aria-pressed="false">Flown</button>
    </div><div class="noise-legend" hidden></div>`;
  viewport.append(panel);
  const legend = panel.querySelector('.noise-legend');
  function set(l) {
    panel.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.l === l));
    if (l === 'off') { plane.visible = false; legend.hidden = true; return; }
    mat.map = cache[l] ??= texture(N, l); mat.needsUpdate = true; plane.visible = true;
    const L = LAYERS[l];
    legend.hidden = false;
    legend.innerHTML = `<b>${L.title}</b><div class="noise-sw">${L.colors.map(c => `<span style="background:${c}"></span>`).join('')}</div>
      <div class="noise-ticks">${L.steps.map(s => `<span>${s}</span>`).join('')}</div>
      <span>${L.unit} · ${N.modelled} observed jet departures · ECAC Doc 29</span>
      <span>Departures only, one day · Wingbits evaluation data: do not publish</span>`;
  }
  panel.querySelectorAll('button').forEach(b => b.onclick = () => set(b.dataset.l));
  return {set, plane};
}
