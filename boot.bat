@echo off
REM ============================================================
REM   Sales Project Manager V2.0 - One-click boot script
REM
REM   - 双击或 cmd 中执行都可
REM   - 任何出错会暂停窗口显示错误（不再闪退）
REM   - Python 3.11+ （兼容 3.12）
REM
REM   Usage:  双击 boot.bat
REM   Stop:   在弹出的黑窗口里按 Ctrl + C
REM ============================================================

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT_DIR=%cd%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"
set "WRAPPER=%BACKEND_DIR%\start_server2.py"
set "PORT=8765"
set "EXTRA_PKGS=%BACKEND_DIR%\.venv_local_new_pkgs"
set "SITE_PKG=%BACKEND_DIR%\site_pkg"

cls
echo.
echo ============================================================
echo   Sales Project Manager V2.0
echo   Root: %ROOT_DIR%
echo ============================================================
echo.

REM ---------- 1. Resolve Python interpreter ----------
echo [1/5] Resolving Python interpreter ...
set "VENV_PY="

REM Try project venv
if exist "%BACKEND_DIR%\.venv_local\Scripts\python.exe" set "VENV_PY=%BACKEND_DIR%\.venv_local\Scripts\python.exe"
if not defined VENV_PY if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" set "VENV_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"
if not defined VENV_PY if exist "%BACKEND_DIR%\venv\Scripts\python.exe" set "VENV_PY=%BACKEND_DIR%\venv\Scripts\python.exe"

REM Try uv-managed Python
if not defined VENV_PY if exist "%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe" set "VENV_PY=%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe"
if not defined VENV_PY if exist "%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe" set "VENV_PY=%USERPROFILE%\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"

REM Try C:\Python3XX
if not defined VENV_PY if exist "C:\Python311\python.exe" set "VENV_PY=C:\Python311\python.exe"
if not defined VENV_PY if exist "C:\Python312\python.exe" set "VENV_PY=C:\Python312\python.exe"

REM Try py launcher -3
if not defined VENV_PY (
    where py >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%p in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "VENV_PY=%%p"
    )
)

REM Try PATH python
if not defined VENV_PY (
    where python >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%p in ('where python') do set "VENV_PY=%%p"
    )
)

if not defined VENV_PY goto :PYTHON_NOT_FOUND

echo   OK Python: %VENV_PY%
"%VENV_PY%" --version
echo.

REM ---------- 2. Check Node ----------
echo [2/5] Checking Node.js ...
where node >nul 2>nul
if errorlevel 1 goto :NODE_NOT_FOUND
for /f "tokens=1 delims=v" %%v in ('node --version') do set "NODE_VER=%%v"
echo   OK Node.js !NODE_VER!
echo.

REM ---------- 3. Verify backend dependencies ----------
echo [3/5] Checking backend dependencies ...
if not exist "%WRAPPER%" goto :WRAPPER_NOT_FOUND
if exist "%BACKEND_DIR%\site_pkg\fastapi" (
    echo   OK backend\site_pkg present
) else if exist "%EXTRA_PKGS%\fastapi" (
    echo   OK backend\.venv_local_new_pkgs present
) else (
    echo   [WARN] Neither site_pkg nor .venv_local_new_pkgs found. Installing...
    "%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check -q
    "%VENV_PY%" -m pip install -r "%BACKEND_DIR%\requirements.txt" --disable-pip-version-check
    if errorlevel 1 goto :DEPS_INSTALL_FAILED
    echo   OK Backend dependencies installed
)
echo.

REM ---------- 4. Build frontend ----------
echo [4/5] Building frontend ...
if not exist "%FRONTEND_DIR%\node_modules" (
    echo   Installing frontend deps (this may take 2-3 min)...
    pushd "%FRONTEND_DIR%"
    call npm install --no-audit --no-fund
    set "RC=!errorlevel!"
    popd
    if not "!RC!"=="0" goto :FRONTEND_INSTALL_FAILED
)
pushd "%FRONTEND_DIR%"
call node node_modules\vite\bin\vite.js build
set "RC=!errorlevel!"
popd
if not "!RC!"=="0" goto :FRONTEND_BUILD_FAILED
echo   OK Frontend built
echo.

REM ---------- 5. Launch backend (foreground, blocks until Ctrl+C) ----------
echo [5/5] Launching backend on port %PORT% ...
echo.
echo   Local:    http://127.0.0.1:%PORT%/admin/
echo   Default:  admin / Admin@2026
echo   Stop:     按 Ctrl + C 退出，日志写入 backend\uvicorn_run.log
echo.
cd /d "%BACKEND_DIR%"

REM pick python interpreter
set "PY_EXE=%VENV_PY%"
if exist "%BACKEND_DIR%\.venv_local\Scripts\python.exe" set "PY_EXE=%BACKEND_DIR%\.venv_local\Scripts\python.exe"
if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" if not exist "%PY_EXE%" set "PY_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"

REM start_server2.py will set PYTHONPATH and reload sitecustomize.py, then
REM launch `python -m uvicorn app.main:app` in foreground. Blocks until Ctrl+C.
"%PY_EXE%" "%WRAPPER%"
set "RC=!errorlevel!"
echo.
echo Server stopped (exit code !RC!). Tail: backend\uvicorn_run.log
goto :END_OK

:PYTHON_NOT_FOUND
echo.
echo   X Python 3.11+ not found.
echo   请安装 Python 3.11+ 后重试：
echo     - https://www.python.org/downloads/
echo     - uv:     uv python install 3.11
echo     - winget: winget install Python.Python.3.11
goto :PAUSE_AND_END

:NODE_NOT_FOUND
echo.
echo   X Node.js not found. 请安装 Node.js 16+：
echo     https://nodejs.org/
goto :PAUSE_AND_END

:WRAPPER_NOT_FOUND
echo.
echo   X Missing start_server2.py in backend directory
goto :PAUSE_AND_END

:DEPS_INSTALL_FAILED
echo.
echo   X Failed to install backend deps. Check network.
goto :PAUSE_AND_END

:FRONTEND_INSTALL_FAILED
echo.
echo   X Failed to install frontend deps. Check network.
goto :PAUSE_AND_END

:FRONTEND_BUILD_FAILED
echo.
echo   X Frontend build failed
goto :PAUSE_AND_END

:PAUSE_AND_END
echo.
pause

:END_OK
endlocal
