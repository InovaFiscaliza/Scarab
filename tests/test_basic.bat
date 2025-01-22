@echo off
REM Extract test_basic.zip using 7zip
7z x test_basic.zip -o.

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_basic.zip
    exit /b %errorlevel%
)

REM Run the scarab.py script with config.json
uv run ..\src\scarab.py config.json

REM Check if the script execution was successful
if %errorlevel% neq 0 (
    echo Failed to execute scarab.py
    exit /b %errorlevel%
)

echo Test completed successfully. Check if the output is as expected.