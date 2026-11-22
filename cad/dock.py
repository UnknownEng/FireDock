"""
Flat-top drone dock: the landing deck IS the top of the dock, so nothing ever surrounds the props.

  closed  two half covers (twin-wall polycarbonate shells) close over the drone
  open    each cover flips 180 deg outward on a motorised hinge and hangs beside the body
  centre  after landing, two pairs of pusher bars slide the drone's legs to the centre:
          X pair low (deck + 10..25 mm), Y pair high (deck + 29..44 mm) so they pass over each other.
          Each bar rides on two MGN12 carriages; each side has its own GT2 belt + NEMA17 (4 steppers,
          driven in step like a dual-Z 3D printer), one bar clamped to each run of the belt loop.
          Pushing two legs with a straight bar also squares the drone's yaw to the nearest 90 degrees.
  charge  the four feet then stand on four contact pads (+ - + - on the diagonals); the drone's
          ideal-diode bridge accepts either polarity, so all four 90-degree landing yaws charge.

Body: 2020 aluminium extrusion frame + 3 mm aluminium-composite (ACM) panels. Deck: 10 mm ACM or HDPE.
Every printed part fits a 256 x 256 x 256 mm bed (print the dock parts in PETG or ASA: they live outdoors).
Units mm. Origin = dock centre on the ground, X / Y the same as the drone, Z up.
"""
import cadquery as cq

V, L = cq.Vector, cq.Location

D = dict(
    half=365.0,           # body frame half size (730 x 730)
    body_h=300.0,         # ground -> top of the 2020 frame
    ext=20.0,             # 2020 extrusion
    panel_t=3.0,          # ACM side panels
    deck_t=10.0,
    rail_c=318.0,         # MGN12 rail centre line, from the dock centre
    rail_end=(-300.0, 310.0),
    rail_w=12.0, rail_h=8.0,
    car_w=27.0, car_l=45.4, car_h=13.0, car_gap=3.0,   # MGN12H carriage (height from rail bottom)
    belt_c=342.0,         # GT2 belt loop: pulley axis line
    pulley_r=6.37,        # GT2 20T pitch radius
    pulley_d=16.0,        # flange diameter
    belt_z=(9.0, 15.0),   # 6 mm belt, height above the deck
    motor_end=310.0,      # stepper (drive pulley) position along its side
    idler_end=300.0,
    nema=42.3, nema_h=40.0,
    bar=15.0,             # 15 x 15 aluminium square tube
    bar_half_len=302.0,
    x_bar_z=10.0,         # X pushers: bottom above the deck
    y_bar_z=29.0,         # Y pushers: pass over the X pushers
    park=260.0,           # pusher centre line from the dock centre when parked
    cover_reach=385.0,    # each half cover: x 2..385, y -385..385
    cover_h=255.0,
    cover_t=6.0,          # twin-wall polycarbonate
    skirt=15.0,           # cover edge below the deck top (rain lip)
    hinge=(400.0, 279.0), # hinge axis (x, z), along Y
    shaft_d=8.0,
    marker=130.0,         # ArUco / AprilTag for precision landing (fits between the 4 contact pads)
    contact=40.0,
    foot_xy=91.92,        # drone foot position after centering (leg at 130 mm on the 45 deg arms)
)
H = D["half"]
Z_DECK = D["body_h"] + D["deck_t"]          # top surface of the landing deck
XH, ZH = D["hinge"]
COVER_BOTTOM = Z_DECK - D["skirt"]
Y_MOTOR = -D["cover_reach"] - 30.0           # inner face of the cover worm-gear motors (outside the -Y end)

COL = {"alu": (0.75, 0.76, 0.78), "panel": (0.93, 0.93, 0.9), "deck": (0.96, 0.96, 0.95),
       "rail": (0.55, 0.57, 0.6), "steel": (0.6, 0.6, 0.62), "print": (0.95, 0.45, 0.1), "cover": (0.75, 0.85, 0.95),
       "motor": (0.15, 0.15, 0.17), "belt": (0.1, 0.1, 0.1), "copper": (0.85, 0.5, 0.25), "pcb": (0.1, 0.45, 0.2),
       "psu": (0.7, 0.7, 0.72), "marker": (0.05, 0.05, 0.05)}
I = L(V(0, 0, 0))


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_y(r, y0, y1, x, z):
    return cq.Workplane("XZ").center(x, z).circle(r).extrude(-(y1 - y0)).translate((0, y0, 0))


