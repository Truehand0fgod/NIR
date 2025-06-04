@echo off
echo Downloading dependencies
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Dependency installation error
    pause
) else (
    echo Dependencies have been successfully established!
    pause
)