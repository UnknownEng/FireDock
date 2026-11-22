"""
3D finite-element stress test of the arm (the part that takes every flight and crash load).

Mesh: gmsh tetrahedra from output/parts/arm.step.  Solver: scikit-fem, quadratic (P2) tetrahedra,
linear elastic, quasi-isotropic carbon.  Load cases match analysis/analysis.py so the two methods can be
compared:
  LC1  full thrust 2.6 kgf, upward, on the motor footprint
  LC2  motor reaction torque 400 N*mm about the motor axis
  LC3  vertical crash: same direction as LC1, scaled to the load that reaches the carbon allowable
  LC4  side hit on the motor (in-plane), scaled the same way
  MODAL  natural frequencies with the motor + prop mass on the pad
Boundary condition: arm clamped top and bottom between the bottom plate and the clamp plate up to the
clamp-plate edge (same idealisation as the beam model).  Peak stresses are read outside a 3 mm band next to
that idealised clamp edge, where a perfectly rigid clamp creates an artificial stress singularity.

Run:  .venv\\Scripts\\python analysis\\fea.py      (writes output/fea/)
"""
import json
import math
import sys
import time
from pathlib import Path

import gmsh
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import meshio  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import cm, colors  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402
import pypardiso  # noqa: E402
from scipy.sparse.linalg import LinearOperator, eigsh  # noqa: E402
from skfem import (Basis, BilinearForm, ElementTetP1, ElementTetP2, ElementVector, FacetBasis,  # noqa: E402
                   Functional, LinearForm, MeshTet, asm)
from skfem.helpers import dot, sym_grad  # noqa: E402
from skfem.models.elasticity import lame_parameters, linear_elasticity, linear_stress  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REP = ROOT / "output" / "report"
OUT = ROOT / "output" / "fea"
OUT.mkdir(parents=True, exist_ok=True)

data = json.loads((REP / "checks.json").read_text())
ana = json.loads((REP / "analysis.json").read_text())
G, P = data["geometry"], data["params"]
R, CLAMP, T = G["R_motor_mm"], G["clamp_edge_mm"], G["arm_t_mm"]
BASE_R = P["motor_d"] / 2                      # motor base footprint on the pad

MATERIALS = {   # E MPa, nu, density t/mm^3 (x print fill), design allowable MPa  - same values as analysis.py
    "carbon": (55_000.0, 0.30, 1.55e-9, 450.0, "quasi-isotropic carbon plate"),
    "pa_cf": (4_500.0, 0.35, 1.20e-9 * 0.80, 35.0, "printed PA6-CF (in-plane, 6 walls + 50 % gyroid)"),
}
E, NU, RHO, ALLOW, MAT_NAME = MATERIALS[P.get("material", "carbon")]   # units: N, mm, t, s
g = 9.81
AUW_N = ana["results"]["performance"]["AUW_g"] / 1000 * g
THRUST_N = 2.6 * g
TORQUE_NMM = 400.0
TIP_MASS_T = (60.7 + 11.0) * 1e-6              # motor + prop, tonnes
BAND = 3.0                                     # mm excluded next to the idealised clamp edge
BEAM = ana["results"]


def mesh_arm(h):
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.occ.importShapes(str(ROOT / "output" / "parts" / "arm.step"))
    gmsh.model.occ.synchronize()
    gmsh.option.setNumber("Mesh.MeshSizeMax", h)
    gmsh.option.setNumber("Mesh.MeshSizeMin", h / 4)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 16)
    gmsh.option.setNumber("Mesh.Optimize", 1)
    gmsh.model.mesh.generate(3)
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    types, _, conn = gmsh.model.mesh.getElements(3)
    tet = np.asarray(conn[list(types).index(4)], dtype=np.int64).reshape(-1, 4)
    gmsh.finalize()
    lut = np.zeros(int(tags.max()) + 1, dtype=np.int64)
    lut[tags.astype(np.int64)] = np.arange(len(tags))
    tet = lut[tet]
    used = np.unique(tet)
    remap = -np.ones(len(tags), dtype=np.int64)
    remap[used] = np.arange(len(used))
    pts = xyz.reshape(-1, 3)[used]
    return MeshTet(pts.T.copy(), remap[tet].T.copy())


