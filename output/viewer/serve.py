"""
Local server for the 3D viewer (the browser cannot load the 3D models from a plain file:// page).

    .venv\\Scripts\\python output\\viewer\\serve.py          then open http://localhost:8765

The viewer's "Save picture" and "Record video" buttons POST to /save; files land in output/viewer/media/.
Only listens on this computer (127.0.0.1).
"""
import http.server
import re
import socketserver
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEDIA = HERE / "media"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(HERE), **k)

    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".glb": "model/gltf-binary",
                      ".js": "text/javascript", ".json": "application/json"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_GET(self):
        """Byte-range support so the browser can seek in the MP4."""
        rng = self.headers.get("Range")
        path = Path(self.translate_path(self.path))
        m = re.match(r"bytes=(\d*)-(\d*)$", rng or "")
        if not m or not path.is_file():
            return super().do_GET()
        size = path.stat().st_size
        a = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2)))
        b = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
        b = min(b, size - 1)
        if a > b:
            self.send_error(416)
            return
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.send_header("Content-Length", str(b - a + 1))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(a)
            left = b - a + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def do_POST(self):
        f = re.match(r"^/frame\?i=(\d{1,6})$", self.path)          # video frames from renderVideo()
        if f:
            n = int(self.headers.get("Content-Length", 0))
            (MEDIA / "frames").mkdir(parents=True, exist_ok=True)
            (MEDIA / "frames" / f"f_{int(f.group(1)):05d}.jpg").write_bytes(self.rfile.read(n))
            self.send_response(200)
            self.end_headers()
            return
        m = re.match(r"^/save\?name=([A-Za-z0-9_\-]{1,80}\.(png|jpg|webm|mp4))$", self.path)
        if not m:
            self.send_error(400, "bad name")
            return
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0 or n > 500_000_000:
            self.send_error(400, "bad size")
            return
        MEDIA.mkdir(exist_ok=True)
        data = self.rfile.read(n)
        (MEDIA / m.group(1)).write_bytes(data)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"saved {m.group(1)} ({len(data)} bytes)".encode())

    def log_message(self, fmt, *args):
        if "POST" in (args[0] if args else ""):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Docker Drone viewer: http://localhost:{PORT}", flush=True)
        httpd.serve_forever()
