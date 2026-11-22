"""
Build the combined PDF report (design, parts, checks, beam analysis, FEA, CFD, renders) from the result files.

Run (after build.py, analysis.py, fea.py, cfd.py, render.py):
    .venv\\Scripts\\python analysis\\make_report.py
Writes output/Docker_Drone_Report.pdf
"""
import json
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parent.parent
O = ROOT / "output"


def load(p):
    p = O / p
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


chk, ana, fea, cfd = load("report/checks.json"), load("report/analysis.json"), load("fea/fea_results.json"), \
    load("cfd/cfd_results.json")

# fonts: Segoe UI / Arial from Windows when available (they include symbols such as ≈ and ±)
FONT, BOLD = "Helvetica", "Helvetica-Bold"
for reg, bold in (("segoeui.ttf", "segoeuib.ttf"), ("arial.ttf", "arialbd.ttf")):
    fr, fb = Path("C:/Windows/Fonts") / reg, Path("C:/Windows/Fonts") / bold
    if fr.exists() and fb.exists():
        pdfmetrics.registerFont(TTFont("Body", str(fr)))
        pdfmetrics.registerFont(TTFont("BodyB", str(fb)))
        pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyB", italic="Body", boldItalic="BodyB")
        FONT, BOLD = "Body", "BodyB"
        break

ss = getSampleStyleSheet()
ACC = colors.HexColor("#1f4e79")
st = {
    "title": ParagraphStyle("t", parent=ss["Title"], fontName=BOLD, fontSize=24, leading=29, textColor=ACC),
    "sub": ParagraphStyle("s", parent=ss["Normal"], fontName=FONT, fontSize=12, leading=16, alignment=TA_CENTER,
                          textColor=colors.HexColor("#444444")),
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName=BOLD, fontSize=16, leading=20, textColor=ACC,
                         spaceBefore=6, spaceAfter=6),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName=BOLD, fontSize=12.5, leading=16, textColor=ACC,
                         spaceBefore=8, spaceAfter=4),
    "p": ParagraphStyle("p", parent=ss["Normal"], fontName=FONT, fontSize=9.5, leading=13.5, spaceAfter=4),
    "cap": ParagraphStyle("c", parent=ss["Normal"], fontName=FONT, fontSize=8.5, leading=11, alignment=TA_CENTER,
                          textColor=colors.HexColor("#555555"), spaceAfter=8),
    "cell": ParagraphStyle("cell", parent=ss["Normal"], fontName=FONT, fontSize=8.5, leading=11),
    "cellb": ParagraphStyle("cellb", parent=ss["Normal"], fontName=BOLD, fontSize=8.5, leading=11,
                            textColor=colors.white),
}
W = A4[0] - 36 * mm


def P(t, s="p"):
    return Paragraph(t, st[s])


def table(rows, widths=None, header=True):
    data = [[P(str(c), "cellb" if header and i == 0 else "cell") for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0b7c3")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f9")]),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), ACC))
    t.setStyle(TableStyle(style))
    return t


def img(path, width=W, caption=None):
    p = O / path
    if not p.exists():
        return []
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(str(p)).getSize()
    h = width * ih / iw
    if h > 200 * mm:
        width, h = width * 200 * mm / h, 200 * mm
    out = [Image(str(p), width=width, height=h)]
    if caption:
        out.append(P(caption, "cap"))
    return [KeepTogether(out)]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 8)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(18 * mm, 10 * mm, "Docker Drone: printed 7-inch drone + charging dock")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


S = []
C = chk["checks"]
R = ana["results"]
perf = R["performance"]
DP = chk["dock_params"]
fmt = lambda d: f"{d['distance_mm']} mm" if isinstance(d, dict) else str(d)  # noqa: E731
none_or = lambda v: "none" if not v else f"{len(v)} found: " + ", ".join(f"{x['a']}/{x['b']}" for x in v[:4])  # noqa: E731
hover_loss = cfd["hover"]["flight_time_loss_pct"] if cfd and "hover" in cfd else 0.0
hover_min = perf["hover_flight_time_min"] * (1 - hover_loss / 100)

