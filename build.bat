@echo off
REM Build Attention Tracker executable (Windows)
REM Requires: Python with venv activated and dependencies + pyinstaller installed

echo Installing PyInstaller if needed...
pip install pyinstaller -q

echo Building executable...
pyinstaller --noconfirm attention_tracker.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo Build complete. Run: dist\AttentionTracker\AttentionTracker.exe
    echo Config and logs will be created next to the .exe on first run.
) else (
    echo Build failed.
    exit /b 1
)
