@echo off
setlocal
cd /d "%~dp0"

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "D:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=D:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC for /f "delims=" %%i in ('where ISCC.exe 2^>nul') do set "ISCC=%%i"

if not defined ISCC (
    echo [EyesTrainer] Inno Setup 6 ISCC.exe not found.
    exit /b 1
)
if not exist "dist\EyesTrainer.exe" (
    echo [EyesTrainer] dist\EyesTrainer.exe not found. Run build_exe.bat first.
    exit /b 1
)

"%ISCC%" "installer\EyesTrainer.iss"
if errorlevel 1 exit /b 1
echo.
echo [EyesTrainer] Installer written to dist\EyesTrainer-Setup-0.5.1.exe
endlocal
