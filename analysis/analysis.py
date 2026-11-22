"""
Strength, stiffness, vibration and thermal checks for the 7-inch frame + dock.

Reads geometry/mass from output/report/checks.json (written by cad/build.py) and
writes output/report/analysis_report.md + analysis.json.

Method: classical beam theory on the real arm geometry (tapered 14 mm printed PA-CF arm,
cantilevered from the clamp-plate edge). This is the hand-calculation check; analysis/fea.py
runs the 3D finite-element version.
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
REP = ROOT / "output" / "report"
data = json.loads((REP / "checks.json").read_text())
P, G, M = data["params"], data["geometry"], data["masses"]

g = 9.81

# ---------------- material data (typical published values, mm/N/MPa) --------------
MAT = {
    "carbon": {"name": "T700 3K twill carbon/epoxy plate (quasi-isotropic)", "E": 55_000.0,
               "flex_strength": 550.0, "design_allow": 450.0, "rho": 1.55e-3, "fill": 1.0,
               "Tg_std": 120.0, "Tg_high": 180.0},
    # printed in the XY plane (loads along the layers), 6 walls + 50 % gyroid; dry, annealed PA6-CF.
    # Allowable ~40 % of the dry flexural strength: covers moisture, layer lines, notches and fatigue.
    "pa_cf": {"name": "PA6-CF (nylon + carbon fibre), 3D printed", "E": 4_500.0,
              "flex_strength": 90.0, "design_allow": 35.0, "rho": 1.20e-3, "fill": 0.80, "hdt": 150.0},
    "al7075": {"name": "Aluminium 7075-T6", "E": 71_700.0, "yield": 503.0, "max_service_C": 120.0},
    "tpu": {"name": "TPU 95A", "max_service_C": 80.0},
    "nylon": {"name": "Nylon 66 standoffs", "max_service_C": 85.0},
}
CF = MAT[P.get("material", "carbon")]      # arm / frame material (printed PA-CF in this version)

# ---------------- weight: CAD frame + electronics catalogue from build.py -----------
COMPONENTS_G = {"frame + legs + mounts (from CAD)": data["checks"]["frame_mass_g"]}
COMPONENTS_G.update({f"{k}: {v['description']}": v["mass_g"] for k, v in data["components"].items()})
AUW_g = sum(COMPONENTS_G.values())
AUW_N = AUW_g / 1000 * g
MAX_THRUST_KGF = 2.2          # per motor, XING2 2809 1250KV 6S + 7" tri-blade (estimate - check iFlight table)
DESIGN_THRUST_N = 2.6 * g     # design case, above max thrust
MOTOR_TORQUE_NMM = 400.0      # reaction torque at full power
TIP_MASS_KG = 0.0607 + 0.011  # motor + prop
BATT_MAH = P["battery_mah"]

# ---------------- arm geometry ----------------------------------------------------
t = G["arm_t_mm"]
L = G["arm_free_len_mm"]
clamp = G["clamp_edge_mm"]
R = G["R_motor_mm"]
s0, wr, wt = P["arm_start"], P["arm_w_root"], P["arm_w_tip"]


def width(d):
    return wr - (wr - wt) * (d - s0) / (R - s0)


s = np.linspace(0, L, 2001)            # from clamp edge to motor centre
w = width(clamp + s)
I_out = w * t ** 3 / 12                # bending out of plane (thrust / landing)
I_in = t * w ** 3 / 12                 # bending in plane (side hit)
Z_out = w * t ** 2 / 6
Z_in = t * w ** 2 / 6


def tip_load_results(I, Z, F):
    Mx = F * (L - s)
    sigma = Mx / Z
    # unit-load method for tip deflection of the tapered cantilever
    defl = np.trapezoid(F * (L - s) ** 2 / (CF["E"] * I), s)
    return sigma, defl


# leg-bolt holes are the only holes outside the clamp: check the inner one (bigger moment)
d_foot = min(G["leg_bolts_mm"])
w_net_foot = width(d_foot) - 3.2
Z_out_foot = w_net_foot * t ** 2 / 6
arm_lever_foot = R - d_foot

res = {}

# LC1: design thrust (2.4 kgf) on one arm
sig, defl = tip_load_results(I_out, Z_out, DESIGN_THRUST_N)
sig_foot = DESIGN_THRUST_N * arm_lever_foot / Z_out_foot
res["LC1_full_thrust"] = {
    "load_N": round(DESIGN_THRUST_N, 1),
    "max_stress_MPa": round(float(sig.max()), 1),
    "stress_at_foot_hole_MPa": round(sig_foot, 1),
    "tip_deflection_mm": round(float(defl), 3),
    "safety_factor": round(CF["design_allow"] / float(sig.max()), 1),
}

# LC2: motor reaction torque -> torsion of the arm (rectangular section)
b_c, a_t = width(clamp), t
beta = 1 / 3 - 0.21 * (a_t / b_c) * (1 - (a_t / b_c) ** 4 / 12)
tau = MOTOR_TORQUE_NMM / (beta * b_c * a_t ** 2)
res["LC2_motor_torque"] = {"torque_Nmm": MOTOR_TORQUE_NMM, "shear_stress_MPa": round(tau, 2),
                           "safety_factor": round(0.5 * CF["design_allow"] / tau, 0)}

# LC3: vertical crash - whole drone stopped by ONE arm tip (worst case)
F_break_out = CF["design_allow"] * Z_out[0] / L
res["LC3_vertical_crash_one_arm"] = {
    "tip_force_to_reach_allowable_N": round(F_break_out, 0),
    "equivalent_g_whole_drone": round(F_break_out / AUW_N, 1),
}

# LC4: side hit (in-plane) - e.g. tree branch / gate post on the motor bell
F_break_in = CF["design_allow"] * Z_in[0] / L
res["LC4_side_hit_one_arm"] = {
    "tip_force_to_reach_allowable_N": round(F_break_in, 0),
    "equivalent_g_whole_drone": round(F_break_in / AUW_N, 1),
}

# Comparison with the 6 mm carbon arm of the earlier (cut-carbon) version, same plan shape
Zc = width(clamp) * 6.0 ** 2 / 6
F_carbon = MAT["carbon"]["design_allow"] * Zc / L
F_ult = CF["flex_strength"] * Z_out[0] / L
res["comparison_vs_carbon_arm"] = {
    "carbon_6mm_allowable_force_N": round(F_carbon, 0),
    "this_arm_allowable_force_N": round(F_break_out, 0),
    "this_arm_ultimate_force_N": round(F_ult, 0),
    "this_arm_ultimate_g": round(F_ult / AUW_N, 1),
    "stiffness_vs_carbon_pct": round(100 * CF["E"] * I_out[0] / (MAT["carbon"]["E"] * width(clamp) * 6.0 ** 3 / 12), 0),
}

# LC5: body standoffs - top deck (top plate + Pi + GPS mast + radio + BEC) side impact at 50 g,
# shared by 6 standoffs, fixed-fixed
CMP = data["components"]
deck_g = (M["top_plate"]["mass_total_g"] + M["gps_plate"]["mass_total_g"] + M["standoff_gps_m2x40"]["mass_total_g"]
          + M["standoff_rpi_m2_5x10"]["mass_total_g"]
          + sum(CMP[k]["mass_g"] for k in ("rpi", "gps", "telemetry", "ant_telemetry", "bec")))
F_side = deck_g / 1000 * 50 * g
d_o, d_i, Ls = 5.0 / math.cos(math.radians(30)) * 0.95, 2.5, P["standoff_len"]
Z_st = math.pi * (d_o ** 4 - d_i ** 4) / (32 * d_o)
sig_st = (F_side / 6) * Ls / 2 / Z_st
res["LC5_standoff_side_impact_50g"] = {"top_deck_g": round(deck_g, 0), "stress_MPa": round(sig_st, 1),
                                       "safety_factor": round(MAT["al7075"]["yield"] / sig_st, 1)}

# Vibration: first bending mode of one arm with motor + prop on the tip
k_out = DESIGN_THRUST_N / res["LC1_full_thrust"]["tip_deflection_mm"] * 1000  # N/m
m_arm_free = float(np.trapezoid(w * t, s)) * CF["rho"] * CF["fill"] / 1000      # kg
f1 = 1 / (2 * math.pi) * math.sqrt(k_out / (TIP_MASS_KG + 0.24 * m_arm_free))
# prop rotation frequencies (static thrust T = Ct*rho*n^2*D^4, Ct~0.11 for 7x4)
D = P["prop_d"] / 1000
n_hover = math.sqrt((AUW_N / 4) / (0.11 * 1.225 * D ** 4))
n_max = math.sqrt((MAX_THRUST_KGF * g) / (0.11 * 1.225 * D ** 4))
res["vibration"] = {"arm_first_bending_Hz": round(f1, 0), "arm_stiffness_N_per_mm": round(k_out / 1000, 1),
                    "prop_rotation_hover_Hz": round(n_hover, 0), "prop_rotation_max_Hz": round(n_max, 0)}

# LC6: landing legs (PA-CF), hard landing 5 g with 30 % side load, worst case one leg takes it all
leg_len = G["leg_len_mm"]
F_leg_side = 0.3 * 5 * AUW_N
Z_leg = math.pi * 14 ** 3 / 32  # root of the tapered leg, dia 14
sig_leg = F_leg_side * leg_len / Z_leg
res["LC6_leg_hard_landing"] = {"side_force_N": round(F_leg_side, 1), "stress_MPa": round(sig_leg, 1),
                               "safety_factor": round(MAT["pa_cf"]["flex_strength"] / sig_leg, 1)}

# Flight time (hover), 6S LiPo, 80 % usable, 7-inch hover efficiency ~8.5 g/W
AVIONICS_W = {"Raspberry Pi 5 (average)": 6.0, "VTX 400 mW": 4.0, "FC + GPS + RX + cameras": 2.5,
              "LoRa telemetry 1 W (duty-cycled)": 2.0}
hover_W = AUW_g / 8.5 + sum(AVIONICS_W.values())
usable_Wh = 22.2 * BATT_MAH / 1000 * 0.8
res["performance"] = {"AUW_g": round(AUW_g, 0), "thrust_to_weight": round(4 * MAX_THRUST_KGF * g / AUW_N, 1),
                      "hover_thrust_per_motor_g": round(AUW_g / 4, 0), "hover_power_W": round(hover_W, 0),
                      "avionics_W": sum(AVIONICS_W.values()),
                      "hover_flight_time_min": round(usable_Wh / hover_W * 60, 1)}

# ---------------- thermal ---------------------------------------------------------
PA = MAT["pa_cf"]
heat = [
    # component, worst-case temp C, material touching it, material limit C
    ("Motor base -> printed arm pad", 110, "PA6-CF (heat deflection temp.)", PA["hdt"]),
    ("Motor base -> arm pad, if printed in PET-CF", 110, "PET-CF (HDT ~ 80 C, not annealed)", 80.0),
    ("ESC stack -> printed clamp plate", 100, "PA6-CF (HDT)", PA["hdt"]),
    ("VTX -> printed bottom plate", 95, "PA6-CF (HDT)", PA["hdt"]),
    ("Standoffs (stack air)", 90, "Al 7075-T6", MAT["al7075"]["max_service_C"]),
    ("Raspberry Pi 5 board (cooler on)", 70, "Nylon 66 standoffs", MAT["nylon"]["max_service_C"]),
    ("Landing legs / feet", 60, "PA6-CF (HDT)", PA["hdt"]),
    ("Antenna mount", 60, "TPU 95A", MAT["tpu"]["max_service_C"]),
]
thermal_rows = [{"part": a, "worst_C": b, "material": c, "limit_C": d, "margin_C": d - b} for a, b, c, d in heat]

# dock lid in sun: surface rise = absorptivity * irradiance / h (still air, h~10 W/m2K)
G_sun, h_conv, T_amb = 1000.0, 10.0, 45.0
dock_sun = {f"{name} (alpha={a})": round(T_amb + a * G_sun / h_conv, 0)
            for name, a in (("white/silver lid", 0.25), ("grey lid", 0.6), ("black lid", 0.9))}

out = {"AUW_breakdown_g": COMPONENTS_G, "results": res, "thermal": thermal_rows,
       "dock_lid_surface_temp_C_at_45C_ambient": dock_sun, "materials": MAT}
(REP / "analysis.json").write_text(json.dumps(out, indent=2))

# ---------------- markdown report --------------------------------------------------
r = res
md = f"""# 7-inch FPV frame and dock: strength and heat check

