"""
Talk to the dock controller (ESP32) over Wi-Fi.

    from dock_client import Dock
    dock = Dock("http://drone-dock.local", token="change-me")
    dock.launch()              # stop charging, open covers, park pushers; waits until ready_for_takeoff
    ...fly...
    dock.dock()                # after landing: centre the drone, close covers, start charging

Command line:  python dock_client.py status|launch|dock|open|close|center|release|charge-start|charge-stop|stop|reset
"""
import sys
import time

import requests


class DockError(RuntimeError):
    pass


class Dock:
    def __init__(self, url="http://drone-dock.local", token="change-me", timeout=5.0):
        self.url, self.headers, self.timeout = url.rstrip("/"), {"X-Token": token}, timeout

    def _post(self, path):
        r = requests.post(self.url + path, headers=self.headers, timeout=self.timeout)
        if r.status_code >= 400:
            raise DockError(f"{path}: {r.status_code} {r.text}")
        return r.json()

    def status(self):
        r = requests.get(self.url + "/status", headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def wait_idle(self, timeout=90.0, poll=0.5):
        t0 = time.time()
        while time.time() - t0 < timeout:
            s = self.status()
            if s["error"]:
                raise DockError(f"dock fault: {s['message']}")
            if not s["busy"]:
                return s
            time.sleep(poll)
        raise DockError("dock did not finish in time")

    def launch(self):
        self._post("/launch")
        s = self.wait_idle()
        if not s["ready_for_takeoff"]:
            raise DockError(f"dock not ready for take-off: {s}")
        return s

    def dock(self):
        self._post("/dock")
        return self.wait_idle(timeout=120.0)

    def open(self):
        self._post("/open")
        return self.wait_idle()

    def close(self):
        self._post("/close")
        return self.wait_idle()

    def center(self):
        self._post("/center")
        return self.wait_idle()

    def release(self):
        self._post("/release")
        return self.wait_idle()

    def charge_start(self):
        return self._post("/charge/start")

    def charge_stop(self):
        return self._post("/charge/stop")

    def stop(self):
        return self._post("/stop")

    def reset(self):
        self._post("/reset")
        return self.wait_idle()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    d = Dock(*(sys.argv[2:4]))
    fn = {"status": d.status, "launch": d.launch, "dock": d.dock, "open": d.open, "close": d.close,
          "center": d.center, "release": d.release, "charge-start": d.charge_start, "charge-stop": d.charge_stop,
          "stop": d.stop, "reset": d.reset}[cmd]
    print(fn())
