@echo off
chcp 65001 > nul
echo ===================================================
echo   DONG GOI PDF AI MARKER V3 BANG PYINSTALLER
echo ===================================================

pyinstaller --onedir --noconsole --name "PDF_AI_Marker" ^
    --icon "app_icon.ico" ^
    --version-file "version_info.txt" ^
    --add-data "md_postprocess.py;." ^
    --add-data "app_icon.ico;." ^
    --add-data "app_icon.png;." ^
    --exclude-module keygen ^
    app.py

echo.
echo ===================================================
echo   HOAN TAT DONG GOI!
echo ===================================================
pause
