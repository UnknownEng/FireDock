# Using the Docker Drone files in FreeCAD 1.1

All files are in `output/freecad/`. Rebuild them any time with:
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" freecad\make_freecad_files.py
```

## 1. Stress test of the printed arm: `arm_FEA_FreeCAD.FCStd`
A complete FEM study in FreeCAD's FEM workbench, already solved with CalculiX:

| Object | What it is |
|---|---|
| `PrintedArm` | the PA-CF arm (top/bottom faces split at the clamp-plate edge, 53.25 mm) |
| `PA6_CF_printed` | material: E = 4.5 GPa, ν = 0.35, ρ = 960 kg/m³ (1200 × 80 % print fill) |
| `Clamp_between_plates` | fixed: the arm faces clamped between the bottom plate and the clamp plate |
| `Full_thrust_2_6kgf` | 25.5 N upward on the motor-pocket ceiling (where the motor screw heads pull) |
| `Mesh` | gmsh, 2nd-order tetrahedra (34 k elements, 57 k nodes) |
| `CCX_Results` | CalculiX results |

**See the stress:** open the file → switch to the **FEM** workbench → double-click **CCX_Results** →
pick **von Mises stress** (or **Displacement**, and tick "Show" with a factor of 100 to see the bend).
Or select `Pipeline_CCX_Results` and use the colour bar in the 3D view.

**Run it again** (for example after changing the load or the material): double-click `Full_thrust_2_6kgf` or
`PA6_CF_printed` to edit them, then select `Analysis` → right-click `CalculiX` → **Solve**, or use the
**Solver CalculiX** toolbar button.

Result (25.5 N, full thrust on one arm):

| | FreeCAD / CalculiX | analysis/fea.py (scikit-fem) | beam theory |
|---|---|---|---|
| Motor deflection | 0.60 mm | 0.654 mm | 0.621 mm |
| Peak stress outside the clamp edge | 5.0 MPa | 6.4 MPa | 4.9 MPa |
| Safety factor vs 35 MPa | 7.0 | 5.4 | 7.1 |

The highest number FreeCAD shows (6.75 MPa) sits right on the clamp edge, where a perfectly rigid clamp makes an
artificial spike; the table ignores the first 3 mm, like `analysis/fea.py`.

## 2. The drone and the dock
* `drone_full.FCStd`: the complete drone (every part a solid, with colours)
* `dock_closed.FCStd`: dock closed with the drone centred inside
* `dock_open.FCStd`: dock open (covers down, pushers parked) with the drone

These are solid models imported from the STEP files. You can measure, section (Part → Cross-sections), check
interference (Part → Check geometry / Boolean common), and export drawings (TechDraw workbench).
To change a dimension properly, change it in `cad/build.py` or `cad/dock.py` (every size is a parameter) and
re-run the build, then this script; or rebuild a part as a parametric PartDesign body in FreeCAD, using the
imported solid as a reference.

## FEA of other parts
Copy `arm_FEA_FreeCAD.FCStd`, replace `PrintedArm` with any part from `output/parts/*.step`
(File → Import), re-pick the faces of the two constraints, re-mesh (double-click `Mesh` → Apply) and solve.
