@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract test_basic.zip using 7zip
tar -xf test_basic.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_basic.zip
    exit /b %errorlevel%
)

echo
echo Run the script using: uv run ..\src\scarab.py config.json
echo Check if the output is as expected.

REM Wait for user to press any key before exiting
pause >nul
exit /b 0