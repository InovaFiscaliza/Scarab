@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Sandbox Cleaned
echo.
echo Run the test_1.bat script to setup the sandbox for the first test.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

exit /b 0