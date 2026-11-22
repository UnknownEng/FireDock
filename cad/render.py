"""Render PNG previews of the drone and dock with matplotlib (no CAD program needed).
Run:  .venv\\Scripts\\python cad\\render.py
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

OUT = build.OUT / "renders"
OUT.mkdir(parents=True, exist_ok=True)
LIGHT = np.array([0.4, -0.5, 0.8]) / np.linalg.norm([0.4, -0.5, 0.8])
build.C["carbon"] = (0.33, 0.34, 0.38)  # lighter than real carbon so details read on screen


def tris(items, extra=None, tol=0.4, skip=()):
    polys, cols = [], []
    for name, shp, loc, col, ref in items:
        if any(name.startswith(s) for s in skip):
            continue
        l = extra * loc if extra is not None else loc
        verts, faces = shp.moved(l).tessellate(tol, 0.3)
        v = np.array([[p.x, p.y, p.z] for p in verts])
        alpha = 0.22 if name.startswith("REF_prop") else 0.30 if name == "dockCOVER_R" or name == "dockCOVER_L" else 1.0
        for f in faces:
            t = v[list(f)]
            n = np.cross(t[1] - t[0], t[2] - t[0])
            nn = np.linalg.norm(n)
            shade = 0.45 + 0.55 * abs(n @ LIGHT / nn) if nn > 0 else 0.7
            polys.append(t)
            cols.append((*np.clip(np.array(col) * shade + 0.04, 0, 1), alpha))
    return polys, cols


def draw(polys, cols, path, elev, azim, title):
    fig = plt.figure(figsize=(10, 8), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    pc = Poly3DCollection(polys, facecolors=cols, edgecolors="none", linewidths=0)
    ax.add_collection3d(pc)
    allp = np.concatenate(polys)
    mn, mx = allp.min(0), allp.max(0)
    c, r = (mn + mx) / 2, (mx - mn).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1), zoom=1.45)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title, fontsize=13)
    fig.tight_layout()
    fig.savefig(path, facecolor="white", bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    print("wrote", path)


if __name__ == "__main__":
    S = build.build_shapes()
    drone = build.drone_items(S)
    frame = build.drone_items(S, with_refs=False)
    dloc = build.drone_in_dock_location()

    for old in OUT.glob("*.png"):
        old.unlink()
    p, c = tris(frame, tol=0.2)
    draw(p, c, OUT / "frame_iso.png", 28, -60, "3D-printed PA-CF frame - 14 mm arms, 320 mm wheelbase")
    draw(p, c, OUT / "frame_top.png", 90, -90, "Frame - top view")
    no_props = [i for i in drone if not i[0].startswith("REF_prop")]
    p, c = tris(no_props, tol=0.3)
    draw(p, c, OUT / "drone_full_iso.png", 22, -50,
         "Full drone: Pi 5 + GPS mast on top, FC/ESC/VTX/RX/radio inside, battery + down-cam below")
    draw(p, c, OUT / "drone_full_side.png", 0, -90, "Side view (front is right): charging contacts under the feet")
    draw(p, c, OUT / "drone_full_rear.png", 18, -150, "Rear: antenna mount, telemetry radio, charge module, GPS mast")
    p, c = tris(drone, tol=0.3)
    draw(p, c, OUT / "drone_with_props.png", 25, -55, "Full drone with 7-inch prop discs")
    on_deck = [(n, s, dloc * l, col, r) for n, s, l, col, r in drone]
    hover = build.L(build.V(0, 0, 450)) * dloc
    flying = [(n, s, hover * l, col, r) for n, s, l, col, r in drone]
    p, c = tris(build.dock_items(S, "closed") + on_deck, tol=0.8, skip=("dockREF_elec",))
    draw(p, c, OUT / "dock_closed.png", 22, -55, "Dock closed: drone centred and charging under the covers")
    p, c = tris(build.dock_items(S, "open") + flying, tol=0.8)
    draw(p, c, OUT / "dock_open.png", 30, -60, "Dock open: covers flipped down, pushers parked, drone taking off")
    p, c = tris(build.dock_items(S, "centering") + on_deck, tol=0.8, skip=("dockCOVER",))
    draw(p, c, OUT / "dock_centering.png", 62, -60, "After landing: X and Y pushers slide the legs onto the charge pads")
    draw(p, c, OUT / "dock_centering_top.png", 90, -90, "Top view: pushers centred, feet on the 4 contact pads")
    p, c = tris(build.dock_items(S, "open"), tol=0.8, skip=("dockCOVER",))
    draw(p, c, OUT / "dock_mechanism.png", 35, -35, "Deck mechanism: MGN12 rails, GT2 belts, 4 NEMA17, pushers parked")
