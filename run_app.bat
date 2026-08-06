@echo off
chcp 65001 > nul
echo Starting Community Complaint Portal...
echo.
powershell -Command "& 'c:\Users\Tejas\OneDrive\文件\project k\venv\Scripts\python.exe' app.py"
pause