Generated by `analysis/analysis.py` from the CAD model. All loads are applied to one arm,
cantilevered from the clamp-plate edge (free length **{L:.1f} mm**, arm **{t:.0f} mm** tall,
**{width(clamp):.1f} mm** wide at the clamp and tapering to {wt:.0f} mm at the motor).
Frame material: **{CF['name']}**, E = {CF['E'] / 1000:.1f} GPa, design allowable **{CF['design_allow']:.0f} MPa**
(dry flexural strength about {CF['flex_strength']:.0f} MPa).

## Weight and performance (assumed electronics)
| Item | g |
|---|---|
""" + "\n".join(f"| {k} | {v:.0f} |" for k, v in COMPONENTS_G.items()) + f"""
| **All-up weight** | **{AUW_g:.0f}** |

Thrust-to-weight at {MAX_THRUST_KGF} kgf per motor: **{r['performance']['thrust_to_weight']}:1**.
Hover power is about {r['performance']['hover_power_W']:.0f} W, of which {r['performance']['avionics_W']:.0f} W is avionics (Pi, VTX, radios).
Estimated hover time on the 6S {BATT_MAH} mAh pack: **≈{r['performance']['hover_flight_time_min']} min**
(forward cruise is usually 10–20 % longer than hover, and aggressive flying is much shorter).