def cyl_z(r, z0, z1, x, y):
    return cq.Workplane("XY").center(x, y).circle(r).extrude(z1 - z0).translate((0, 0, z0))


def union_all(parts):
    out = parts[0]
    for p in parts[1:]:
        out = out.union(p)
    return out


def rz(deg):
    return L(V(0, 0, 0), V(0, 0, 1), deg)


# --------------------------------------------------------------------------------- body (cut / bought)
def make_frame():
    e, h, top = D["ext"], H, D["body_h"]
    parts = []
    for z0 in (0.0, top - e):
        parts += [box(-h, h, h - e, h, z0, z0 + e), box(-h, h, -h, -h + e, z0, z0 + e),
                  box(h - e, h, -h + e, h - e, z0, z0 + e), box(-h, -h + e, -h + e, h - e, z0, z0 + e)]
    for x0 in (h - e, -h):
        for y0 in (h - e, -h):
            parts.append(box(x0, x0 + e, y0, y0 + e, e, top - e))
    parts.append(box(-e / 2, e / 2, -h + e, h - e, top - e, top))          # deck support across the middle
    return union_all(parts)


def make_panels():
    t, h, top = D["panel_t"], H, D["body_h"]
    return union_all([box(h, h + t, -h - t, h + t, 0, top), box(-h - t, -h, -h - t, h + t, 0, top),
                      box(-h, h, h, h + t, 0, top), box(-h, h, -h - t, -h, 0, top),
                      box(-h + 20, h - 20, -h + 20, h - 20, 20, 23)])                # floor


def make_deck():
    d = box(-H, H, -H, H, D["body_h"], Z_DECK)
    c, s = D["contact"], D["foot_xy"]
    for sx in (1, -1):
        for sy in (1, -1):
            d = d.cut(box(sx * s - c / 2, sx * s + c / 2, sy * s - c / 2, sy * s + c / 2, Z_DECK - 1.5, Z_DECK + 1))
            d = d.cut(cyl_z(3.0, D["body_h"] - 1, Z_DECK, sx * s, sy * s))     # contact wire
    m = D["marker"] / 2
    return d.cut(box(-m, m, -m, m, Z_DECK - 0.5, Z_DECK + 1))


def contact_pads():
    c, s = D["contact"] / 2 - 0.2, D["foot_xy"]
    return [box(sx * s - c, sx * s + c, sy * s - c, sy * s + c, Z_DECK - 1.5, Z_DECK)
            for sx in (1, -1) for sy in (1, -1)]


def make_marker():
    m = D["marker"] / 2 - 0.2
    return box(-m, m, -m, m, Z_DECK - 0.5, Z_DECK)


# --------------------------------------------------------------------------------- centering mechanism
def rail(axis, side):
    """MGN12 rail. axis 'x': runs along X at y = side*rail_c; 'y': along Y at x = side*rail_c."""
    a0, a1 = D["rail_end"]
    w, c = D["rail_w"] / 2, side * D["rail_c"]
    if axis == "x":
        return box(a0, a1, c - w, c + w, Z_DECK, Z_DECK + D["rail_h"])
    return box(c - w, c + w, a0, a1, Z_DECK, Z_DECK + D["rail_h"])


def carriage(axis, side, pos):
    w, l2, c = D["car_w"] / 2, D["car_l"] / 2, side * D["rail_c"]
    z0, z1 = Z_DECK + D["car_gap"], Z_DECK + D["car_h"]
    rw, rh = D["rail_w"] / 2 + 0.3, Z_DECK + D["rail_h"] + 0.3
    if axis == "x":
        return box(pos - l2, pos + l2, c - w, c + w, z0, z1).cut(box(pos - l2 - 1, pos + l2 + 1, c - rw, c + rw, z0 - 1, rh))
    return box(c - w, c + w, pos - l2, pos + l2, z0, z1).cut(box(c - rw, c + rw, pos - l2 - 1, pos + l2 + 1, z0 - 1, rh))


