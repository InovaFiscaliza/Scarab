@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract sandbox using tar
tar -xf test_N.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_N.tgz
    exit /b %errorlevel%
)

REM If argument is number 0, only display the test setup instructions
if "%~1"=="0" (
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    echo.
    echo Monitor RNI test setup.
    echo.
    echo Run the script using: uv run ..\src\scarab.py .\sandbox\config.json
    echo.
    echo Check if the output is as described in README.md.
    echo.
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    exit /b 0
)

set "arg=%~1"
set "max=3"
if not "%arg%"=="" (
    if "%arg:~0,1%"=="<" (
        set "max=%arg:~1%"
        set /a max-=1
    ) else (
        set "max=%arg%"
    )
) else (
    set "max=3"
)

REM Run the Scarab script for Scenario1
uv run ..\src\scarab.py .\sandbox\config.json

set "run1=0"
if %max% GEQ 1 set "run1=1"
if "%arg%"=="1" set "run1=1"

if %run1%==1 (

    call :check_folder .\sandbox\post .SCH_post

    call :check_file_exists .\sandbox\teams\SCH_20260213_232f1cec-c887-41c8-b266-ec4dbb9e2b8b.teams "Failed: File \"SCH_20260213_232f1cec-c887-41c8-b266-ec4dbb9e2b8b.teams\" was not moved to the ./teams folder."

    call :check_file_exists .\sandbox\store\SCH_20260213_232f1cec-c887-41c8-b266-ec4dbb9e2b8b.json "Failed: File \"SCH_20260213_232f1cec-c887-41c8-b266-ec4dbb9e2b8b.json\" was not created in the ./store folder."

    call :check_file_exists .\sandbox\get\sch.xlsx "Failed: File \"sch.xlsx\" was not created in the ./get folder."

    call :check_file_exists .\sandbox\get\sch.json "Failed: File \"sch.json\" was not created in the ./get folder."

    call :check_file_compare .\sandbox\get\sch.json .\sandbox\results\Scenario1\sch.json "Warning: The content of \"sch.json\" does not match the expected result."

    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    echo.
    echo Scenario1 checks passed successfully.
    echo.
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    if %max% LEQ 1 (
        echo Test completed for Scenario1. To run the next scenarios, run the script again with argument 2.
        exit /b 0
    )
)

REM Prepare Scenario2 and run the Scarab script again
set "run1=0"
if %max% GEQ 2 set "run1=1"
if "%arg%"=="2" set "run1=1"
if %run1%==1 (
    copy .\sandbox\store\Scenario2\* .\sandbox\post\ >nul

    uv run ..\src\scarab.py .\sandbox\config.json

    call :check_folder .\sandbox\post .SCH_post

    call :check_file_exists .\sandbox\teams\SCH_20260213_c261a991-1119-41c0-a605-a10bad10ea93.teams "Failed: File \"SCH_20260213_c261a991-1119-41c0-a605-a10bad10ea93.teams\" was not moved to the ./teams folder."

    call :check_file_exists .\sandbox\store\SCH_20260213_c261a991-1119-41c0-a605-a10bad10ea93.json "Failed: File \"SCH_20260213_c261a991-1119-41c0-a605-a10bad10ea93.json\" was not created in the ./store folder."

    call :check_file_exists .\sandbox\get\sch.xlsx "Failed: File \"sch.xlsx\" was not created in the ./get folder."

    call :check_file_exists .\sandbox\get\sch.json "Failed: File \"sch.json\" was not created in the ./get folder."

    call :check_file_compare .\sandbox\get\sch.json .\sandbox\results\Scenario2\sch.json "Warning: The content of \"sch.json\" does not match the expected result."

    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    echo.
    echo Scenario2 checks passed successfully.
    echo.
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    if %max% LEQ 2 (
        echo Test completed for Scenario2. To run the next scenarios, run the script again with argument 3.
        exit /b 0
    )
)

REM Prepare Scenario3 and run the Scarab script again
set "run1=0"
if %max% GEQ 3 set "run1=1"
if "%arg%"=="3" set "run1=1"
if %run1%==1 (
    copy .\sandbox\store\Scenario3\* .\sandbox\post\ >nul

    uv run ..\src\scarab.py .\sandbox\config.json

    call :check_folder .\sandbox\post .SCH_post

    call :check_file_exists .\sandbox\teams\SCH_20260213_d3623935-3e0d-4f85-966f-af4eba455f36.teams "Failed: File \"SCH_20260213_d3623935-3e0d-4f85-966f-af4eba455f36.teams\" was not moved to the ./teams folder."

    call :check_file_exists .\sandbox\store\SCH_20260213_d3623935-3e0d-4f85-966f-af4eba455f36.json "Failed: File \"SCH_20260213_d3623935-3e0d-4f85-966f-af4eba455f36.json\" was not created in the ./store folder."

    call :check_file_exists .\sandbox\get\sch.xlsx "Failed: File \"sch.xlsx\" was not created in the ./get folder."

    call :check_file_exists .\sandbox\get\sch.json "Failed: File \"sch.json\" was not created in the ./get folder."

    call :check_file_compare .\sandbox\get\sch.json .\sandbox\results\Scenario3\sch.json "Warning: The content of \"sch.json\" does not match the expected result."

    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    echo.
    echo Scenario3 checks passed successfully.
    echo.
    echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    if %max% LEQ 3 (
        echo Test completed for Scenario3.
        exit /b 0
    )
)

exit /b 0

REM --------------------------------------------------------------
REM Function to check if only the allowed file is present in the folder
REM %1: Folder to check
REM %2: Allowed file name
:check_folder
setlocal enabledelayedexpansion
set "folder=%~1"
set "allowed_file=%~2"
set "found_other=0"
set "found_allowed=0"
for /f "delims=" %%i in ('dir /b "%folder%"') do (
    if /i not "%%i"=="%allowed_file%" (
        echo Failed: File "%%i" should have been moved from the %folder% folder.
        set "found_other=1"
    ) else (
        set "found_allowed=1"
    )
)
if !found_other! equ 1 (
    pause
REM     set /p "choice=Do you want to stop the test? (y/n): "
REM     if /i "%choice%"=="y" (
REM         endlocal
REM         exit /b 1
REM     )
)
if !found_allowed! equ 0 (
    echo Failed: File "%allowed_file%" was not found in the %folder% folder.
    pause
REM     set /p "choice=Do you want to stop the test? (y/n): "
REM     if /i "%choice%"=="y" (
REM         endlocal
REM         exit /b 1
REM     )
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
REM            endlocal
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