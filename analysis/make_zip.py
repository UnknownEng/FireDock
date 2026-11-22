"""
Pack everything (source, CAD files, drawings, reports, FEA, CFD, pictures) into Docker_Drone_Final.zip.
Run:  .venv\\Scripts\\python analysis\\make_zip.py
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIP = ROOT / "Docker_Drone_Final.zip"
INCLUDE = ["README.md", "requirements.txt", "start_viewer.bat", "cad", "analysis", "firmware", "companion", "freecad", "reports", "research_notes",
           "paper", "output"]
SKIP_DIRS = {"__pycache__", ".venv", ".pio"}

files = []
for item in INCLUDE:
    p = ROOT / item
    if p.is_file():
        files.append(p)
    elif p.is_dir():
        files += [f for f in sorted(p.rglob("*")) if f.is_file() and not (SKIP_DIRS & set(f.parts))
                  and f.suffix not in (".pyc", ".nbi", ".nbc") and not f.name.startswith(".claim_")]

ZIP.unlink(missing_ok=True)
with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in files:
        z.write(f, Path("Docker_Drone") / f.relative_to(ROOT))
with zipfile.ZipFile(ZIP) as z:
    bad = z.testzip()
    n = len(z.namelist())
print(f"wrote {ZIP} ({ZIP.stat().st_size / 1e6:.1f} MB, {n} files, integrity {'OK' if bad is None else 'FAILED: ' + bad})")