def von_mises(s):
    return np.sqrt(0.5 * ((s[0, 0] - s[1, 1]) ** 2 + (s[1, 1] - s[2, 2]) ** 2 + (s[2, 2] - s[0, 0]) ** 2)
                   + 3 * (s[0, 1] ** 2 + s[1, 2] ** 2 + s[2, 0] ** 2))


def run(h, full=True):
    t0 = time.time()
    mesh = mesh_arm(h)
    e = ElementVector(ElementTetP2())
    ib = Basis(mesh, e, intorder=3)
    lam, mu = lame_parameters(E, NU)
    K = asm(linear_elasticity(lam, mu), ib)

    on_pad = lambda x: ((x[0] - R) ** 2 + x[1] ** 2) < BASE_R ** 2  # noqa: E731
    fb = FacetBasis(mesh, e, facets=mesh.facets_satisfying(lambda x: (np.abs(x[2]) < 1e-6) & on_pad(x)),
                    intorder=4)
    area = Functional(lambda w: 1.0 + 0 * w.x[0]).assemble(fb)
    J = Functional(lambda w: (w.x[0] - R) ** 2 + w.x[1] ** 2).assemble(fb)

    def traction(fun):
        return asm(LinearForm(lambda v, w: sum(c * v[i] for i, c in enumerate(fun(w.x)))), fb)

    z0 = lambda x: 0 * x[0]  # noqa: E731
    loads = {
        "LC1": traction(lambda x: (z0(x), z0(x), THRUST_N / area + z0(x))),
        "LC2": traction(lambda x: (-TORQUE_NMM / J * x[1], TORQUE_NMM / J * (x[0] - R), z0(x))),
        "LC4_unit": traction(lambda x: (z0(x), 1.0 / area + z0(x), z0(x))),
    }
    D = ib.get_dofs(lambda x: (x[0] <= CLAMP + 1e-6) & ((np.abs(x[2]) < 1e-6) | (np.abs(x[2] - T) < 1e-6))).all()
    I = ib.complement_dofs(D)
    Kii = K[I][:, I].tocsr()
    del K
    # sparse direct solver (Intel MKL PARDISO), factorised once and reused for every load case and the modal solve
    ps = pypardiso.PyPardisoSolver()
    ps.factorize(Kii)

    def solve_ii(b):
        x = ps.solve(Kii, b)
        return x + ps.solve(Kii, b - Kii @ x)                  # one step of iterative refinement

    U = {}
    for k, f in loads.items():
        u = np.zeros(ib.N)
        u[I] = solve_ii(f[I])
        U[k] = u

    C = linear_stress(lam, mu)
    xc = mesh.p[:, mesh.t].mean(axis=1)                         # element centroids
    keep = xc[0] > CLAMP + BAND
    b1 = ib.with_element(ElementTetP1())
    pad_c = np.where(((mesh.p[0] - R) ** 2 + mesh.p[1] ** 2) < 5.0 ** 2)[0]
    res = {"h_mm": h, "nodes": mesh.p.shape[1], "tets": mesh.t.shape[1], "dofs": ib.N}
    fields = {}
    for k, u in U.items():
        s = C(sym_grad(ib.interpolate(u)))
        vm = von_mises(s)                                       # (nelem, nqp)
        vm_el = vm.max(axis=1)
        i_pk = int(np.argmax(np.where(keep, vm_el, -1)))
        disp = u[ib.nodal_dofs]
        res[k] = {"peak_von_mises_MPa": float(vm_el[i_pk]),
                  "peak_at_x_mm": float(xc[0, i_pk]), "peak_at_y_mm": float(xc[1, i_pk]),
                  "peak_at_z_mm": float(xc[2, i_pk]),
                  "motor_centre_disp_mm": [float(disp[j, pad_c].mean()) for j in range(3)],
                  "max_disp_mm": float(np.linalg.norm(disp, axis=0).max())}
        if full:
            fields[k] = (disp, b1.project(vm))
        if k == "LC1":
            # nominal bending stress (sigma_xx, top fibre) just outside the band, for comparison with beam theory
            # same points in beam theory: sigma = M * (z - t/2) / I at each element centroid
            sel = keep & (xc[0] < CLAMP + BAND + 2.0) & (xc[2] > T - 1.5)
            w_ = P["arm_w_root"] - (P["arm_w_root"] - P["arm_w_tip"]) * (xc[0][sel] - P["arm_start"]) / (R - P["arm_start"])
            beam = THRUST_N * (R - xc[0][sel]) * (xc[2][sel] - T / 2) / (w_ * T ** 3 / 12)
            res[k]["sigma_xx_near_clamp_MPa"] = float(np.abs(s[0, 0][sel].mean(axis=1)).mean())
            res[k]["beam_same_points_MPa"] = float(np.abs(beam).mean())
    res["solve_s"] = round(time.time() - t0, 1)
    if not full:
        ps.free_memory(everything=True)
        return res, None

    # modal: motor + prop mass smeared over the motor footprint on the pad
    vpad = Functional(lambda w: on_pad(w.x) * 1.0).assemble(ib)
    rho_add = TIP_MASS_T / vpad

    @BilinearForm
    def mass(u, v, w):
        return (RHO + rho_add * on_pad(w.x)) * dot(u, v)

    Mii = asm(mass, ib)[I][:, I].tocsr()
    n = Kii.shape[0]
    opinv = LinearOperator((n, n), matvec=lambda b: ps.solve(Kii, np.ravel(b)), dtype=float)
    vals, vecs = eigsh(Kii, k=6, M=Mii, sigma=0, which="LM", OPinv=opinv, tol=1e-8)
    ps.free_memory(everything=True)
    order = np.argsort(vals)
    modes = []
    for j in order:
        u = np.zeros(ib.N)
        u[I] = vecs[:, j]
        d = u[ib.nodal_dofs]
        tip = np.where(on_pad(mesh.p))[0]
        uz, uy, ux = (np.abs(d[2, tip]).mean(), np.abs(d[1, tip]).mean(), np.abs(d[0, tip]).mean())
        twist = abs(np.polyfit(mesh.p[1, tip], d[2, tip], 1)[0]) * BASE_R
        kind = ("out-of-plane bending (thrust direction)" if uz >= max(uy, twist, ux) else
                "in-plane bending (yaw direction)" if uy >= max(twist, ux) else
                "torsion (arm twisting)" if twist >= ux else "axial")
        modes.append({"freq_Hz": float(np.sqrt(max(vals[j], 0)) / (2 * math.pi)), "shape": kind})
        fields[f"mode{len(modes)}"] = (d / np.abs(d).max(), None)
    res["modes"] = modes
    res["arm_plus_motor_mass_g"] = float(Functional(lambda w: RHO + rho_add * on_pad(w.x)).assemble(ib) * 1e6)
    return res, (mesh, fields)


