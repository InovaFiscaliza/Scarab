REM This batch script is intended to test scarab with multiple input files and check if the output is as expected. It will move files from the storeGood folder to the post folder, wait for scarab to process them, and check if they are removed from the temp folder. If a file is not removed, it will be moved to the storeEvil folder.

@echo off
setlocal

cd /d "%~dp0"

set "source_dir=.\sandbox\storeGood"
set "post_dir=.\sandbox\post"
set "test_dir=.\sandbox\temp"
set "evil_dir=.\sandbox\storeEvil"
set "target_file=.\sandbox\get\Anuncios.xlsx"

if not exist "%source_dir%\." (
    echo Source folder not found: "%source_dir%"
    exit /b 1
)

if not exist "%post_dir%\." (
    echo Post folder not found: "%post_dir%"
    exit /b 1
)

if not exist "%test_dir%\." (
    echo Temp folder not found: "%test_dir%"
    exit /b 1
)

if not exist "%target_file%" (
    echo Target file not found: "%target_file%"
    exit /b 1
)

for /f "delims=" %%S in ('powershell -NoProfile -Command "(Get-Item -LiteralPath '%target_file%').Length"') do set "initial_target_size=%%S"
if not defined initial_target_size (
    echo Failed to read the initial size of "%target_file%".
    exit /b 1
)
echo Initial target file size: %initial_target_size% bytes.

call :start_scarab
if errorlevel 1 exit /b 1

set "found_file=0"
for /f "delims=" %%F in ('dir /b /a-d /o:n "%source_dir%" 2^>nul') do (
    set "found_file=1"
    call :move_and_wait "%%F"
    if errorlevel 1 exit /b 1
)

if "%found_file%"=="0" echo No files found in "%source_dir%".
exit /b 0

:start_scarab
set "scarab_pid="
for /f "delims=" %%P in ('powershell -NoProfile -Command "$p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','uv run ..\src\scarab.py .\sandbox\config.json' -WorkingDirectory '%cd%' -PassThru; $p.Id"') do set "scarab_pid=%%P"
if not defined scarab_pid (
    echo Failed to start Scarab.
    exit /b 1
)
echo Scarab started with process ID %scarab_pid%.
exit /b 0

:move_and_wait
set "file_name=%~1"

echo Moving "%file_name%" to "%post_dir%".
move /y "%source_dir%\%file_name%" "%post_dir%\" >nul
if errorlevel 1 (
    echo Failed to move "%file_name%".
    exit /b 1
)

echo Waiting 10 seconds before checking "%test_dir%\%file_name%".
timeout /t 10 /nobreak >nul
if not exist "%test_dir%\%file_name%" exit /b 0

echo "%file_name%" is still in the temp folder. Waiting 10 more seconds.
timeout /t 10 /nobreak >nul
if exist "%test_dir%\%file_name%" (
    echo "%file_name%" was not removed from the temp folder. Quarantining the file.
    call :check_target_size
    if errorlevel 1 exit /b 1
    call :quarantine_file
    if errorlevel 1 exit /b 1
    call :start_scarab
    if errorlevel 1 exit /b 1
)

exit /b 0

:check_target_size
if not exist "%target_file%" (
    echo Target file "%target_file%" is missing. Ending script.
    exit /b 1
)

for /f "delims=" %%S in ('powershell -NoProfile -Command "(Get-Item -LiteralPath '%target_file%').Length"') do set "current_target_size=%%S"
if not defined current_target_size (
    echo Failed to read the current size of "%target_file%". Ending script.
    exit /b 1
)

powershell -NoProfile -Command "if ([Int64]'%current_target_size%' -lt [Int64]'%initial_target_size%') { exit 1 }"
if errorlevel 1 (
    echo Target file size decreased from %initial_target_size% to %current_target_size% bytes. Ending script.
    exit /b 1
)

echo Target file size is %current_target_size% bytes; continuing.
exit /b 0

:quarantine_file
if defined scarab_pid (
    echo Stopping Scarab process ID %scarab_pid%.
    taskkill /PID %scarab_pid% /T /F >nul 2>&1
    set "scarab_pid="
)

if not exist "%evil_dir%\." mkdir "%evil_dir%"
if not exist "%test_dir%\%file_name%" (
    echo "%file_name%" was removed from the temp folder while Scarab was stopping.
    exit /b 0
)

move /y "%test_dir%\%file_name%" "%evil_dir%\" >nul
if errorlevel 1 (
    echo Failed to move "%file_name%" from the temp folder to "%evil_dir%".
    exit /b 1
)
echo Moved problematic file "%file_name%" to "%evil_dir%".
exit /b 0