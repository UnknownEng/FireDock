@echo off
rem Opens the Docker Drone dock + drone and the solved arm FEA in FreeCAD 1.1, showing the von Mises stress.
cd /d "%~dp0.."
set FC=C:\Program Files\FreeCAD 1.1\bin\freecad.exe
if not exist "%FC%" (
  echo FreeCAD 1.1 not found at "%FC%" - edit this file to point at your freecad.exe
  pause
  exit /b 1
)
start "" "%FC%" "%CD%\output\freecad\dock_closed.FCStd" "%CD%\output\freecad\arm_FEA_FreeCAD.FCStd" "%CD%\freecad\show_results.py"
