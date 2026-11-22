"""
Builds FreeCAD files from the project (run with FreeCAD's own command-line Python):

    & "C:\\Program Files\\FreeCAD 1.1\\bin\\freecadcmd.exe" freecad\\make_freecad_files.py

  output/freecad/arm_FEA_FreeCAD.FCStd   FEM study of the printed arm (FreeCAD FEM workbench + CalculiX),
                                         already solved: open it, double-click the result to see the stress
  output/freecad/drone_full.FCStd        the complete drone
  output/freecad/dock_closed.FCStd       dock closed with the drone inside
  output/freecad/dock_open.FCStd         dock open (covers down) with the drone
  output/freecad/freecad_fea_results.json

The arm FEA uses the same set-up as analysis/fea.py: arm clamped top and bottom up to the clamp-plate edge,
2.6 kgf (25.5 N) upward on the motor (applied on the pocket ceiling, where the motor screw heads pull), printed
PA6-CF (E = 4.5 GPa, nu = 0.35), quadratic tetrahedra from gmsh, CalculiX solver.
"""
import json
import os
import sys
import time

import FreeCAD as App
import Import
import ObjectsFem
import Part
from femmesh.gmshtools import GmshTools
from femtools import ccxtools

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
ROOT = os.path.dirname(HERE) if os.path.basename(HERE) == "freecad" else os.getcwd()
OUT = os.path.join(ROOT, "output", "freecad")
os.makedirs(OUT, exist_ok=True)
CHK = json.load(open(os.path.join(ROOT, "output", "report", "checks.json")))
G, P = CHK["geometry"], CHK["params"]
CLAMP, T, FLOOR, R = G["clamp_edge_mm"], P["arm_t"], P["arm_floor"], G["R_motor_mm"]
THRUST_N, ALLOW, BAND = 25.5, 35.0, 3.0


def log(*a):
    print(*a, flush=True)
    App.Console.PrintMessage(" ".join(str(x) for x in a) + "\n")


