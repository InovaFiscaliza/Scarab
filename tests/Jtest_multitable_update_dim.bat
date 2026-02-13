@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract sandbox using tar
tar -xf test_J.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_J.tgz
    exit /b %errorlevel%
)

REM If any argument is provided, exit after extraction only
if not "%~1"=="" (
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    echo.
    echo Multitable update dimension table test
    echo.
    echo Run the script using: uv run ..\src\scarab.py .\sandbox\config.json
    echo.
    echo Check if the output is as described in README.md.
    echo.
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    exit /b 0
)

REM Run the Scarab script
uv run ..\src\scarab.py .\sandbox\config.json

REM Compare expected and obtained results
code -d .\sandbox\get\catalog.json .\sandbox\result\catalog.json

exit /b 0