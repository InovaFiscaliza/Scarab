@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract test_basic.zip using 7zip
tar -xf test_A.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_basic.zip
    exit /b %errorlevel%
)

REM If argument is number 0, only display the test setup instructions
if "%~1"=="0" (
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    echo.
    echo Test null filename column.
    echo.
    echo Run the script using two terminals or sequentially using:
    echo     uv run ..\src\scarab.py .\sandbox\config.json
    echo.
    echo Check if the output is as described in README.md.
    echo.
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    exit /b 0
)

REM Run the Scarab script for Scenario1
uv run ..\src\scarab.py .\sandbox\config.json

exit /b 0