@echo off
REM Test XLSX export engine for incompatible charset
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract sandbox using tar
tar -xf test_O.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_N.tgz
    exit /b %errorlevel%
)

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Test incompatible charset.
echo.
echo Run the script using: uv run ..\src\scarab.py .\sandbox\config.json
echo.
echo Check if log presented any error related to writing XLSX files with incompatible charset.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REM If argument is number 0, only display the test setup instructions
if "%~1"=="0" (
    exit /b 0
)

REM Run the Scarab script for Scenario1
uv run ..\src\scarab.py .\sandbox\config.json