def make_bar_bracket(high, outer_run):
    """Printed bracket, modelled for an X-pusher end on the +Y side: bar along Y at x=0, carriage at (0, rail_c).
    Holds the bar end in a socket, sits on the carriage (4x M3) and clamps one run of the belt."""
    rc, w, b = D["rail_c"], D["car_w"] / 2, D["bar"]
    bz = Z_DECK + (D["y_bar_z"] if high else D["x_bar_z"])
    zc0, zc1 = Z_DECK + D["car_h"], Z_DECK + D["car_h"] + 8
    plate = box(-D["car_l"] / 2, D["car_l"] / 2, rc - w, rc + w, zc0, zc1)
    sock = box(-b / 2 - 3, b / 2 + 3, rc - w - 16.5, rc - w, min(bz - 3, zc0), max(bz + b + 3, zc1))
    sock = sock.cut(box(-b / 2 - 0.15, b / 2 + 0.15, rc - w - 17, rc - w - 2, bz - 0.15, bz + b + 0.15))
    br = plate.union(sock)
    run_y = D["belt_c"] + (D["pulley_r"] if outer_run else -D["pulley_r"])
    bz0, bz1 = Z_DECK + D["belt_z"][0] - 2, Z_DECK + D["belt_z"][1] + 2
    if outer_run:
        br = br.union(box(-8, 8, rc + w, run_y + 3, zc0 + 4, zc1))                  # bridge over the inner run
        br = br.union(box(-8, 8, run_y - 2.5, run_y + 3, bz0, zc1))
    else:
        br = br.union(box(-8, 8, rc + w, run_y + 2.5, bz0, zc1))
    br = br.cut(box(-8.5, 8.5, run_y - 0.8, run_y + 0.8, bz0 + 2, bz1 - 2))        # belt slot (teeth grip)
    for x in (-10.0, 10.0):                                                          # M3 into the carriage
        for y in (rc - 10.0, rc + 10.0):
            br = br.cut(cyl_z(1.65, zc0 - 1, zc1 + 1, x, y))
    return br


def make_bar():
    b, hl = D["bar"], D["bar_half_len"]
    return box(-b / 2, b / 2, -hl, hl, 0, b).cut(box(-b / 2 + 1.5, b / 2 - 1.5, -hl - 1, hl + 1, 1.5, b - 1.5))


def make_stepper_bracket():
    """Printed: holds a NEMA17 shaft-down above its drive pulley. Local: pulley axis at (0,0), deck top at z=0.
    Legs on local +X (away from the belt) and +Y (outer edge)."""
    n = D["nema"] / 2
    top = box(-n - 2, n + 2, -n - 2, n + 2, 18, 22).cut(cyl_z(11.5, 17, 23, 0, 0))
    for sx in (1, -1):
        for sy in (1, -1):
            top = top.cut(cyl_z(1.7, 17, 23, sx * 15.5, sy * 15.5))
    return top.union(box(-n - 2, n + 2, n - 4, n + 2, 0, 18)).union(box(n - 4, n + 2, -n - 2, n + 2, 0, 18))


def make_idler_post():
    """Printed: two flanged bearings on an M5 bolt turn the belt at the idler end. Open toward local -X."""
    p = union_all([box(-10, 14, -11, 11, 0, 6), box(9, 14, -11, 11, 0, 24), box(-10, 14, -11, 11, 20, 24)])
    return p.cut(cyl_z(2.6, -1, 25, 0, 0))


def ref_nema():
    n = D["nema"] / 2
    return box(-n, n, -n, n, 22, 22 + D["nema_h"]).union(cyl_z(2.5, 17.5, 22, 0, 0))


def ref_pulley():
    """GT2 20T pulley / idler: toothed core under the belt + a flange above and below it."""
    z0, z1 = D["belt_z"]
    core = cyl_z(D["pulley_r"] - 0.75, z0 - 2, z1 + 2, 0, 0)
    return core.union(cyl_z(D["pulley_d"] / 2, z0 - 2, z0 - 0.5, 0, 0)).union(cyl_z(D["pulley_d"] / 2, z1 + 0.5, z1 + 2, 0, 0))


def belt_ends(axis, side):
    """(drive end, idler end) along the belt. X system: motor at +side end; Y system: motor at -side end."""
    if axis == "x":
        return side * D["motor_end"], -side * D["idler_end"]
    return -side * D["motor_end"], side * D["idler_end"]


def belt_runs(axis, side):
    """The two straight runs of a belt loop as thin strips."""
    c, r = side * D["belt_c"], D["pulley_r"]
    a0, a1 = sorted(belt_ends(axis, side))
    z0, z1 = Z_DECK + D["belt_z"][0], Z_DECK + D["belt_z"][1]
    if axis == "x":
        return [box(a0, a1, c + off - 0.7, c + off + 0.7, z0, z1) for off in (-r, r)]
    return [box(c + off - 0.7, c + off + 0.7, a0, a1, z0, z1) for off in (-r, r)]