# ---------------------------------------------------------------- cover
S += [Spacer(1, 22 * mm), P("Docker Drone", "title"),
      P("3D-printed 7-inch autonomous drone and flat-top charging dock: design, tests and simulation", "sub"),
      Spacer(1, 3 * mm), P(f"Generated {date.today():%d %B %Y} from the parametric CAD model", "sub"), Spacer(1, 6 * mm)]
S += img("renders/dock_open.png", W * 0.78)
S += [Spacer(1, 3 * mm), table([
    ["Item", "Value"],
    ["Frame", f"3D-printed PA-CF, {C['printed_frame_mass_g']:.0f} g printed parts, every part fits a "
              f"{C['print_bed_fit']['bed_mm'][0]:.0f} mm bed"],
    ["All-up weight / thrust-to-weight", f"≈{perf['AUW_g']:.0f} g / ≈{perf['thrust_to_weight']} : 1"],
    ["Hover time (6S 3000 mAh)", f"≈{hover_min:.0f} min (estimate, incl. prop-wash loss from CFD)"],
    ["Drone size with props", f"{C['drone_envelope_mm']['x']:.0f} × {C['drone_envelope_mm']['y']:.0f} × "
                              f"{C['drone_envelope_mm']['z']:.0f} mm"],
    ["Dock closed / open", f"{C['dock_closed_size_mm']['x']} × {C['dock_closed_size_mm']['y']} × {C['dock_closed_size_mm']['z']} mm / "
                           f"{C['dock_open_size_mm']['x']} mm wide with the covers down"],
    ["Dock functions", "motorised covers, X/Y auto-centring, contact charging, Wi-Fi API"],
    ["Landing capture", f"±{C['landing_capture_mm']['aligned_yaw']:.0f} mm (±{C['landing_capture_mm']['worst_yaw_45deg']:.0f} mm at 45° yaw)"],
], [W * 0.34, W * 0.66]), PageBreak()]

# ---------------------------------------------------------------- summary
S += [P("1. Summary", "h1"),
      P("<b>Drone.</b> True-X, 320 mm wheelbase, 7-inch props. Every frame part is 3D printed in PA-CF (nylon + carbon "
        "fibre): 14 mm tall arms (as stiff as the 6 mm carbon arms they replace), 4 mm plates, hollow legs. Each foot "
        "carries a stainless dome contact; the charge current goes up the legs to an ideal-diode bridge and a 6S BMS."),
      P("<b>Dock.</b> The landing deck is the top of the dock, so nothing ever surrounds the props. Two covers flip 180° "
        "outward on worm-gear motors and hang beside the body. After landing, X and Y pusher bars (on MGN12 rails, "
        "4 steppers) slide the legs onto four copper pads; the dock then closes and charges the battery. An ESP32 runs "
        "the dock and talks to the drone's Raspberry Pi over Wi-Fi."),
      P("Checks run on the model:")]
rows = [["Check", "Tool", "Result"],
        ["Fit: collisions, clearances, camera view", "CAD (OpenCascade)",
         "No collisions in the drone, nor with the dock closed, open or centring; covers sweep 0–180° clear"],
        ["Printability", "CAD", f"all {len(chk['print_list'])} printed part types fit the bed"],
        ["Strength, stiffness, heat", "Beam theory",
         f"Arm safety factor {R['LC1_full_thrust']['safety_factor']} at full thrust; "
         f"{R['comparison_vs_carbon_arm']['stiffness_vs_carbon_pct']:.0f} % of the carbon arm's stiffness"]]
if fea:
    rows.append(["Stress test of the printed arm", "3D FEA (quadratic tets)",
                 f"Peak {fea['LC1_full_thrust']['peak_von_mises_MPa']} MPa at full thrust (SF {fea['LC1_full_thrust']['safety_factor']}); "
                 f"first mode {fea['modal']['modes'][0]['freq_Hz']:.0f} Hz"])