# ------------------------------------------------------------------ arm FEA
def arm_fea():
    doc = App.newDocument("ArmFEA")
    shp = Part.read(os.path.join(OUT, "arm_for_fea.step"))
    arm = doc.addObject("Part::Feature", "PrintedArm")
    arm.Shape = shp
    doc.recompute()

    clamp, pocket, up = [], None, None
    for i, f in enumerate(shp.Faces, 1):
        if not isinstance(f.Surface, Part.Plane):
            continue
        u0, u1, v0, v1 = f.ParameterRange
        n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        c = f.CenterOfMass
        if abs(n.z) < 0.99:
            continue
        on_top, on_bot = abs(c.z - T) < 1e-3, abs(c.z) < 1e-3
        if (on_top or on_bot) and c.x < CLAMP:
            clamp.append(f"Face{i}")
        if abs(c.z - (T - FLOOR)) < 1e-3 and c.x > R - 20:
            pocket = f"Face{i}"
        if on_top and n.z > 0 and c.x > CLAMP:
            up = f"Face{i}"
    log("clamp faces", clamp, "load face", pocket, "direction face", up)

    an = ObjectsFem.makeAnalysis(doc, "Analysis")
    solver = ObjectsFem.makeSolverCalculiXCcxTools(doc, "CalculiX")
    solver.AnalysisType = "static"
    solver.GeometricalNonlinearity = "linear"
    an.addObject(solver)
    mat = ObjectsFem.makeMaterialSolid(doc, "PA6_CF_printed")
    m = mat.Material
    m.update({"Name": "PA6-CF printed (6 walls, 50 % gyroid)", "YoungsModulus": "4500 MPa", "PoissonRatio": "0.35",
              "Density": "960 kg/m^3"})
    mat.Material = m
    an.addObject(mat)
    fixed = ObjectsFem.makeConstraintFixed(doc, "Clamp_between_plates")
    fixed.References = [(arm, tuple(clamp))]
    an.addObject(fixed)
    force = ObjectsFem.makeConstraintForce(doc, "Full_thrust_2_6kgf")
    force.References = [(arm, pocket)]
    force.Force = f"{THRUST_N} N"
    force.Direction = (arm, [up])
    force.Reversed = False
    an.addObject(force)
    mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
    if hasattr(mesh, "Shape"):
        mesh.Shape = arm
    else:
        mesh.Part = arm
    mesh.CharacteristicLengthMax = "3.5 mm"
    mesh.CharacteristicLengthMin = "0.8 mm"
    mesh.ElementOrder = "2nd"
    mesh.SecondOrderLinear = True        # straight mid-side nodes: avoids inverted (negative Jacobian) elements at fillets
    mesh.OptimizeStd = True
    an.addObject(mesh)
    doc.recompute()

    t0 = time.time()
    err = GmshTools(mesh).create_mesh()
    if err:
        log("gmsh:", err)
    fm = mesh.FemMesh
    log(f"mesh: {fm.NodeCount} nodes, {fm.VolumeCount} tetrahedra")

    fea = ccxtools.FemToolsCcx(an, solver)
    fea.purge_results()
    fea.reset_all()
    fea.update_objects()
    fea.setup_working_dir(os.path.join(OUT, "ccx_work"))
    fea.setup_ccx()
    msg = fea.check_prerequisites()
    if msg:
        log("prerequisites:", msg)
    fea.write_inp_file()
    fea.ccx_run()
    fea.load_results()
    doc.recompute()

    res = [o for o in an.Group if o.isDerivedFrom("Fem::FemResultObject")][0]
    nodes = res.Mesh.FemMesh.Nodes
    vm = dict(zip(res.NodeNumbers, res.vonMises))
    disp = dict(zip(res.NodeNumbers, res.DisplacementVectors))
    far = [v for n, v in vm.items() if nodes[n].x > CLAMP + BAND]
    tip = [disp[n].z for n in vm if (nodes[n].x - R) ** 2 + nodes[n].y ** 2 < 25]
    out = {
        "software": f"FreeCAD {'.'.join(App.Version()[:3])} FEM workbench, gmsh mesh, CalculiX solver",
        "mesh_nodes": fm.NodeCount, "mesh_tetrahedra": fm.VolumeCount, "element_order": 2,
        "load_N": THRUST_N,
        "max_von_mises_MPa_everywhere": round(max(res.vonMises), 2),
        "max_von_mises_MPa_outside_clamp_band": round(max(far), 2),
        "motor_deflection_mm": round(sum(tip) / max(len(tip), 1), 3),
        "safety_factor_vs_35MPa": round(ALLOW / max(far), 1),
        "solve_s": round(time.time() - t0, 1),
        "note": "the 'everywhere' maximum includes the artificial spike at the perfectly rigid clamp edge; "
                f"the outside-band value ignores the first {BAND:.0f} mm, same as analysis/fea.py",
    }
    path = os.path.join(OUT, "arm_FEA_FreeCAD.FCStd")
    doc.saveAs(path)
    log("saved", path, out)
    App.closeDocument(doc.Name)
    return out


# ------------------------------------------------------------------ assemblies
def step_to_fcstd(step_name, fc_name):
    src = os.path.join(ROOT, "output", "assembly", step_name)
    doc = App.newDocument(fc_name)
    t0 = time.time()
    Import.insert(src, doc.Name)
    doc.recompute()
    path = os.path.join(OUT, fc_name + ".FCStd")
    doc.saveAs(path)
    log(f"saved {path} ({len(doc.Objects)} objects, {time.time() - t0:.0f} s)")
    App.closeDocument(doc.Name)


if __name__ in ("__main__", "make_freecad_files") or True:
    import traceback
    what = [a for a in sys.argv[1:] if not a.endswith(".py")] or ["fea", "assemblies"]
    results = {}
    try:
        if "fea" in what:
            results["arm_fea"] = arm_fea()
            json.dump(results, open(os.path.join(OUT, "freecad_fea_results.json"), "w"), indent=2)
        if "assemblies" in what:
            step_to_fcstd("drone_full.step", "drone_full")
            step_to_fcstd("dock_closed_with_drone.step", "dock_closed")
            step_to_fcstd("dock_open_with_drone.step", "dock_open")
        log("done")
    except Exception:
        log("FAILED:\n" + traceback.format_exc())