# --------------------------------------------------------------------------------- covers + hinges
def make_cover():
    """Right half cover in its CLOSED position (absolute coordinates): top, outer wall, two end walls."""
    r, t, z0 = D["cover_reach"], D["cover_t"], COVER_BOTTOM
    z1 = z0 + D["cover_h"]
    return box(2, r, -r, r, z0, z1).cut(box(-1, r - t, -r + t, r - t, z0 - 1, z1 - t))


def make_cover_corner():
    """Printed 3-sided cap over a top outer corner of the cover panels, modelled at (+X, +Y)."""
    r, z1 = D["cover_reach"], COVER_BOTTOM + D["cover_h"]
    return box(r - 40, r + 3, r - 40, r + 3, z1 - 40, z1 + 3).cut(box(r - 41, r, r - 41, r, z1 - 41, z1))


def make_hinge_arm():
    """Printed arm joining a cover end wall to the hinge shaft (closed, +Y end, absolute coordinates)."""
    r = D["cover_reach"]
    arm = box(r - 22, XH + 12, r, r + 10, ZH - 12, COVER_BOTTOM + 55)
    arm = arm.cut(cyl_y(D["shaft_d"] / 2 + 0.15, r - 1, r + 11, XH, ZH))
    return arm.cut(box(r - 16, r - 6, r - 1, r + 11, COVER_BOTTOM + 10, COVER_BOTTOM + 45))   # lightening slot


def make_shaft():
    return cyl_y(D["shaft_d"] / 2, Y_MOTOR, D["cover_reach"] + 12, XH, ZH)


def make_bearing_block():
    """Printed pillow block with a 608 bearing, bolted to the body side; stays below the cover edge."""
    blk = box(H + D["panel_t"], XH + 13, -10, 10, ZH - 30, COVER_BOTTOM - 2)
    return blk.cut(cyl_y(11.1, -4, 4, XH, ZH)).cut(cyl_y(D["shaft_d"] / 2 + 0.5, -11, 11, XH, ZH))


def ref_cover_motor():
    """12 V worm-gear motor (>= 7 N*m), output coaxial with the hinge shaft, outside the -Y end of the cover."""
    gear = box(XH - 23, XH + 23, Y_MOTOR - 65, Y_MOTOR, ZH - 24, ZH + 24)
    can = cq.Workplane("YZ").center(Y_MOTOR - 32.5, ZH).circle(18.5).extrude(70).translate((XH + 23, 0, 0))
    return gear.union(can)


def make_coupler():
    return cyl_y(10, Y_MOTOR, Y_MOTOR + 15, XH, ZH).cut(cyl_y(D["shaft_d"] / 2, Y_MOTOR - 1, Y_MOTOR + 16, XH, ZH))


def make_cover_motor_bracket():
    """Printed: carries the worm-gear motor and reaches back to the body BELOW the hinge-arm sweep."""
    y0, y1 = Y_MOTOR - 65, Y_MOTOR
    seat = box(XH - 27, XH + 27, y0, y1, ZH - 30, ZH - 24)
    post = box(XH - 27, XH - 19, y0, y1, 180, ZH - 30)
    foot = box(H - 60, XH - 19, y0, -H - D["panel_t"], 180, 190)
    face = box(H - 60, H - 5, -H - D["panel_t"] - 6, -H - D["panel_t"], 150, 230)
    return union_all([seat, post, foot, face])


# --------------------------------------------------------------------------------- electronics (bought)
def ref_electronics():
    z = 23.0
    return {
        "psu_24v": (box(-300, -85, -320, -205, z, z + 50), "psu", "24 V 10 A (240 W) enclosed PSU, 215x115x50 mm"),
        "controller": (box(-60, 100, -320, -220, z, z + 30), "pcb",
                       "ESP32 DevKit + 4x TMC2209 + 2x DRV8871 on a 160x100 carrier board"),
        "charger": (box(120, 220, -320, -260, z, z + 30), "pcb", "6S CC/CV charger module, 25.2 V 4 A"),
        "power_board": (box(-300, -180, -180, -120, z, z + 30), "pcb",
                        "24->12 V buck, 24->5 V buck, fuses, charge relay, terminal blocks"),
    }