if cfd and "hover" in cfd:
    rows.append(["Airflow", "3D CFD on the GPUs",
                 f"Prop wash on the frame {cfd['hover']['download_pct_of_thrust']} % of thrust"
                 + (f"; drag {cfd['ff0']['drag_N']} N at 15 m/s" if "ff0" in cfd else "")
                 + ("; take-off from the open dock simulated" if "dock_takeoff" in cfd else "")])
S += [table(rows, [W * 0.3, W * 0.22, W * 0.48])]

# ---------------------------------------------------------------- parts
S += [P("2. Bought parts on the drone", "h1")]
rows = [["Part", "Weight (g)"]]
for k, v in chk["components"].items():
    rows.append([v["description"], f"{v['mass_g']:.0f}"])
S += [table(rows, [W * 0.82, W * 0.18])]
S += [P("Printed parts (drone and dock)", "h2"),
      P("STL files in <b>output/print/</b> are already in print orientation. Full settings in "
        "output/system/print_guide.md; full shopping list in output/system/BOM.csv.")]
rows = [["Part", "Qty", "Material", "Size (mm)", "g each", "Fits bed"]]
for p in chk["print_list"]:
    rows.append([p["part"], p["qty"], p["material"].upper(), " × ".join(f"{v:g}" for v in p["size_mm"]),
                 f"{p['mass_each_g']}", "yes" if p["fits_bed"] else "NO"])
S += [table(rows, [W * 0.34, W * 0.07, W * 0.12, W * 0.22, W * 0.12, W * 0.13]), PageBreak()]

# ---------------------------------------------------------------- renders
S += [P("3. Model views", "h1")]
S += img("renders/drone_full_iso.png", W * 0.75, "The drone: printed PA-CF frame, Pi 5 on top, battery crosswise underneath")
S += img("renders/drone_full_side.png", W * 0.75, "Side view (front right): contact domes under the feet")
S += img("renders/frame_top.png", W * 0.6, "Bare printed frame, top view")
S += img("renders/dock_closed.png", W * 0.75, "Dock closed: drone centred and charging under the twin-wall covers")
S += img("renders/dock_centering.png", W * 0.75, "After landing: X and Y pushers slide the legs onto the four charge pads")
S += img("renders/dock_centering_top.png", W * 0.6, "Top view: drone centred, feet on the copper pads")
S += img("renders/dock_mechanism.png", W * 0.75, "Deck mechanism: MGN12 rails, GT2 belts, 4 NEMA17 steppers")

# ---------------------------------------------------------------- fit checks
S += [PageBreak(), P("4. Fit checks (CAD)", "h1")]
lc = C["landing_capture_mm"]
rows = [["Check", "Result"],
        ["Collisions inside the drone", none_or(C["drone_interference"])],
        ["Collisions: dock closed / open / centring", " / ".join(none_or(C[f"dock_{k}_interference"]) for k in ("closed", "open", "centering"))],
        ["Covers swept 0° → 180° in 15° steps", none_or(C["cover_sweep_0_to_180deg_interference"])],
        ["Take-off column above the open dock", f"{2 * C['takeoff_column_half_width_mm']:.0f} mm square, "
                                                f"{C['takeoff_column_vs_dock_open_mm3']} mm³ of dock inside it"],
        ["Props to the nearest dock part (open)", fmt(C["props_to_dock_when_open"])],
        ["Drone top to the closed covers", fmt(C["drone_top_to_closed_cover"])],
        ["Pushers to the legs when centred", fmt(C["pusher_to_leg_when_centred"])],
        ["Pushers to anything else on the drone", fmt(C["pushers_to_drone_body_when_centred"])],
        ["Landing capture (drone still centred)", f"±{lc['aligned_yaw']} mm aligned, ±{lc['worst_yaw_45deg']} mm at 45° yaw"],
        ["Prop to nearest drone part / prop to prop", f"{fmt(C['prop_to_anything_min_clearance'])} / {fmt(C['prop_to_prop_min_gap'])}"],
        ["Lowest part (BMS) to ground", f"{C['battery_ground_clearance_mm']} mm"],
        ["Down-camera view blocked by", ", ".join(C["down_camera_view_blocked_by"]) or "nothing"],
        ["Compass to ESC / battery", f"{fmt(C['compass_to_esc_mm'])} / {fmt(C['compass_to_battery_mm'])}"],
        ["Centre of gravity", f"{C['cg_mm']['offset_from_centre_mm']} mm from centre, "
                              f"{C['cg_mm']['below_prop_plane_mm']} mm below the prop plane"],
        ["Every printed part fits the bed", "yes" if C["print_bed_fit"]["all_fit"] else "NO: " + ", ".join(C["print_bed_fit"]["too_big"])]]
