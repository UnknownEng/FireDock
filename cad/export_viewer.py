"""
Export the drone + dock as separate GLB models for the 3D viewer / animation (output/viewer/models/):
dock body (static), the two covers (rotate on their hinges), the four pusher bars with their brackets and
carriages (slide), the drone body and a 3-blade 7-inch prop (spins). Also writes viewer_config.json with the
hinge axes, pusher positions, motor positions and heights the animation needs.

Run:  .venv\\Scripts\\python cad\\export_viewer.py
"""
import json
import math
import sys
from pathlib import Path

import cadquery as cq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

DK = build.DK
OUT = build.OUT / "viewer" / "models"
OUT.mkdir(parents=True, exist_ok=True)


def make_prop():
    """7-inch tri-blade prop: hub + three pitched, tapered blades (visual model)."""
    r = build.P["prop_d"] / 2
    hub = cq.Workplane("XY").circle(6.5).extrude(7.0).translate((0, 0, -1.5))
    blade = (cq.Workplane("XY").polyline([(5.5, -6.5), (r * 0.45, -9.0), (r - 2, -4.0), (r, 0.0), (r - 2, 3.5),
                                          (r * 0.45, 7.5), (5.5, 6.5)]).close().extrude(1.4)
             .edges("|Z").fillet(0.6))
    blade = blade.rotate((0, 0, 0.7), (1, 0, 0.7), 16)          # pitch
    prop = hub
    for k in range(3):
        prop = prop.union(blade.rotate((0, 0, 0), (0, 0, 1), 120 * k))
    return prop


def export(name, items, tol=0.2):
    a = cq.Assembly(name=name)
    for n, shp, loc, col, _ in items:
        a.add(shp, name=n, loc=loc, color=cq.Color(*col))
    path = OUT / f"{name}.glb"
    a.export(str(path), exportType="GLTF", tolerance=tol, angularTolerance=0.25)
    print(f"{path.name}: {len(items)} parts, {path.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    S = build.build_shapes()
    dock_all = DK.items(S, 0.0, 0.0, 0.0)                         # covers closed, pushers at x/y = 0 (reference)
    moving = ("dockCOVER", "dock_bar_", "dockREF_carriage", "dockREF_elec")
    export("dock_body", [i for i in dock_all if not i[0].startswith(moving)], tol=0.3)
    for tag in ("R", "L"):
        export(f"cover_{tag}", [i for i in dock_all if i[0].startswith("dockCOVER") and
                                (i[0] == f"dockCOVER_{tag}" or f"_{tag}" in i[0][9:])], tol=0.4)
    for axis in ("x", "y"):
        for s in ("+1", "-1"):
            grp = [i for i in dock_all if (i[0] == f"dock_bar_{axis}{s}") or
                   (i[0].startswith(("dock_bar_bracket", "dockREF_carriage")) and f"_{axis}{s}" in i[0])]
            export(f"pusher_{axis}{'p' if s == '+1' else 'n'}", grp, tol=0.2)
    drone = [i for i in build.drone_items(S) if not i[0].startswith("REF_prop")]
    export("drone", drone, tol=0.12)
    export("prop", [("prop_blades", make_prop().val(), cq.Location(cq.Vector(0, 0, 0)), (0.12, 0.12, 0.13), True)],
           tol=0.1)

    motors = [list(build.polar(build.R, a)) for a in build.ARM_ANGLES]
    cfg = {
        "units": "mm, CAD axes: X forward, Y left, Z up (the GLB files are already turned to Y-up)",
        "z_deck": DK.Z_DECK, "drone_on_deck_z": DK.Z_DECK - build.LEG_BOTTOM,
        "hinge_x": DK.XH, "hinge_z": DK.ZH,
        "pusher_park": DK.D["park"], "pusher_x_centred": build.BAR_X_CENTRED, "pusher_y_centred": build.BAR_Y_CENTRED,
        "motors_xy": motors, "prop_z": build.Z_MID + build.P["motor_h"] + 1.5,
        "foot_xy": DK.D["foot_xy"], "half": DK.H, "body_h": DK.D["body_h"],
        "capture_mm": round(DK.D["park"] - DK.D["bar"] / 2 - build.leg_radius_above_deck(25.0) - DK.D["foot_xy"], 1),
    }
    (OUT.parent / "viewer_config.json").write_text(json.dumps(cfg, indent=2))
    print("config written")
