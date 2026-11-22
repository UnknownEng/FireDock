"""
Precision landing on the dock: the downward Pi Camera Module 3 finds the ArUco marker in the centre of the
deck and streams MAVLink LANDING_TARGET messages to ArduPilot (PLND_TYPE = 1, MAVLink).

Marker: ArUco DICT_4X4_50, id 0, 130 mm black square (print it, stick it in the recess in the deck).
Camera: calibrate once (cv2 chessboard calibration) and put the numbers in camera_calib.npz; the defaults
below are rough values for the Camera Module 3 at 1280x720.

Run on the Pi 5:   python precision_landing.py --mav /dev/ttyAMA0 --baud 921600
(or --mav udpout:127.0.0.1:14550 when mavlink-router shares the FC link)
"""
import argparse
import math
import time
from pathlib import Path

import cv2
import numpy as np
from pymavlink import mavutil

MARKER_ID, MARKER_M = 0, 0.130
W, H = 1280, 720


def load_calibration():
    f = Path(__file__).with_name("camera_calib.npz")
    if f.exists():
        d = np.load(f)
        return d["K"], d["dist"]
    fx = fy = 1000.0          # approximate for Camera Module 3 (66 deg HFOV) at 1280x720
    return np.array([[fx, 0, W / 2], [0, fy, H / 2], [0, 0, 1]], float), np.zeros(5)


def open_camera():
    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        cam.configure(cam.create_video_configuration(main={"size": (W, H), "format": "RGB888"}))
        cam.start()
        return lambda: cam.capture_array()
    except ImportError:                       # fallback: any USB/V4L2 camera
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
        return lambda: cap.read()[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mav", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=921600)
    a = ap.parse_args()

    mav = mavutil.mavlink_connection(a.mav, baud=a.baud, source_system=1, source_component=197)
    mav.wait_heartbeat()
    print("FC heartbeat, sending LANDING_TARGET")
    K, dist = load_calibration()
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
                                       cv2.aruco.DetectorParameters())
    half = MARKER_M / 2
    obj = np.array([[-half, half, 0], [half, half, 0], [half, -half, 0], [-half, -half, 0]], np.float32)
    grab = open_camera()
    while True:
        frame = grab()
        if frame is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)
        if ids is None or MARKER_ID not in ids.flatten():
            continue
        c = corners[list(ids.flatten()).index(MARKER_ID)].reshape(4, 2).astype(np.float32)
        ok, rvec, tvec = cv2.solvePnP(obj, c, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)
        if not ok:
            continue
        x, y, z = tvec.flatten()                         # camera frame: x right, y down, z forward (= down)
        # camera mounted looking down, image top = drone nose -> body FRD: forward = -y, right = x
        angle_x = math.atan2(x, z)
        angle_y = math.atan2(y, z)
        size_x = 2 * math.atan2(half, z)
        mav.mav.landing_target_send(
            int(time.time() * 1e6), 0, mavutil.mavlink.MAV_FRAME_BODY_FRD,
            angle_x, angle_y, float(np.linalg.norm(tvec)), size_x, size_x)


if __name__ == "__main__":
    main()
