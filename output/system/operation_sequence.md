# How the dock system works

## Take-off
1. The Pi (or your laptop) calls `POST /launch` on the dock (`companion/dock_client.py`).
2. The dock stops charging, opens both covers (each flips 180 deg outward and hangs beside the body, about
   12 s) and parks the pushers at 260 mm from the centre. `/status` then reports `ready_for_takeoff`.
3. The drone arms and climbs straight up. Nothing is around the props: the closest dock part is
   71.89 mm away and the take-off column (424 mm square) is empty.

## Landing and docking
1. The mission ends with RTL to the dock. ArduPilot precision landing (PLND) follows the 130 mm ArUco marker in the
   middle of the deck, using the downward Pi Camera 3 (`companion/precision_landing.py`).
2. The pushers catch the drone if it lands within **155 mm** of the centre
   (≥ 117 mm at the worst 45-degree yaw).
3. After disarm the Pi calls `POST /dock`: the X pushers then the Y pushers slide the legs to the centre and
   square the yaw; the four feet end up on the four copper pads.
4. The covers close (the drone is held by the pushers while they move), then charging starts.

## Charging
* The dock's 25.2 V CC/CV charger feeds the pads through a relay and a current monitor.
* On the drone the four foot contacts go to an ideal-diode bridge (any polarity, so any of the four square
  yaws works), a fuse and a 6S BMS that balances the cells.
* The controller stops charging when the current falls below 0.3 A (full), above 45 °C, above 25.4 V,
  after 2 h, or if no current flows (feet not on the pads).

## Safety interlocks (firmware)
* The covers never move while the pushers move, and the reverse.
* Every motion has a timeout; the e-stop button or `POST /stop` switches all motors and charging off.
* After any fault the pushers re-home before anything else moves.

## HTTP API (header `X-Token`)
| Call | Does |
|---|---|
| `GET /status` | JSON: cover, pusher, charge state, volts, amps, temperatures, ready_for_takeoff |
| `POST /launch` | stop charge, open, park pushers |
| `POST /dock` | centre, close, charge |
| `POST /open`, `/close`, `/center`, `/release` | single steps |
| `POST /charge/start`, `/charge/stop`, `/home`, `/stop`, `/reset` | |
