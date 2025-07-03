@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)


REM Extract test_basic.zip using 7zip
tar -xf test_0.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_basic.zip
    exit /b %errorlevel%
)

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Sandbox Cleaned
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

exit /b 0