"""Local 3D noise map: a copy of the team's Map 2 (Departure Studio) with the departure-noise ground layer.

    PYTHONPATH=src python scripts/build_map3d.py  <path to Research-and-Innovation-department-SANS-project-main>

The team repository is only read. Its Map 2 files are copied unchanged into map3d/ (hashes in SOURCE.json);
two files get a minimal, asserted patch (studio.js: mount the noise layer; index.html: stylesheet + header
label). Writes map3d/noise-layer.json (500 m grid) and the double-click file map3d/OEJN_Map3D_Noise.html.
Local use only: the noise layer is derived from Wingbits evaluation data and must not be published.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from viz.noise_grid import grid500  # noqa: E402

OUT = ROOT / "map3d"
COPY = ["index.html", "studio.js", "studio.css", "flight-model.mjs", "observed-model.mjs", "observed-layer.mjs", "observed.css",
        "data.json", "sans-logo.svg", "sans-logo-light.svg", "vendor/three.core.js", "vendor/three.module.js",
        "vendor/OrbitControls.js", "vendor/LICENSE.txt"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def copy_map2(src_repo: Path) -> dict:
    src = src_repo / "map-2"
    if not (src / "studio.js").exists():
        raise SystemExit(f"Map 2 not found under {src}")
    hashes = {}
    for name in COPY:
        (OUT / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / name, OUT / name)
        hashes[f"map-2/{name}"] = sha(src / name)
    return hashes


def patch():
    s = (OUT / "studio.js").read_text(encoding="utf-8")
    a = "import {mountObserved} from './observed-layer.mjs';"
    assert a in s, "Map 2 imports changed; update build_map3d.py"
    s = s.replace(a, a + "\nimport {mountNoise} from './noise-layer.mjs';", 1)
    b = "$('loading').style.display='none';ready=true;"
    assert s.count(b) == 1, "Map 2 init changed; update build_map3d.py"
    s = s.replace(b, b + "try{const nr=await fetch('./noise-layer.json');if(nr.ok)window.map2noise=mountNoise({scene,data,viewport,noise:await nr.json()})}catch(err){console.warn('noise layer',err)}", 1)
    (OUT / "studio.js").write_text(s, encoding="utf-8")
    h = (OUT / "index.html").read_text(encoding="utf-8")
    c = '<link rel="stylesheet" href="observed.css">'
    assert c in h
    h = h.replace(c, c + '<link rel="stylesheet" href="noise-layer.css">', 1)
    h = h.replace("<title>OEJN — Departure Studio</title>", "<title>OEJN — Departure Studio + Noise (local)</title>", 1)
    h = h.replace('<span class="pill">MAP 02 · 3D EXPLORER</span>', '<span class="pill">MAP 02 · 3D + NOISE · LOCAL COPY</span>', 1)
    d = "Fuel, noise and capacity models are not connected."
    assert d in h
    h = h.replace(d, "In this local copy the Noise panel shows the departure-noise results of 1 Oct 2026 (OEJN noise model, ECAC Doc 29, observed departures; aggregates only, local use). Fuel and capacity models are not connected.", 1)
    (OUT / "index.html").write_text(h, encoding="utf-8")


def noise_json() -> dict:
    s, meta = grid500(ROOT, step=1)
    s = s.sort_values(["y_utm37n_m", "x_utm37n_m"])            # row-major, south -> north, west -> east
    fr = json.loads((ROOT / "data" / "noise" / "validation" / "noise_manifest.json").read_text())
    out = {"release": meta["release"], "n": meta["n"], "cell_m": meta["cell_m"], "x0": meta["x0"], "y0": meta["y0"],
           "crs": "EPSG:32637", "modelled": fr["flights_modelled"],
           "lden": [int(round(v)) if v == v else 0 for v in s.Lden], "n70": [int(v) for v in s.N70], "dens": [int(v) for v in s.dens],
           "note": "Departures only, 1 Oct 2026. Derived from Wingbits evaluation data via A2: local use only."}
    (OUT / "noise-layer.json").write_text(json.dumps(out, separators=(",", ":")))
    return out


def standalone():
    """Same approach as the team's tools/build_map2_offline.py, plus the noise module and data."""
    read = lambda n: (OUT / n).read_text(encoding="utf-8")
    url = lambda t, m="text/javascript": f"data:{m};base64," + base64.b64encode(t.encode("utf-8")).decode("ascii")
    mods = {"three-core": read("vendor/three.core.js"),
            "three": read("vendor/three.module.js").replace("'./three.core.js'", "'three-core'"),
            "orbit-controls": read("vendor/OrbitControls.js"), "flight-model": read("flight-model.mjs"),
            "observed-model": read("observed-model.mjs"),
            "observed-layer": read("observed-layer.mjs").replace("'./observed-model.mjs'", "'observed-model'"),
            "noise-layer": read("noise-layer.mjs")}
    html = read("index.html")
    for css in ("observed.css", "noise-layer.css"):
        html = html.replace(f'<link rel="stylesheet" href="{css}">', "<style>" + read(css) + "</style>")
    html = re.sub(r'<link rel="stylesheet" href="studio\.css[^"]*">', lambda _: "<style>" + read("studio.css") + "</style>", html)
    html = re.sub(r'<script type="importmap">.*?</script>',
                  lambda _: '<script type="importmap">' + json.dumps({"imports": {k: url(v) for k, v in mods.items()}}) + "</script>", html)
    html = html.replace('src="sans-logo-light.svg"', 'src="' + url(read("sans-logo-light.svg"), "image/svg+xml") + '"')
    st = (read("studio.js").replace("'./vendor/OrbitControls.js'", "'orbit-controls'").replace("'./flight-model.mjs'", "'flight-model'")
          .replace("'./observed-layer.mjs'", "'observed-layer'").replace("'./noise-layer.mjs'", "'noise-layer'"))
    old = "const response=await fetch('./data.json');if(!response.ok)throw new Error('Map dataset could not be loaded');data=await response.json();"
    assert old in st
    st = st.replace(old, "data=JSON.parse(document.getElementById('embedded-map-data').textContent);")
    oldn = "const nr=await fetch('./noise-layer.json');if(nr.ok)window.map2noise=mountNoise({scene,data,viewport,noise:await nr.json()})"
    assert oldn in st
    st = st.replace(oldn, "window.map2noise=mountNoise({scene,data,viewport,noise:JSON.parse(document.getElementById('embedded-noise-data').textContent)})")
    emb = lambda i, t: f'<script type="application/json" id="{i}">' + t.replace("<", "\\u003c") + "</script>"
    scripts = (emb("embedded-map-data", json.dumps(json.loads(read("data.json")), separators=(",", ":")))
               + emb("embedded-noise-data", read("noise-layer.json"))
               + '<script type="module">' + st.replace("</script", "<\\/script") + "</script>")
    html = re.sub(r'<script type="module" src="studio\.js[^"]*"></script>', lambda _: scripts, html)
    assert '<script type="module" src=' not in html and "fetch('./data.json')" not in html
    (OUT / "OEJN_Map3D_Noise.html").write_text(html, encoding="utf-8")
    return OUT / "OEJN_Map3D_Noise.html"


def main(src_repo: str):
    OUT.mkdir(exist_ok=True)
    hashes = copy_map2(Path(src_repo))
    patch()
    nj = noise_json()
    p = standalone()
    (OUT / "SOURCE.json").write_text(json.dumps({
        "copied_from": "M-AlGhazali/Research-and-Innovation-department-SANS-project, map-2 (read only; not modified)",
        "files_sha256": hashes, "patched": ["studio.js (noise-layer mount, 2 lines)", "index.html (stylesheet link, title, header pill, one sentence in Sources)"],
        "added": ["noise-layer.mjs", "noise-layer.css", "noise-layer.json", "OEJN_Map3D_Noise.html"],
        "noise_release": nj["release"]}, indent=2))
    print(f"map3d ready: {p} ({p.stat().st_size / 1e6:.1f} MB); grid {nj['n']}x{nj['n']} @ {nj['cell_m']:.0f} m")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT.parent / "Research-and-Innovation-department-SANS-project-main"))