# --------------------------------------------------------------------------------- catalogue + assembly
# name -> (factory, material, qty, note)
PRINT_PARTS = {
    "dock_bar_bracket_low_inner": (lambda: make_bar_bracket(False, False), "petg", 2, "X pusher end, -X bar (inner belt run)"),
    "dock_bar_bracket_low_outer": (lambda: make_bar_bracket(False, True), "petg", 2, "X pusher end, +X bar (outer belt run)"),
    "dock_bar_bracket_high_inner": (lambda: make_bar_bracket(True, False), "petg", 2, "Y pusher end, -Y bar"),
    "dock_bar_bracket_high_outer": (lambda: make_bar_bracket(True, True), "petg", 2, "Y pusher end, +Y bar"),
    "dock_stepper_bracket": (make_stepper_bracket, "petg", 4, "NEMA17 above each drive pulley"),
    "dock_idler_post": (make_idler_post, "petg", 4, "belt idler: 2x F625 flanged bearings on M5"),
    "dock_hinge_arm": (make_hinge_arm, "petg", 4, "cover to hinge shaft (print 2, and 2 mirrored)"),
    "dock_bearing_block": (make_bearing_block, "petg", 4, "608 pillow block on the body side"),
    "dock_coupler": (make_coupler, "petg", 2, "worm motor to hinge shaft"),
    "dock_motor_bracket": (make_cover_motor_bracket, "petg", 2, "worm motor mount (print 1, and 1 mirrored)"),
    "dock_cover_corner": (make_cover_corner, "petg", 4, "corner cap of the cover panels (print 2, and 2 mirrored)"),
}
CUT_PARTS = {
    "dock_frame": (make_frame, "al6063", 1, "2020 extrusion frame (cut list in the BOM)"),
    "dock_panels": (make_panels, "acm", 1, "3 mm ACM side panels + floor"),
    "dock_deck": (make_deck, "acm", 1, "10 mm ACM/HDPE landing deck 730x730 with contact + marker recesses"),
    "dock_cover": (make_cover, "pc", 2, "6 mm twin-wall polycarbonate shell (top, outer side, 2 ends)"),
    "dock_bar": (make_bar, "al6063", 4, "15x15x1.5 aluminium square tube, 604 mm"),
    "dock_shaft": (make_shaft, "steel", 2, "8 mm steel hinge shaft, 812 mm"),
}


def bar_stop(leg_r_at, bar_z):
    """Pusher centre line when it touches the legs: leg cone radius at the bar's top edge + half the bar."""
    return D["foot_xy"] + leg_r_at(bar_z + D["bar"]) + D["bar"] / 2 + 0.3


def about_hinge(side, deg):
    """Rotate a right-side part about its hinge by deg (0 closed, 180 open); side=-1 = left (mirrored by 180 deg)."""
    if side > 0:
        return L(V(XH, 0, ZH), V(0, 1, 0), deg) * L(V(-XH, 0, -ZH))
    return L(V(-XH, 0, ZH), V(0, 1, 0), -deg) * L(V(XH, 0, -ZH)) * rz(180)


def build_shapes():
    S = {n: f().val() for n, (f, *_rest) in {**PRINT_PARTS, **CUT_PARTS}.items()}
    S["nema"] = ref_nema().val()
    S["pulley"] = ref_pulley().val()
    S["cover_motor"] = ref_cover_motor().val()
    S["marker"] = make_marker().val()
    S["hinge_arm_m"] = S["dock_hinge_arm"].mirror("XZ")
    S["cover_corner_m"] = S["dock_cover_corner"].mirror("XZ")
    return S