# ------------------------------------------------------------------- plots
def surface(mesh):
    return mesh.facets[:, mesh.boundary_facets()].T


def draw_field(ax, mesh, tri, disp, val, scale, norm, cmap, elev, azim):
    p = mesh.p + scale * disp
    polys = p.T[tri]
    fc = cmap(norm(val[tri].mean(axis=1)))
    pc = Poly3DCollection(polys, facecolors=fc, edgecolors="none", linewidths=0)
    ax.add_collection3d(pc)
    frame_axes(ax, elev, azim)


def frame_axes(ax, elev, azim):
    ax.set_xlim(10, 182)
    ax.set_ylim(-30, 30)
    ax.set_zlim(-22, 22)
    ax.set_box_aspect((172, 60, 44), zoom=1.0)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()


def plot_case(mesh, disp, vm, title, path, unit_scale=None):
    tri = surface(mesh)
    vmax = float(np.percentile(vm, 99.9))
    norm = colors.Normalize(0, vmax)
    cmap = matplotlib.colormaps["turbo"]
    scale = unit_scale or 12.0 / max(np.linalg.norm(disp, axis=0).max(), 1e-12)
    fig = plt.figure(figsize=(13, 5.6), dpi=130)
    for i, (el, az, sub) in enumerate(((28, -60, "3D view"), (90, -90, "top view"))):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        draw_field(ax, mesh, tri, disp, vm, scale, norm, cmap, el, az)
        ax.set_title(f"{sub}  (deformation x{scale:.0f})", fontsize=10)
    fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), ax=fig.axes, shrink=0.7,
                 label="von Mises stress [MPa]")
    fig.suptitle(title, fontsize=12)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def plot_modes(mesh, fields, modes, path):
    tri = surface(mesh)
    cmap = matplotlib.colormaps["viridis"]
    fig = plt.figure(figsize=(15, 5), dpi=120)
    for i in range(3):
        d, _ = fields[f"mode{i + 1}"]
        mag = np.linalg.norm(d, axis=0)
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        draw_field(ax, mesh, tri, d, mag, 15.0, colors.Normalize(0, mag.max()), cmap, 20, -70)
        ax.set_title(f"Mode {i + 1}: {modes[i]['freq_Hz']:.0f} Hz\n{modes[i]['shape']}", fontsize=10)
    fig.suptitle("Arm natural frequencies with motor + prop on the pad (shape exaggerated)", fontsize=12)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def plot_mesh(mesh, path, res):
    tri = surface(mesh)
    fig = plt.figure(figsize=(11, 5), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    pc = Poly3DCollection(mesh.p.T[tri], facecolors=(0.75, 0.78, 0.85), edgecolors=(0.2, 0.2, 0.3),
                          linewidths=0.15)
    ax.add_collection3d(pc)
    frame_axes(ax, 35, -60)
    ax.set_title(f"FEA mesh: {res['tets']:,} quadratic tetrahedra, {res['dofs']:,} unknowns", fontsize=11)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def plot_all(mesh, fields, out):
    l1, l2, l4 = out["LC1_full_thrust"], out["LC2_motor_torque"], out["LC4_side_hit_one_arm"]
    plot_mesh(mesh, OUT / "fea_mesh.png", out["mesh"])
    d, vm = fields["LC1"]
    plot_case(mesh, d, vm, f"LC1 full thrust {l1['load_N']} N: peak {l1['peak_von_mises_MPa']} MPa, "
              f"safety factor {l1['safety_factor']}, motor lifts {l1['motor_deflection_mm']:.2f} mm",
              OUT / "fea_LC1_full_thrust.png")
    d, vm = fields["LC4_unit"]
    F4 = l4["tip_force_to_reach_allowable_N"]
    plot_case(mesh, d, vm * F4, f"LC4 side hit: {F4:.0f} N on the motor brings the arm to the {ALLOW:.0f} MPa "
              f"allowable ({l4['equivalent_g_whole_drone']:.0f} g)", OUT / "fea_LC4_side_hit.png")
    d, vm = fields["LC2"]
    plot_case(mesh, d, vm, f"LC2 motor torque {l2['torque_Nmm']:.0f} N*mm: peak {l2['peak_von_mises_MPa']} MPa",
              OUT / "fea_LC2_motor_torque.png")
    plot_modes(mesh, fields, out["modal"]["modes"], OUT / "fea_modes.png")


if __name__ == "__main__" and "--plots" in sys.argv:
    # redraw the pictures from the saved results without solving again
    vt = meshio.read(OUT / "arm_fea_results.vtu")
    mesh = MeshTet(vt.points.T.copy(), vt.cells_dict["tetra"].T.copy())
    fd = {}
    for key, arr in vt.point_data.items():
        if key.startswith("displacement_"):
            k = key[len("displacement_"):]
            fd[k] = (arr.T, vt.point_data.get(f"von_mises_{k}"))
    plot_all(mesh, fd, json.loads((OUT / "fea_results.json").read_text()))
    sys.exit()

if __name__ == "__main__":
    for old in OUT.glob("*"):
        old.unlink()
    study = []
    for h in (6.0, 4.5):
        r, _ = run(h, full=False)
        study.append(r)
        print(f"mesh h={h}: {r['dofs']} dofs, LC1 peak {r['LC1']['peak_von_mises_MPa']:.1f} MPa, "
              f"tip {r['LC1']['motor_centre_disp_mm'][2]:.3f} mm, {r['solve_s']} s", flush=True)
    res, (mesh, fields) = run(3.5)
    study.append({k: res[k] for k in ("h_mm", "nodes", "tets", "dofs", "LC1", "solve_s")})
    print(f"mesh h=3.5: {res['dofs']} dofs, LC1 peak {res['LC1']['peak_von_mises_MPa']:.1f} MPa, "
          f"tip {res['LC1']['motor_centre_disp_mm'][2]:.3f} mm, {res['solve_s']} s", flush=True)

    lc1, lc2, lc4 = res["LC1"], res["LC2"], res["LC4_unit"]
    per_N_out = lc1["peak_von_mises_MPa"] / THRUST_N
    per_N_in = lc4["peak_von_mises_MPa"]
    out = {
        "method": "3D linear-elastic FEA, quadratic tetrahedra (gmsh + scikit-fem)",
        "material": {"E_MPa": E, "nu": NU, "density_kg_m3": RHO * 1e12, "allowable_MPa": ALLOW},
        "boundary": f"clamped top+bottom up to the clamp-plate edge at {CLAMP} mm; peaks read beyond {CLAMP + BAND} mm",
        "mesh": {k: res[k] for k in ("h_mm", "nodes", "tets", "dofs")},
        "mesh_study": [{"h_mm": s["h_mm"], "dofs": s["dofs"], "LC1_peak_MPa": round(s["LC1"]["peak_von_mises_MPa"], 1),
                        "LC1_tip_mm": round(s["LC1"]["motor_centre_disp_mm"][2], 4)} for s in study],
        "LC1_full_thrust": {
            "load_N": round(THRUST_N, 1),
            "peak_von_mises_MPa": round(lc1["peak_von_mises_MPa"], 1),
            "peak_location_mm": [round(lc1[f"peak_at_{a}_mm"], 1) for a in "xyz"],
            "nominal_bending_near_clamp_MPa": round(lc1["sigma_xx_near_clamp_MPa"], 1),
            "beam_theory_at_same_place_MPa": round(lc1["beam_same_points_MPa"], 1),
            "motor_deflection_mm": round(lc1["motor_centre_disp_mm"][2], 3),
            "beam_theory_deflection_mm": BEAM["LC1_full_thrust"]["tip_deflection_mm"],
            "safety_factor": round(ALLOW / lc1["peak_von_mises_MPa"], 1),
            "beam_theory_safety_factor": BEAM["LC1_full_thrust"]["safety_factor"],
        },
        "LC2_motor_torque": {"torque_Nmm": TORQUE_NMM, "peak_von_mises_MPa": round(lc2["peak_von_mises_MPa"], 2),
                             "safety_factor": round(ALLOW / lc2["peak_von_mises_MPa"], 0)},
        "LC3_vertical_crash_one_arm": {
            "tip_force_to_reach_allowable_N": round(ALLOW / per_N_out, 0),
            "equivalent_g_whole_drone": round(ALLOW / per_N_out / AUW_N, 1),
            "beam_theory_g": BEAM["LC3_vertical_crash_one_arm"]["equivalent_g_whole_drone"]},
        "LC4_side_hit_one_arm": {
            "tip_force_to_reach_allowable_N": round(ALLOW / per_N_in, 0),
            "equivalent_g_whole_drone": round(ALLOW / per_N_in / AUW_N, 1),
            "peak_location_mm": [round(lc4[f"peak_at_{a}_mm"], 1) for a in "xyz"],
            "beam_theory_g": BEAM["LC4_side_hit_one_arm"]["equivalent_g_whole_drone"]},
        "modal": {"arm_plus_motor_mass_g": round(res["arm_plus_motor_mass_g"], 1),
                  "modes": [{"freq_Hz": round(m["freq_Hz"], 0), "shape": m["shape"]} for m in res["modes"]],
                  "beam_theory_first_bending_Hz": BEAM["vibration"]["arm_first_bending_Hz"],
                  "prop_hover_Hz": BEAM["vibration"]["prop_rotation_hover_Hz"],
                  "prop_max_Hz": BEAM["vibration"]["prop_rotation_max_Hz"]},
    }
    (OUT / "fea_results.json").write_text(json.dumps(out, indent=2, default=lambda o: o.item()))

    # ParaView file with every result on the mesh
    pdata = {}
    for k, (d, vm) in fields.items():
        pdata[f"displacement_{k}"] = d.T
        if vm is not None:
            pdata[f"von_mises_{k}"] = vm
    meshio.Mesh(mesh.p.T, [("tetra", mesh.t.T)], point_data=pdata).write(OUT / "arm_fea_results.vtu")
    plot_all(mesh, fields, out)

    m = out["modal"]["modes"]
    md = f"""# Arm FEA (3D finite elements)

Generated by `analysis/fea.py`. Mesh: {res['tets']:,} quadratic tetrahedra, {res['dofs']:,} unknowns (gmsh + scikit-fem).
Material: {MAT_NAME}, E = {E/1000:.1f} GPa, nu = {NU}, allowable {ALLOW:.0f} MPa.
Boundary: arm clamped between the bottom plate and the clamp plate up to {CLAMP} mm from the centre. Peak
stresses are read outside the {BAND:.0f} mm band next to that clamp edge, because a perfectly rigid clamp makes
an artificial spike there.

| Case | FEA | Beam theory | Notes |
|---|---|---|---|
| LC1 full thrust {THRUST_N:.1f} N | peak **{lc1['peak_von_mises_MPa']:.1f} MPa**, SF **{ALLOW / lc1['peak_von_mises_MPa']:.1f}** | {BEAM['LC1_full_thrust']['max_stress_MPa']} MPa, SF {BEAM['LC1_full_thrust']['safety_factor']} | peak at x = {lc1['peak_at_x_mm']:.0f} mm{' (edge of the inner landing-leg bolt hole)' if abs(lc1['peak_at_x_mm'] - (P['leg_at'] - P['leg_bolt_off'])) < 4 else ''} |
| LC1 motor deflection | **{lc1['motor_centre_disp_mm'][2]:.3f} mm** | {BEAM['LC1_full_thrust']['tip_deflection_mm']} mm | FEA includes shear and the pad |
| LC1 bending stress, upper layer just outside the clamp | {lc1['sigma_xx_near_clamp_MPa']:.1f} MPa | {out['LC1_full_thrust']['beam_theory_at_same_place_MPa']} MPa | same points, checks the model |
| LC2 motor torque {TORQUE_NMM:.0f} N·mm | peak {lc2['peak_von_mises_MPa']:.2f} MPa, SF {ALLOW / lc2['peak_von_mises_MPa']:.0f} | SF {BEAM['LC2_motor_torque']['safety_factor']:.0f} | |
| LC3 vertical crash on one arm | survives **{out['LC3_vertical_crash_one_arm']['equivalent_g_whole_drone']} g** | {BEAM['LC3_vertical_crash_one_arm']['equivalent_g_whole_drone']} g | includes hole/fillet stress peaks |
| LC4 side hit on motor | survives **{out['LC4_side_hit_one_arm']['equivalent_g_whole_drone']} g** | {BEAM['LC4_side_hit_one_arm']['equivalent_g_whole_drone']} g | |

Mesh study (LC1): """ + ", ".join(f"h = {s['h_mm']} mm → {s['LC1_peak_MPa']} MPa / {s['LC1_tip_mm']} mm"
                                for s in out["mesh_study"]) + f"""

## Natural frequencies (arm + {TIP_MASS_T*1e6:.1f} g motor and prop)
""" + "\n".join(f"* Mode {i+1}: **{x['freq_Hz']:.0f} Hz**, {x['shape']}" for i, x in enumerate(m)) + f"""

Beam theory gave {BEAM['vibration']['arm_first_bending_Hz']:.0f} Hz for the first bending mode. Props spin at about
{BEAM['vibration']['prop_rotation_hover_Hz']:.0f} Hz in hover and up to {BEAM['vibration']['prop_rotation_max_Hz']:.0f} Hz,
so use RPM notch filtering (bidirectional DShot) as noted in the main report.

## Files
* `arm_fea_results.vtu`: mesh with displacement and von Mises stress for every case and the mode shapes
  (open in ParaView)
* `fea_LC1_full_thrust.png`, `fea_LC2_motor_torque.png`, `fea_LC4_side_hit.png`, `fea_modes.png`, `fea_mesh.png`

## Limits
Linear elastic, isotropic stand-in for a woven laminate (no ply-by-ply failure, no delamination), rigid clamp,
bolts not modelled as separate parts. Real crash loads are dynamic; the g values are the static load that
brings the arm to the design allowable.
"""
    (OUT / "fea_report.md").write_text(md, encoding="utf-8")
    print(json.dumps(out, indent=2, default=lambda o: o.item()))
