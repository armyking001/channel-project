@echo off
chcp 936 >nul 2>&1
cd /d "Y:\soft-RED\hermes\开发软件\渠道项目登记\backend"
set "PYTHONPATH=Y:\soft-RED\hermes\开发软件\渠道项目登记\backend"
echo ============================================
echo   渠道项目登记 本地后端
echo   Port : 8766
echo   URL  : http://127.0.0.1:8766/admin/
echo ============================================
"C:\Users\admin\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8766
pause
