@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract test_H.tgz using tar
tar -xf test_H.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_H.tgz
    exit /b %errorlevel%
)

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Timestamp column test
echo.
echo Run the script using: uv run ..\src\scarab.py .\sandbox\config.json
echo.
echo Check if the output is as described in README.md.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

exit /b 0