S += [table(rows, [W * 0.4, W * 0.6])]

# ---------------------------------------------------------------- beam analysis
S += [P("5. Strength, vibration and heat (beam theory)", "h1"),
      P(f"Hand calculations on the real arm geometry, cantilevered from the clamp-plate edge. Material: "
        f"{ana['materials']['pa_cf']['name']}, E = {ana['materials']['pa_cf']['E'] / 1000:.1f} GPa, design allowable "
        f"{ana['materials']['pa_cf']['design_allow']:.0f} MPa (about 40 % of the dry strength, for moisture, layer lines "
        "and fatigue). Checked against the 3D FEA in section 6.")]
cv = R["comparison_vs_carbon_arm"]
rows = [["Load case", "Result", "Safety factor / capacity"],
        ["LC1 full thrust 2.6 kgf on one arm", f"{R['LC1_full_thrust']['max_stress_MPa']} MPa, "
         f"{R['LC1_full_thrust']['tip_deflection_mm']} mm deflection", f"{R['LC1_full_thrust']['safety_factor']}"],
        ["LC2 motor reaction torque 400 N·mm", f"{R['LC2_motor_torque']['shear_stress_MPa']} MPa shear",
         f"{R['LC2_motor_torque']['safety_factor']:.0f}"],
        ["LC3 vertical crash on one arm tip", f"design allowable at {R['LC3_vertical_crash_one_arm']['tip_force_to_reach_allowable_N']:.0f} N; "
         f"breaks at ≈{cv['this_arm_ultimate_force_N']:.0f} N", f"{R['LC3_vertical_crash_one_arm']['equivalent_g_whole_drone']} g "
                                                               f"(breaks ≈{cv['this_arm_ultimate_g']} g)"],
        ["LC4 side hit on a motor", f"design allowable at {R['LC4_side_hit_one_arm']['tip_force_to_reach_allowable_N']:.0f} N",
         f"{R['LC4_side_hit_one_arm']['equivalent_g_whole_drone']} g"],
        ["LC5 top-deck standoffs, 50 g side impact", f"{R['LC5_standoff_side_impact_50g']['stress_MPa']} MPa",
         f"{R['LC5_standoff_side_impact_50g']['safety_factor']}"],
        ["LC6 landing leg, 5 g hard landing", f"{R['LC6_leg_hard_landing']['stress_MPa']} MPa",
         f"{R['LC6_leg_hard_landing']['safety_factor']}"],
        ["Stiffness vs the 6 mm carbon arm", f"{cv['stiffness_vs_carbon_pct']:.0f} %", ""],
        ["Arm first bending mode", f"{R['vibration']['arm_first_bending_Hz']:.0f} Hz",
         f"props {R['vibration']['prop_rotation_hover_Hz']:.0f}–{R['vibration']['prop_rotation_max_Hz']:.0f} Hz"]]
S += [table(rows, [W * 0.36, W * 0.38, W * 0.26]), P("Heat", "h2")]
rows = [["Part", "Worst °C", "Material", "Limit °C", "Margin °C"]]
for x in ana["thermal"]:
    rows.append([x["part"], x["worst_C"], x["material"], f"{x['limit_C']:.0f}", f"{x['margin_C']:.0f}"])