def items(S, cover_deg=0.0, bar_x=None, bar_y=None):
    """Dock parts as (name, shape, Location, colour, is_reference). bar_x / bar_y: pusher centre lines."""
    bx = D["park"] if bar_x is None else bar_x
    by = D["park"] if bar_y is None else bar_y
    it = [("dock_frame", S["dock_frame"], I, COL["alu"], False),
          ("dock_panels", S["dock_panels"], I, COL["panel"], False),
          ("dock_deck", S["dock_deck"], I, COL["deck"], False),
          ("dockREF_marker", S["marker"], I, COL["marker"], True)]
    it += [(f"dockREF_contact_pad_{i}", p.val(), I, COL["copper"], True) for i, p in enumerate(contact_pads())]
    for side in (1, -1):
        sg = f"{side:+d}"
        for axis in ("x", "y"):
            it.append((f"dockREF_rail_{axis}{sg}", rail(axis, side).val(), I, COL["rail"], True))
            it += [(f"dockBELT_{axis}{sg}_{k}", r.val(), I, COL["belt"], True) for k, r in enumerate(belt_runs(axis, side))]
        # X system belts on y = side*belt_c, Y system belts on x = side*belt_c
        (mx, ix), c = belt_ends("x", side), side * D["belt_c"]
        it += [(f"dockREF_nema_x{sg}", S["nema"], L(V(mx, c, Z_DECK)), COL["motor"], True),
               (f"dockREF_pulley_x{sg}", S["pulley"], L(V(mx, c, Z_DECK)), COL["steel"], True),
               (f"dockREF_idler_x{sg}", S["pulley"], L(V(ix, c, Z_DECK)), COL["steel"], True),
               (f"dock_stepper_bracket_x{sg}", S["dock_stepper_bracket"], L(V(mx, c, Z_DECK)) * rz(0 if side > 0 else 180),
                COL["print"], False),
               (f"dock_idler_post_x{sg}", S["dock_idler_post"], L(V(ix, c, Z_DECK)) * rz(180 if side > 0 else 0),
                COL["print"], False)]
        (my, iy) = belt_ends("y", side)
        it += [(f"dockREF_nema_y{sg}", S["nema"], L(V(c, my, Z_DECK)), COL["motor"], True),
               (f"dockREF_pulley_y{sg}", S["pulley"], L(V(c, my, Z_DECK)), COL["steel"], True),
               (f"dockREF_idler_y{sg}", S["pulley"], L(V(c, iy, Z_DECK)), COL["steel"], True),
               (f"dock_stepper_bracket_y{sg}", S["dock_stepper_bracket"], L(V(c, my, Z_DECK)) * rz(270 if side > 0 else 90),
                COL["print"], False),
               (f"dock_idler_post_y{sg}", S["dock_idler_post"], L(V(c, iy, Z_DECK)) * rz(90 if side > 0 else 270),
                COL["print"], False)]
    # pushers: X bars (along Y) at x = +-bx, Y bars (along X) at y = +-by; a bracket + carriage at each end
    for s in (1, -1):
        run = "outer" if s > 0 else "inner"
        sg = f"{s:+d}"
        for side in (1, -1):
            e = f"{side:+d}"
            it.append((f"dock_bar_bracket_low_{run}_x{sg}{e}", S[f"dock_bar_bracket_low_{run}"],
                       L(V(s * bx, 0, 0)) * rz(0 if side > 0 else 180), COL["print"], False))
            it.append((f"dockREF_carriage_x{sg}{e}", carriage("x", side, s * bx).val(), I, COL["steel"], True))
            it.append((f"dock_bar_bracket_high_{run}_y{sg}{e}", S[f"dock_bar_bracket_high_{run}"],
                       L(V(0, s * by, 0)) * rz(270 if side > 0 else 90), COL["print"], False))
            it.append((f"dockREF_carriage_y{sg}{e}", carriage("y", side, s * by).val(), I, COL["steel"], True))
        it.append((f"dock_bar_x{sg}", S["dock_bar"], L(V(s * bx, 0, Z_DECK + D["x_bar_z"])), COL["alu"], False))
        it.append((f"dock_bar_y{sg}", S["dock_bar"], L(V(0, s * by, Z_DECK + D["y_bar_z"])) * rz(90), COL["alu"], False))
    # covers (rotate), hinge parts and motors (static)
    for side in (1, -1):
        rot, static = about_hinge(side, cover_deg), about_hinge(side, 0.0)
        tag = "R" if side > 0 else "L"
        it.append((f"dockCOVER_{tag}", S["dock_cover"], rot, COL["cover"], False))
        it.append((f"dockCOVER_arm_{tag}+", S["dock_hinge_arm"], rot, COL["print"], False))
        it.append((f"dockCOVER_arm_{tag}-", S["hinge_arm_m"], rot, COL["print"], False))
        it.append((f"dockCOVER_corner_{tag}+", S["dock_cover_corner"], rot, COL["print"], False))
        it.append((f"dockCOVER_corner_{tag}-", S["cover_corner_m"], rot, COL["print"], False))
        it.append((f"dock_shaft_{tag}", S["dock_shaft"], static, COL["steel"], False))
        for y in (-300.0, 300.0):
            it.append((f"dock_bearing_block_{tag}{int(y):+d}", S["dock_bearing_block"], static * L(V(0, y, 0)),
                       COL["print"], False))
        it.append((f"dock_coupler_{tag}", S["dock_coupler"], static, COL["print"], False))
        it.append((f"dock_motor_bracket_{tag}", S["dock_motor_bracket"], static, COL["print"], False))
        it.append((f"dockREF_cover_motor_{tag}", S["cover_motor"], static, COL["motor"], True))
    for n, (f, col, _) in ref_electronics().items():
        it.append((f"dockREF_elec_{n}", f.val(), I, COL[col], True))
    return it
