"""
One complete dock-to-dock flight, run on the Pi 5 next to precision_landing.py.

  1. dock.launch()      stop charging, open covers, park pushers (waits for ready_for_takeoff)
  2. arm + take off     GUIDED, climb to TAKEOFF_ALT
  3. fly                AUTO mission already uploaded from Mission Planner / QGroundControl
                        (end the mission with RETURN_TO_LAUNCH; the dock is the home position)
  4. land               RTL lands with precision landing on the marker (PLND_ENABLED = 1)
  5. dock.dock()        after disarm: centre the drone, close covers, start charging

Run:  python mission.py --mav /dev/ttyAMA0 --dock http://drone-dock.local --token change-me
Safety: keep a pilot with the ELRS radio ready to take over; check local drone laws before flying BVLOS.
"""
import argparse
import time

from pymavlink import mavutil

from dock_client import Dock

TAKEOFF_ALT = 15.0


def set_mode(m, mode):
    m.set_mode(m.mode_mapping()[mode])
    while True:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=5)
        if hb and mavutil.mode_string_v10(hb) == mode:
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mav", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--dock", default="http://drone-dock.local")
    ap.add_argument("--token", default="change-me")
    a = ap.parse_args()

    dock = Dock(a.dock, a.token)
    m = mavutil.mavlink_connection(a.mav, baud=a.baud, source_system=1, source_component=191)
    m.wait_heartbeat()

    print("dock:", dock.launch())
    set_mode(m, "GUIDED")
    m.arducopter_arm()
    m.motors_armed_wait()
    m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                            0, 0, 0, 0, 0, 0, 0, TAKEOFF_ALT)
    while True:
        msg = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=5)
        if msg and msg.relative_alt / 1000.0 > TAKEOFF_ALT * 0.9:
            break
    print("airborne, starting AUTO mission")
    set_mode(m, "AUTO")
    m.motors_disarmed_wait()                 # mission ends with RTL -> precision landing -> auto disarm
    time.sleep(3)
    print("landed, docking:", dock.dock())


if __name__ == "__main__":
    main()