S += [table(rows, [W * 0.32, W * 0.1, W * 0.32, W * 0.13, W * 0.13]),
      P("Print the arms, plates and legs in <b>PA6-CF</b>, dried, and anneal them if you can. Un-annealed PET-CF softens "
        "around 80 °C, below a hot motor base, so keep PET-CF for the small parts only.")]

# ---------------------------------------------------------------- FEA
if fea:
    f1, mo = fea["LC1_full_thrust"], fea["modal"]
    S += [PageBreak(), P("6. Stress test: 3D finite-element analysis of the printed arm", "h1"),
          P(f"{fea['method']}. Mesh {fea['mesh']['tets']:,} tetrahedra, {fea['mesh']['dofs']:,} unknowns, solved with "
            f"Intel MKL PARDISO. E = {fea['material']['E_MPa'] / 1000:.1f} GPa, allowable {fea['material']['allowable_MPa']:.0f} MPa. "
            f"Boundary: {fea['boundary']}.")]
    rows = [["Case", "FEA", "Beam theory"],
            ["LC1 peak stress at full thrust", f"{f1['peak_von_mises_MPa']} MPa (SF {f1['safety_factor']})",
             f"{R['LC1_full_thrust']['max_stress_MPa']} MPa (SF {f1['beam_theory_safety_factor']})"],
            ["LC1 motor deflection", f"{f1['motor_deflection_mm']} mm", f"{f1['beam_theory_deflection_mm']} mm"],
            ["LC1 bending stress, same points near the clamp", f"{f1['nominal_bending_near_clamp_MPa']} MPa",
             f"{f1['beam_theory_at_same_place_MPa']} MPa"],
            ["LC2 motor torque", f"{fea['LC2_motor_torque']['peak_von_mises_MPa']} MPa (SF {fea['LC2_motor_torque']['safety_factor']:.0f})",
             f"SF {R['LC2_motor_torque']['safety_factor']:.0f}"],
            ["LC3 vertical crash (design allowable)", f"{fea['LC3_vertical_crash_one_arm']['equivalent_g_whole_drone']} g",
             f"{fea['LC3_vertical_crash_one_arm']['beam_theory_g']} g"],
            ["LC4 side hit (design allowable)", f"{fea['LC4_side_hit_one_arm']['equivalent_g_whole_drone']} g",
             f"{fea['LC4_side_hit_one_arm']['beam_theory_g']} g"]]
    S += [table(rows, [W * 0.4, W * 0.32, W * 0.28])]
    S += [P("Mesh study (LC1): " + "; ".join(f"h {m['h_mm']} mm: {m['LC1_peak_MPa']} MPa, {m['LC1_tip_mm']} mm"
                                             for m in fea["mesh_study"]))]
    S += [P("Natural frequencies (arm with motor and prop): " +
            "; ".join(f"{m['freq_Hz']:.0f} Hz {m['shape']}" for m in mo["modes"][:4]) +
            f". Props turn at about {mo['prop_hover_Hz']:.0f} Hz in hover and up to {mo['prop_max_Hz']:.0f} Hz: use the RPM "
            "harmonic notch (bidirectional DShot), already set in companion/ardupilot_dock.param.")]
    S += img("fea/fea_LC1_full_thrust.png", W, "LC1 full thrust: von Mises stress and deformed shape")
    S += img("fea/fea_LC4_side_hit.png", W, "LC4 side hit at the load that reaches the allowable")
    S += img("fea/fea_modes.png", W, "First three mode shapes")

