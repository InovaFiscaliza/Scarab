@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract test_basic.zip using 7zip
tar -xf test_D.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_D.tgz
    exit /b %errorlevel%
)

REM If argument is number 0, only display the test setup instructions
if "%~1"=="0" (
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    echo.
    echo Test processing of multiple input files with different formats with single output file
    echo.
    echo Run the script using: uv run ..\src\scarab.py .\sandbox\config.json
    echo.
    echo Check if the output is as described in README.md.
    echo.
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    exit /b 0
)

REM Run the Scarab script for Scenario1
uv run ..\src\scarab.py .\sandbox\config.json

call :check_folder_has_files .\sandbox\store "Failed: No files were moved to the ./store folder."

call :check_folder_has_files .\sandbox\get\raw "Failed: No files were moved to the ./get/raw folder."

call :check_file_exists .\sandbox\get\monitorRNI.xlsx "Failed: File \"monitorRNI.xlsx\" was not created in the ./get folder."

call :check_file_exists .\sandbox\get\monitorRNI.json "Failed: File \"monitorRNI.json\" was not created in the ./get folder."

call :check_file_compare .\sandbox\get\monitorRNI.json .\sandbox\results\monitorRNI.json "Warning: The content of \"monitorRNI.json\" does not match the expected result."

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Scenario checks passed successfully.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

exit /b 0

REM --------------------------------------------------------------
REM Function to check if a folder has at least one file
REM %1: Folder to check
REM %2: Error message to display if empty
:check_folder_has_files
setlocal enabledelayedexpansion
set "folder=%~1"
set "error_msg=%~2"
set "found=0"
for /f "delims=" %%i in ('dir /b "%folder%"') do (
    set "found=1"
    goto :found_file
)
:found_file
if !found! equ 0 (
    echo %error_msg%
    pause
REM    set /p "choice=Do you want to stop the test? (y/n): "
REM    if /i "%choice%"=="y" (
REM        endlocal
REM        exit /b 1
REM    )
)
endlocal
exit /b 0

REM --------------------------------------------------------------
REM Function to check if a specific file exists
REM %1: File to check
REM %2: Error message to display if the file does not exist
:check_file_exists
setlocal
set "target_file=%~1"
set "error_msg=%~2"
if not exist "%target_file%" (
    echo %error_msg%
    pause
REM    set /p "choice=Do you want to stop the test? (y/n): "
REM    if /i "%choice%"=="y" (
REM        endlocal
REM        exit /b 1
REM        )
)
endlocal
exit /b 0

REM --------------------------------------------------------------
REM Function to compare two files and display a warning if they differ
REM %1: First file to compare
REM %2: Second file to compare
REM %3: Warning message to display if the files differ
:check_file_compare
setlocal
set "file_a=%~1"
set "file_b=%~2"
set "warn_msg=%~3"
fc "%file_a%" "%file_b%" >nul
if %errorlevel% neq 0 (
    echo %warn_msg%
    code -d "%file_a%" "%file_b%"
    pause
REM        set /p "choice=Do you want to stop the test? (y/n): "
REM        if /i "%choice%"=="y" (
REM            endlocal
REM            exit /b 1
REM        )
)
endlocal
exit /b 0