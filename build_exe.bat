@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [EyesTrainer] .venv not found. Create it and install dependencies first.
    exit /b 1
)

".venv\Scripts\python.exe" -m nuitka ^
    --mode=onefile ^
    --assume-yes-for-downloads ^
    --zig ^
    --include-package=eyestrainer ^
    --include-package=pygame ^
    --nofollow-import-to=pygame.tests ^
    --nofollow-import-to=pygame.examples ^
    --windows-console-mode=disable ^
    --output-dir=dist ^
    --output-filename=EyesTrainer.exe ^
    --company-name=BaiZiDog ^
    --product-name=EyesTrainer ^
    --copyright="Copyright (C) 2026 BaiZiDog" ^
    --file-version=0.5.1.0 ^
    --product-version=0.5.1.0 ^
    --file-description="FPS visual and reaction trainer" ^
    main.py

echo.
echo [EyesTrainer] Build finished. Check dist\EyesTrainer.exe
endlocal