# ---------------------------------------------------------------- CFD
if cfd:
    S += [PageBreak(), P("7. Airflow: 3D CFD", "h1"),
          P("3D lattice-Boltzmann solver (D3Q19, BGK + Smagorinsky LES) on the real CAD geometry, run on the NVIDIA "
            "MX450 and the Intel Iris Xe through OpenCL. Coarse LES gives indicative numbers (about ±20–30 %), so the "
            "solver is first checked on a cube with a published drag coefficient.")]
    if "cube" in cfd:
        c = cfd["cube"]
        S += [P("Solver check", "h2"),
              P(f"Cube face-on: Cd = <b>{c['Cd']}</b> against the published {c['reference_Cd']} ({c['reference']}), "
                f"error {c['error_pct']} %.")]
    if "hover" in cfd:
        h = cfd["hover"]
        S += [P("Hover: prop wash on the frame", "h2"),
              table([["Quantity", "Value"],
                     ["Thrust per motor", f"{h['thrust_per_motor_N']} N"],
                     ["Download on the airframe", f"{h['download_on_airframe_N']} N = {h['download_pct_of_thrust']} % of thrust"],
                     ["Effect on hover time", f"about −{h['flight_time_loss_pct']} % (≈{hover_min:.0f} min instead of ≈{perf['hover_flight_time_min']:.0f} min)"],
                     ["Air speed through the props (CFD / momentum theory)",
                      f"{h['induced_velocity_mps']} / {h['momentum_theory_induced_velocity_mps']} m/s"]],
                    [W * 0.55, W * 0.45])]
        S += img("cfd/cfd_hover_downwash.png", W, "Hover: diagonal slice through two motors and a top view under the frame")
    if "dock_takeoff" in cfd:
        d = cfd["dock_takeoff"]
        rows = [["Quantity", "Value"], ["Total thrust", f"{d['thrust_total_N']} N"]]
        for k in ("drone", "dock", "ground"):
            if f"downward_force_on_{k}_N" in d:
                rows.append([f"Downward wash force on the {k}", f"{d[f'downward_force_on_{k}_N']} N"])
        rows.append(["Fastest wash 40 mm above the deck", f"{d['max_wash_speed_40mm_above_deck_mps']} m/s"])
        S += [P("Take-off from the open dock", "h2"),
              P(f"Drone hovering with its feet {d['drone_feet_above_deck_mm']:.0f} mm above the deck, covers down, pushers "
                "parked, ground below. The wash hits the flat deck and spreads outward; there are no walls to throw it "
                "back into the props."), table(rows, [W * 0.55, W * 0.45])]
        S += img("cfd/cfd_dock_takeoff.png", W, "Take-off from the open dock: side view and wash over the deck")
    ff = [cfd[k] for k in ("ff0", "ff25") if k in cfd]
    if ff:
        S += [P("Forward flight at 15 m/s (props removed)", "h2")]
        rows = [["Attitude", "Drag", "CdA", "Vertical force", "Drag power", "Drag at 20 m/s"]]
        for f in ff:
            rows.append(["level" if f["pitch_deg"] == 0 else f"{f['pitch_deg']}° nose-down", f"{f['drag_N']} N",
                         f"{f['CdA_m2'] * 1e4:.0f} cm²", f"{f['vertical_force_N']} N", f"{f['drag_power_W']} W",
                         f"{f['drag_at_20mps_N']} N"])
        S += [table(rows, [W * 0.2, W * 0.14, W * 0.14, W * 0.18, W * 0.16, W * 0.18])]
        S += img("cfd/cfd_forward_0deg_top.png", W * 0.9, "Forward flight, level: top view at arm height")
    runs = [[k, v.get("device", "CPU"), f"{v.get('seconds', 0) / 60:.1f} min"] for k, v in cfd.items()]
    S += [P("Where each case ran", "h2"), table([["Case", "Device", "Solve time"]] + runs, [W * 0.25, W * 0.5, W * 0.25]),
          P("Limits: thin plates are a few cells thick (so forces are on the high side); props are actuator discs "
            "without blades or swirl; velocities are time-averaged.")]

