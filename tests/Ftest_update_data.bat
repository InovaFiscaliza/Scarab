@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract test_basic.zip using 7zip
tar -xf test_F.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_F.tgz
    exit /b %errorlevel%
)

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Test processing updates in multitable json.
echo.
echo Run the script using: uv run ..\src\scarab.py .\sandbox\config.json
echo.
echo Check if the output is as described in README.md.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

exit /b 0