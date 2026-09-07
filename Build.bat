@echo off
echo Building avatar-setup.exe...
pyinstaller --clean --onefile --noconsole --icon=icon.ico --add-data "icon.ico;." --exclude-module numpy --exclude-module PIL --exclude-module matplotlib --exclude-module scipy avatar-setup.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Copying avatar-setup.exe and avatar-setup.py to TEMPLATE...
    copy /y "dist\avatar-setup.exe" "TEMPLATE\avatar-setup.exe"
    copy /y "avatar-setup.py" "TEMPLATE\avatar-setup.py"
    echo Cleaning temporary pycache...
    for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
    echo.
    echo Build and packaging complete! Results ready in dist\ and TEMPLATE\
) else (
    echo.
    echo Build failed with error code %ERRORLEVEL%.
    exit /b %ERRORLEVEL%
)