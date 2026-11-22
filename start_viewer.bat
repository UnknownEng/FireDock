@echo off
rem Opens the Docker Drone 3D viewer + animation in your browser (needs internet for the three.js library).
cd /d "%~dp0"
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
start "" http://localhost:8765
echo Docker Drone 3D viewer running at http://localhost:8765  (close this window to stop it)
%PY% output\viewer\serve.py 8765
