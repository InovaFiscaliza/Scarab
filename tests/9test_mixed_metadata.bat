@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract test_basic.zip using 7zip
tar -xf test_9.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_basic.zip
    exit /b %errorlevel%
)

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Test mixed metadata formats.
echo.
echo Run the script using two terminals or sequentially using:
echo     uv run ..\src\scarab.py .\sandbox\config.json
echo     uv run ..\src\scarab.py .\sandbox\config_alt.json
echo.
echo Check if the output is as described in README.md.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

exit /b 0