Centre of gravity (from CAD, every part at its real position): **{data['checks']['cg_mm']['offset_from_centre_mm']} mm**
from the frame centre, {data['checks']['cg_mm']['below_prop_plane_mm']} mm below the prop plane.

## Load cases
| Case | Result | Safety factor |
|---|---|---|
| LC1 full thrust, {r['LC1_full_thrust']['load_N']} N per arm | max stress {r['LC1_full_thrust']['max_stress_MPa']} MPa, tip deflection {r['LC1_full_thrust']['tip_deflection_mm']} mm | **{r['LC1_full_thrust']['safety_factor']}** |
| LC2 motor reaction torque {MOTOR_TORQUE_NMM:.0f} N·mm | shear {r['LC2_motor_torque']['shear_stress_MPa']} MPa | **{r['LC2_motor_torque']['safety_factor']:.0f}** |
| LC3 vertical crash, drone stopped by one arm tip | arm reaches allowable at {r['LC3_vertical_crash_one_arm']['tip_force_to_reach_allowable_N']:.0f} N | survives **{r['LC3_vertical_crash_one_arm']['equivalent_g_whole_drone']} g** |
| LC4 side hit on motor (in-plane) | arm reaches allowable at {r['LC4_side_hit_one_arm']['tip_force_to_reach_allowable_N']:.0f} N | survives **{r['LC4_side_hit_one_arm']['equivalent_g_whole_drone']} g** |
| LC5 body standoffs, {r['LC5_standoff_side_impact_50g']['top_deck_g']:.0f} g top deck (Pi, GPS, radio) side impact at 50 g | {r['LC5_standoff_side_impact_50g']['stress_MPa']} MPa in 7075 | **{r['LC5_standoff_side_impact_50g']['safety_factor']}** |
| LC6 one landing leg, 5 g hard landing with 30 % side load | {r['LC6_leg_hard_landing']['stress_MPa']} MPa in PA6-CF | **{r['LC6_leg_hard_landing']['safety_factor']}** |