# ---------------------------------------------------------------- dock system
S += [PageBreak(), P("8. The dock system", "h1"),
      P("<b>Take-off:</b> the Pi calls POST /launch. The dock stops charging, flips both covers 180° outward (about 12 s) "
        f"and parks the pushers at {DP['park']:.0f} mm from the centre. Nothing is left above the deck."),
      P("<b>Landing:</b> RTL with ArduPilot precision landing on the 130 mm ArUco marker (downward Pi Camera 3, "
        f"companion/precision_landing.py). The pushers catch the drone within ±{lc['aligned_yaw']:.0f} mm of the centre. "
        "After disarm the Pi calls POST /dock: X then Y pushers centre the legs and square the yaw, the covers close "
        "with the drone held, and charging starts."),
      P("<b>Charging:</b> 25.2 V CC/CV charger → relay → INA226 current monitor → four copper pads. On the drone: four "
        "foot contacts → ideal-diode bridge (any polarity, so any of the four square yaws charges) → fuse → 6S BMS "
        "(cell balancing) → battery. The controller stops at < 0.3 A (full), > 45 °C, > 25.4 V, 2 h, or no current."),
      P("<b>Interlocks:</b> covers and pushers never move together; every move has a timeout; an e-stop button or "
        "POST /stop switches everything off; after a fault the pushers re-home first.")]
S += img("system/wiring_diagram.png", W, "Wiring: dock electronics and the on-drone charging path")
S += [P("Software", "h2"),
      table([["File", "Runs on", "Does"],
             ["firmware/dock_controller (PlatformIO)", "ESP32 in the dock", "covers, pushers, charging, Wi-Fi HTTP API"],
             ["companion/dock_client.py", "Pi 5 / laptop", "launch, dock, open, close, status …"],
             ["companion/precision_landing.py", "Pi 5", "ArUco detection → MAVLink LANDING_TARGET"],
             ["companion/mission.py", "Pi 5", "dock → take-off → AUTO mission → RTL → dock + charge"],
             ["companion/ardupilot_dock.param", "flight controller", "precision landing, RPM notch, failsafes, ports"]],
            [W * 0.36, W * 0.2, W * 0.44])]

# ---------------------------------------------------------------- files + limits
S += [PageBreak(), P("9. Files in the package", "h1")]
S += [table([["Folder", "Contents", "Use"],
             ["output/print", "every printed part as STL, already in print orientation", "slicer → printer"],
             ["output/parts", "every part as STEP, IGES and STL (drone + dock)", "SolidWorks / any CAD"],
             ["output/assembly", "drone, frame only, dock closed / open / centring with the drone (STEP, GLB)", "SolidWorks assembly, 3D viewer"],
             ["output/system", "wiring diagram, BOM (CSV + MD), print guide, operating sequence", "building it"],
             ["output/dxf, output/svg", "flat outlines of the plates", "drawings, checking"],
             ["output/report", "checks.json, analysis.json, analysis_report.md", "fit checks, beam analysis"],
             ["output/fea", "FEA results, pictures, arm_fea_results.vtu", "stress test (ParaView)"],
             ["output/cfd", "CFD results, pictures, *.vtk, GPU run logs", "airflow (ParaView)"],
             ["firmware, companion", "dock firmware and the Pi scripts", "flashing / flying"],
             ["cad, analysis", "Python source of the model and every test", "change a size and re-run"]],
            [W * 0.2, W * 0.5, W * 0.3])]
S += [P("Limits of this report", "h2"),
      P("Nothing here has been built, printed or flown yet. Motor thrust, flight time, landing accuracy and LoRa range are "
        "estimates. Printed-part strength depends on the printer, the filament and its dryness: print a test arm and "
        "break it before trusting the numbers. The firmware and scripts are written for this hardware but have not run "
        "on it: bench-test the dock (covers, pushers, charging with a dummy load) before putting a drone in it. LiPo "
        "charging in a closed box needs a fire-safe layout and supervision until you trust it.")]

doc = SimpleDocTemplate(str(O / "Docker_Drone_Report.pdf"), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=16 * mm, bottomMargin=18 * mm, title="Docker Drone report", author="Docker Drone project")
doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("wrote", O / "Docker_Drone_Report.pdf")
