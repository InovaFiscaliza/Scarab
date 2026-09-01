@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "SHELL_SCRIPT=%~dp0exe.sh"
set "SANDBOX_DIR=%~dp0..\sandbox"
set "SSH_HOST="
set "INSTANCE=scarab-test"
set "OPERATION=reset"
set "REMOTE_SANDBOX="
set "DB_HOST="
set "DB_PORT=5432"
set "CONFIRM_RESET="

:parse_arguments
if "%~1"=="" goto arguments_parsed
if /I "%~1"=="-h" goto show_help
if /I "%~1"=="--help" goto show_help
if /I "%~1"=="--host" (
    if "%~2"=="" goto missing_value
    set "SSH_HOST=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--instance" (
    if "%~2"=="" goto missing_value
    set "INSTANCE=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--operation" (
    if "%~2"=="" goto missing_value
    set "OPERATION=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--sandbox-dir" (
    if "%~2"=="" goto missing_value
    set "REMOTE_SANDBOX=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--db-host" (
    if "%~2"=="" goto missing_value
    set "DB_HOST=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--db-port" (
    if "%~2"=="" goto missing_value
    set "DB_PORT=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--confirm-reset" (
    if "%~2"=="" goto missing_value
    set "CONFIRM_RESET=%~2"
    shift
    shift
    goto parse_arguments
)
echo ERROR: Unknown option: %~1
exit /b 1

:missing_value
echo ERROR: An option requires a value.
exit /b 1

:arguments_parsed
if not defined SSH_HOST (
    echo ERROR: --host is required.
    exit /b 1
)
where.exe powershell.exe >nul 2>&1 || (echo ERROR: powershell.exe was not found.& exit /b 1)
where.exe ssh.exe >nul 2>&1 || (echo ERROR: ssh.exe was not found.& exit /b 1)

powershell.exe -NoProfile -Command "$rules = @{ SSH_HOST = '^[A-Za-z0-9._@-]+$'; INSTANCE = '^[a-z][a-z0-9-]*$'; OPERATION = '^(reset|validate|start|stop|restart|status|logs|backup)$' }; foreach ($name in $rules.Keys) { $value = [Environment]::GetEnvironmentVariable($name); if (-not $value -or $value -notmatch $rules[$name]) { Write-Error ('Invalid value for ' + $name); exit 1 } }"
if errorlevel 1 exit /b 1

echo Checking key-based SSH access to %SSH_HOST%...
ssh.exe -o BatchMode=yes "%SSH_HOST%" "test \"$(uname -s)\" = Linux && test -x /usr/local/sbin/scarab-ops"
if errorlevel 1 (
    echo ERROR: The SSH target is unavailable or scarab-ops is not installed.
    exit /b 1
)

if /I not "%OPERATION%"=="reset" goto run_operation

if not defined DB_HOST (
    echo ERROR: --db-host is required for reset.
    exit /b 1
)
if /I not "%CONFIRM_RESET%"=="%INSTANCE%" (
    echo ERROR: Pass --confirm-reset %INSTANCE% to authorize destructive reset.
    exit /b 1
)
if not defined REMOTE_SANDBOX set "REMOTE_SANDBOX=/srv/%INSTANCE%"
if not exist "%SHELL_SCRIPT%" (
    echo ERROR: Companion script not found: %SHELL_SCRIPT%
    exit /b 1
)
if not exist "%SANDBOX_DIR%\config.json" (
    echo ERROR: Sandbox configuration not found: %SANDBOX_DIR%\config.json
    exit /b 1
)
where.exe scp.exe >nul 2>&1 || (echo ERROR: scp.exe was not found.& exit /b 1)

powershell.exe -NoProfile -Command "$rules = @{ REMOTE_SANDBOX = '^/[A-Za-z0-9._/-]+$'; DB_HOST = '^[A-Za-z0-9._-]+$'; DB_PORT = '^[0-9]+$' }; foreach ($name in $rules.Keys) { $value = [Environment]::GetEnvironmentVariable($name); if (-not $value -or $value -notmatch $rules[$name]) { Write-Error ('Invalid value for ' + $name); exit 1 } }; $port = [int]$env:DB_PORT; if ($port -lt 1 -or $port -gt 65535) { Write-Error 'DB_PORT must be between 1 and 65535'; exit 1 }"
if errorlevel 1 exit /b 1

for /f %%C in ('dir /b /a-d "%SANDBOX_DIR%\store\*.json" 2^>nul ^| find /c /v ""') do set "FIXTURE_COUNT=%%C"
if not "%FIXTURE_COUNT%"=="6" (
    echo ERROR: Expected 6 JSON fixtures in examples\sandbox\store. Restore test_01 first.
    exit /b 1
)

set "REMOTE_SCRIPT=.scarab-exe-%RANDOM%-%RANDOM%.sh"
scp.exe -q -o BatchMode=yes "%SHELL_SCRIPT%" "%SSH_HOST%:%REMOTE_SCRIPT%"
if errorlevel 1 (
    echo ERROR: Failed to upload exe.sh.
    exit /b 1
)

setlocal EnableDelayedExpansion
echo Resetting and executing scenario on %SSH_HOST%...
ssh.exe -tt -o BatchMode=yes "%SSH_HOST%" "bash ~/%REMOTE_SCRIPT% --instance !INSTANCE! --sandbox-dir !REMOTE_SANDBOX! --confirm-reset !CONFIRM_RESET!"
set "REMOTE_STATUS=!ERRORLEVEL!"
endlocal & set "REMOTE_STATUS=%REMOTE_STATUS%"
ssh.exe -o BatchMode=yes "%SSH_HOST%" "rm -f ~/%REMOTE_SCRIPT%" >nul 2>&1
if not "%REMOTE_STATUS%"=="0" (
    echo ERROR: Remote scenario failed with exit code %REMOTE_STATUS%.
    exit /b %REMOTE_STATUS%
)

echo Checking PostgreSQL TCP access at %DB_HOST%:%DB_PORT%...
powershell.exe -NoProfile -Command "if (-not (Test-NetConnection -ComputerName $env:DB_HOST -Port ([int]$env:DB_PORT) -InformationLevel Quiet)) { Write-Error 'PostgreSQL TCP connection failed.'; exit 1 }"
if errorlevel 1 exit /b 1

where.exe psql.exe >nul 2>&1
if errorlevel 1 goto psql_skipped
if not defined PGPASSFILE set "PGPASSFILE=%APPDATA%\postgresql\pgpass.conf"
if not exist "%PGPASSFILE%" goto psql_skipped

for /f "usebackq delims=" %%R in (`psql.exe --no-password --host "%DB_HOST%" --port "%DB_PORT%" --username scarab_app --dbname scarab --tuples-only --no-align --field-separator "^|" --command "SELECT ^(SELECT count^(*^) FROM clientes_docs^), ^(SELECT count^(*^) FROM carga_historico^), ^(SELECT count^(^*^) FROM carga_historico WHERE status = 'SUCESSO'^);"`) do set "DIRECT_COUNTS=%%R"
if errorlevel 1 (
    echo ERROR: Direct PostgreSQL query failed. Check PGPASSFILE and pg_hba authentication.
    exit /b 1
)
if not "%DIRECT_COUNTS%"=="2|6|6" (
    echo ERROR: Direct PostgreSQL query returned %DIRECT_COUNTS%; expected 2^|6^|6.
    exit /b 1
)
echo Direct PostgreSQL query passed: %DIRECT_COUNTS%.
goto success

:psql_skipped
echo INFO: Direct SQL check skipped; install psql.exe and configure PGPASSFILE to enable it.

:success
echo Remote scenario and PostgreSQL TCP checks completed successfully.
exit /b 0

:run_operation
setlocal EnableDelayedExpansion
ssh.exe -o BatchMode=yes "%SSH_HOST%" "/usr/local/sbin/scarab-ops !OPERATION! --instance !INSTANCE!"
set "OPERATION_STATUS=!ERRORLEVEL!"
endlocal & exit /b %OPERATION_STATUS%

:show_help
echo Usage:
echo   exe.bat --host SSH_HOST [--instance NAME] --operation OPERATION
echo   exe.bat --host SSH_HOST --operation reset --db-host HOST [--db-port PORT]
echo       [--instance NAME] [--sandbox-dir REMOTE_PATH] --confirm-reset NAME
echo.
echo OPERATION may be validate, start, stop, restart, status, logs, backup, or reset.
echo The sandbox must already be mounted on the Linux host. Reset deletes the
echo selected test instance database and post/get/trash contents. It always
echo checks TCP from Windows and performs direct SQL when psql.exe and PGPASSFILE
echo are available.
exit /b 0