Compared with the 6 mm carbon arm of the earlier cut-carbon version: the printed arm has
**{r['comparison_vs_carbon_arm']['stiffness_vs_carbon_pct']:.0f} %** of its bending stiffness and reaches its design allowable at
{r['comparison_vs_carbon_arm']['this_arm_allowable_force_N']:.0f} N (carbon: {r['comparison_vs_carbon_arm']['carbon_6mm_allowable_force_N']:.0f} N).
Printed PA-CF bends and cracks rather than shattering; it reaches its dry strength at about
{r['comparison_vs_carbon_arm']['this_arm_ultimate_force_N']:.0f} N (≈{r['comparison_vs_carbon_arm']['this_arm_ultimate_g']} g on one arm).
A printed arm is the part meant to break in a crash, and a spare costs about 40 g of filament.

## Vibration
* First bending frequency of the arm with the motor and prop on it: **{r['vibration']['arm_first_bending_Hz']:.0f} Hz**
  (arm stiffness {r['vibration']['arm_stiffness_N_per_mm']} N/mm)
* Prop rotation: ~{r['vibration']['prop_rotation_hover_Hz']:.0f} Hz at hover, ~{r['vibration']['prop_rotation_max_Hz']:.0f} Hz at full throttle

The arm mode sits inside the motor's speed range. That is true of every 7-inch frame. Enable RPM-tracking
notch filters (ArduPilot: harmonic notch with ESC telemetry / bidirectional DShot; Betaflight: RPM filter),
soft-mount the FC stack on its grommets, and check a log after the first hover.

## Heat
| Part | Worst-case °C | Material | Limit °C | Margin °C |
|---|---|---|---|---|
""" + "\n".join(f"| {x['part']} | {x['worst_C']} | {x['material']} | {x['limit_C']:.0f} | {x['margin_C']:.0f} |"
                for x in thermal_rows) + """

**Print the arms, plates and legs in PA6-CF (PA-CF), dried before printing and ideally annealed.** It keeps its
shape well above the hottest motor. **Do not use PET-CF for the arms**: un-annealed PET-CF softens at about 80 °C,
below the 110 °C a hot motor base can reach. PET-CF is fine for the camera plates, tray and GPS plate.

Dock cover surface temperature in full sun at 45 °C ambient (no wind):
""" + "\n".join(f"* {k}: **{v:.0f} °C**" for k, v in dock_sun.items()) + """

A LiPo must stay under about 60 °C, so use **white / opal twin-wall polycarbonate covers**, keep the
electronics bay ventilated, and let the dock controller stop charging above 45 °C (it does). Print the dock
parts in ASA or PETG, not PLA.

## Limits of this check
* These are beam-theory hand calculations; `analysis/fea.py` runs the 3D finite-element version of the arm,
  including the stress peaks at the holes.
* Printed parts depend on the printer, filament dryness and settings: print a test arm and break it before you trust
  the numbers, and keep the layer lines along the arm (print flat).
* No frame is unbreakable. A 30 m/s crash into concrete carries about 400 J. This design makes the arms the
  cheap part that fails first, protecting the stack and camera, and each arm can be replaced on its own.
"""
(REP / "analysis_report.md").write_text(md, encoding="utf-8")
print(json.dumps(res, indent=2))
