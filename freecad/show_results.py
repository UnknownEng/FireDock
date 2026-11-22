# FreeCAD GUI macro: show the arm FEA result (von Mises stress) and save a picture of it.
# Started automatically by freecad\open_in_freecad.bat; you can also run it from Macro -> Macros...
import os

import FreeCAD as App
import FreeCADGui as Gui

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "freecad") \
    if "__file__" in globals() else os.path.join(os.getcwd(), "output", "freecad")

fea = next((App.getDocument(n) for n in App.listDocuments() if App.getDocument(n).getObject("Pipeline_CCX_Results")), None)
if fea is not None:
    Gui.activateWorkbench("FemWorkbench")
    App.setActiveDocument(fea.Name)
    Gui.ActiveDocument = Gui.getDocument(fea.Name)
    for o in fea.Objects:
        if hasattr(o, "ViewObject") and o.ViewObject is not None:
            o.ViewObject.Visibility = False
    vo = fea.getObject("Pipeline_CCX_Results").ViewObject
    vo.Visibility = True
    try:
        modes = vo.listDisplayModes()
        vo.DisplayMode = next((m for m in modes if m.lower() == "surface"), modes[0])
        field = next((f for f in vo.getEnumerationsOfProperty("Field") if "mises" in f.lower()), None)
        if field:
            vo.Field = field
    except Exception as e:  # property names differ slightly between FreeCAD versions
        App.Console.PrintWarning(f"result display: {e}\n")
    for name in ("Clamp_between_plates", "Full_thrust_2_6kgf"):
        o = fea.getObject(name)
        if o is not None:
            o.ViewObject.Visibility = True
    v = Gui.ActiveDocument.ActiveView
    v.viewIsometric()
    v.fitAll()
    try:
        v.saveImage(os.path.join(OUT, "arm_FEA_FreeCAD_vonMises.png"), 1600, 1000, "White")
    except Exception as e:
        App.Console.PrintWarning(f"save image: {e}\n")
    App.Console.PrintMessage("Arm FEA: von Mises stress shown (double-click CCX_Results for other result types)\n")
