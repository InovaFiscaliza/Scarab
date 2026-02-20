@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract sandbox using tar
tar -xf test_M.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_L.tgz
    exit /b %errorlevel%
)

REM If any argument is provided, exit after extraction only
if not "%~1"=="" (
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

REM Run the Scarab script for Scenario1
uv run ..\src\scarab.py .\sandbox\config.json

call :check_folder .\sandbox\post .monitorRNI_post

call :check_file_exists .\sandbox\teams\monitorRNI_20260211_e2dc3d88-3d5e-49d4-95c9-37d445c4737f.teams "Failed: File \"monitorRNI_20260211_e2dc3d88-3d5e-49d4-95c9-37d445c4737f.teams\" was not moved to the ./teams folder."

call :check_file_exists .\sandbox\get\raw\8059Log_080152_270324.txt "Failed: File \"8059Log_080152_270324.txt\" was not moved to the ./get/raw folder."

call :check_file_exists .\sandbox\store\monitorRNI_20260211_e2dc3d88-3d5e-49d4-95c9-37d445c4737f.json "Failed: File \"monitorRNI_20260211_e2dc3d88-3d5e-49d4-95c9-37d445c4737f.json\" was not created in the ./store folder."

call :check_file_exists .\sandbox\get\monitorRNI.xlsx "Failed: File \"monitorRNI.xlsx\" was not created in the ./get folder."

call :check_file_exists .\sandbox\get\monitorRNI.json "Failed: File \"monitorRNI.json\" was not created in the ./get folder."

call :check_file_compare .\sandbox\get\monitorRNI.json .\sandbox\results\Scenario1\monitorRNI.json "Warning: The content of \"monitorRNI.json\" does not match the expected result."

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Scenario1 checks passed successfully.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REM Prepare Scenario2 and run the Scarab script again
copy .\sandbox\store\Scenario2\* .\sandbox\post\ >nul

uv run ..\src\scarab.py .\sandbox\config.json

call :check_folder .\sandbox\post .monitorRNI_post

call :check_file_exists .\sandbox\teams\monitorRNI_20260211_536b0e6a-45bd-4737-92ba-068a1fc1a2a6.teams "Failed: File \"monitorRNI_20260211_536b0e6a-45bd-4737-92ba-068a1fc1a2a6.teams\" was not moved to the ./teams folder."

call :check_file_exists .\sandbox\get\raw\8059Log_080152_270324.txt "Failed: File \"8059Log_080152_270324.txt\" was not moved to the ./get/raw folder."

call :check_file_exists .\sandbox\store\monitorRNI_20260211_536b0e6a-45bd-4737-92ba-068a1fc1a2a6.json "Failed: File \"monitorRNI_20260211_536b0e6a-45bd-4737-92ba-068a1fc1a2a6.json\" was not created in the ./store folder."

call :check_file_exists .\sandbox\get\monitorRNI.xlsx "Failed: File \"monitorRNI.xlsx\" was not created in the ./get folder."

call :check_file_exists .\sandbox\get\monitorRNI.json "Failed: File \"monitorRNI.json\" was not created in the ./get folder."

call :check_file_compare .\sandbox\get\monitorRNI.json .\sandbox\results\Scenario2\monitorRNI.json "Warning: The content of \"monitorRNI.json\" does not match the expected result."

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Scenario2 checks passed successfully.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REM Prepare Scenario3 and run the Scarab script again
copy .\sandbox\store\Scenario3\* .\sandbox\post\ >nul

uv run ..\src\scarab.py .\sandbox\config.json

call :check_folder .\sandbox\post .monitorRNI_post

call :check_file_exists .\sandbox\teams\monitorRNI_20260211_bb21dd3c-251a-4f5f-b93f-689b0fbe8dd8.teams "Failed: File \"monitorRNI_20260211_bb21dd3c-251a-4f5f-b93f-689b0fbe8dd8.teams\" was not moved to the ./teams folder."

call :check_file_exists .\sandbox\get\raw\8059Log_082159_190324.txt "Failed: File \"8059Log_082159_190324.txt\" was not moved to the ./get/raw folder."

call :check_file_exists .\sandbox\get\raw\8059Log_084234_200324.txt "Failed: File \"8059Log_084234_200324.txt\" was not moved to the ./get/raw folder."

call :check_file_exists .\sandbox\store\monitorRNI_20260211_bb21dd3c-251a-4f5f-b93f-689b0fbe8dd8.json "Failed: File \"monitorRNI_20260211_bb21dd3c-251a-4f5f-b93f-689b0fbe8dd8.json\" was not created in the ./store folder."

call :check_file_exists .\sandbox\get\monitorRNI.xlsx "Failed: File \"monitorRNI.xlsx\" was not created in the ./get folder."

call :check_file_exists .\sandbox\get\monitorRNI.json "Failed: File \"monitorRNI.json\" was not created in the ./get folder."

call :check_file_compare .\sandbox\get\monitorRNI.json .\sandbox\results\Scenario3\monitorRNI.json "Warning: The content of \"monitorRNI.json\" does not match the expected result."

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Scenario3 checks passed successfully.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

REM Prepare Scenario4 and run the Scarab script again
copy .\sandbox\store\Scenario4\* .\sandbox\post\ >nul

uv run ..\src\scarab.py .\sandbox\config.json

call :check_folder .\sandbox\post .monitorRNI_post

call :check_file_exists .\sandbox\teams\monitorRNI_20260211_5b1a317d-211a-443e-8420-83fc84567a44.teams "Failed: File \"monitorRNI_20260211_5b1a317d-211a-443e-8420-83fc84567a44.teams\" was not moved to the ./teams folder."

call :check_file_exists .\sandbox\get\raw\8059Log_082159_190324.txt "Failed: File \"8059Log_082159_190324.txt\" was not moved to the ./get/raw folder."

call :check_file_exists .\sandbox\get\raw\8059Log_084234_200324.txt "Failed: File \"8059Log_084234_200324.txt\" was not moved to the ./get/raw folder."

call :check_file_exists .\sandbox\store\monitorRNI_20260211_5b1a317d-211a-443e-8420-83fc84567a44.json "Failed: File \"monitorRNI_20260211_5b1a317d-211a-443e-8420-83fc84567a44.json\" was not created in the ./store folder."

call :check_file_exists .\sandbox\get\monitorRNI.xlsx "Failed: File \"monitorRNI.xlsx\" was not created in the ./get folder."

call :check_file_exists .\sandbox\get\monitorRNI.json "Failed: File \"monitorRNI.json\" was not created in the ./get folder."

call :check_file_compare .\sandbox\get\monitorRNI.json .\sandbox\results\Scenario4\monitorRNI.json "Warning: The content of \"monitorRNI.json\" does not match the expected result."


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
    echo press any key to continue...
    pause
REM     set /p "choice=Do you want to stop the test? (y/n): "
REM     if /i "%choice%"=="y" (
REM         endlocal
REM         exit /b 1
REM     )
)
if !found_allowed! equ 0 (
    echo Failed: File "%allowed_file%" was not found in the %folder% folder.
    echo press any key to continue...
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
    echo press any key to continue...
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
    echo press any key to continue...
    pause
REM        set /p "choice=Do you want to stop the test? (y/n): "
REM        if /i "%choice%"=="y" (
REM            endlocal
REM            exit /b 1
REM        )
)
endlocal
exit /b 0