@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "BASH_SCRIPT=%~dp0scarab-bootstrap.sh"
set "SSH_HOST="
set "BRANCH="
set "INSTANCE="
set "ENVIRONMENT_NAME=test"
set "SERVICE_USER="
set "APP_IMAGE="
set "DB_IMAGE="
set "DB_BIND_ADDRESS="
set "DB_PORT=5432"
set "CHECK_ONLY=false"

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
if /I "%~1"=="--branch" (
    if "%~2"=="" goto missing_value
    set "BRANCH=%~2"
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
if /I "%~1"=="--environment" (
    if "%~2"=="" goto missing_value
    set "ENVIRONMENT_NAME=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--service-user" (
    if "%~2"=="" goto missing_value
    set "SERVICE_USER=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--app-image" (
    if "%~2"=="" goto missing_value
    set "APP_IMAGE=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--db-image" (
    if "%~2"=="" goto missing_value
    set "DB_IMAGE=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--db-bind-address" (
    if "%~2"=="" goto missing_value
    set "DB_BIND_ADDRESS=%~2"
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
if /I "%~1"=="--check" (
    set "CHECK_ONLY=true"
    shift
    goto parse_arguments
)
echo ERROR: Unknown option.
exit /b 1

:missing_value
echo ERROR: An option requires a value.
exit /b 1

:arguments_parsed
if not defined SSH_HOST (
    echo ERROR: --host is required.
    exit /b 1
)
if /I "%SERVICE_USER%"=="root" (
    echo ERROR: --service-user must be a non-root account for rootless Podman.
    exit /b 1
)
if not exist "%BASH_SCRIPT%" (
    echo ERROR: Companion script not found: %BASH_SCRIPT%
    exit /b 1
)

if not defined BRANCH (
    where.exe git.exe >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%B in ('git.exe -C "%~dp0.." branch --show-current 2^>nul') do if not defined BRANCH set "BRANCH=%%B"
    )
)

where.exe powershell.exe >nul 2>&1 || (
    echo ERROR: Required command not found: powershell.exe
    exit /b 1
)
where.exe ssh.exe >nul 2>&1 || (
    echo ERROR: Required command not found: ssh.exe
    exit /b 1
)
where.exe scp.exe >nul 2>&1 || (
    echo ERROR: Required command not found: scp.exe
    exit /b 1
)

powershell.exe -NoProfile -Command "$rules = @{ SSH_HOST = '^[A-Za-z0-9._@-]+$'; BRANCH = '^[A-Za-z0-9][A-Za-z0-9._/-]*$'; INSTANCE = '^[a-z][a-z0-9-]*$'; ENVIRONMENT_NAME = '^(test|production)$'; SERVICE_USER = '^[A-Za-z_][A-Za-z0-9_-]*$'; APP_IMAGE = '^[A-Za-z0-9][A-Za-z0-9._/@:-]*$'; DB_IMAGE = '^[A-Za-z0-9][A-Za-z0-9._/@:-]*$'; DB_BIND_ADDRESS = '^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'; DB_PORT = '^[0-9]+$' }; foreach ($name in $rules.Keys) { $value = [Environment]::GetEnvironmentVariable($name); if ($value -and $value -notmatch $rules[$name]) { Write-Error ('Invalid value for ' + $name + ': ' + $value); exit 1 } }; if ($env:DB_BIND_ADDRESS) { $octets = $env:DB_BIND_ADDRESS.Split('.').ForEach({ [int]$_ }); if ($octets.Where({ $_ -gt 255 }).Count -or $octets[0] -eq 0 -or $octets[0] -eq 127 -or $octets[0] -ge 224) { Write-Error 'DB_BIND_ADDRESS must be a non-loopback unicast IPv4 address'; exit 1 } }; $port = [int]$env:DB_PORT; if ($port -lt 1 -or $port -gt 65535) { Write-Error 'DB_PORT must be between 1 and 65535'; exit 1 }"
if errorlevel 1 exit /b 1

if defined APP_IMAGE if not defined DB_IMAGE (
    echo ERROR: Provide both --app-image and --db-image, or neither.
    exit /b 1
)
if defined DB_IMAGE if not defined APP_IMAGE (
    echo ERROR: Provide both --app-image and --db-image, or neither.
    exit /b 1
)
if /I "%ENVIRONMENT_NAME%"=="production" if not defined APP_IMAGE (
    echo ERROR: --app-image and --db-image are required for production.
    exit /b 1
)

echo Checking key-based SSH access and Linux prerequisites on %SSH_HOST%...
ssh.exe -o BatchMode=yes "%SSH_HOST%" "test \"$(uname -s)\" = Linux && command -v bash >/dev/null"
if errorlevel 1 (
    echo ERROR: The SSH target must be a reachable Linux host with bash.
    exit /b 1
)

set "REMOTE_SCRIPT=.scarab-bootstrap-%RANDOM%-%RANDOM%.sh"
scp.exe -q -o BatchMode=yes "%BASH_SCRIPT%" "%SSH_HOST%:%REMOTE_SCRIPT%"
if errorlevel 1 (
    echo ERROR: Failed to upload the Linux bootstrap script.
    exit /b 1
)

setlocal EnableDelayedExpansion
set "REMOTE_ARGUMENTS= --environment !ENVIRONMENT_NAME! --db-port !DB_PORT!"
if defined DB_BIND_ADDRESS set "REMOTE_ARGUMENTS=!REMOTE_ARGUMENTS! --db-bind-address !DB_BIND_ADDRESS!"
if defined BRANCH set "REMOTE_ARGUMENTS=!REMOTE_ARGUMENTS! --branch !BRANCH!"
if defined INSTANCE set "REMOTE_ARGUMENTS=!REMOTE_ARGUMENTS! --instance !INSTANCE!"
if defined SERVICE_USER set "REMOTE_ARGUMENTS=!REMOTE_ARGUMENTS! --service-user !SERVICE_USER!"
if defined APP_IMAGE set "REMOTE_ARGUMENTS=!REMOTE_ARGUMENTS! --app-image !APP_IMAGE! --db-image !DB_IMAGE!"
if /I "!CHECK_ONLY!"=="true" set "REMOTE_ARGUMENTS=!REMOTE_ARGUMENTS! --check"

echo Running Scarab bootstrap on %SSH_HOST%...
ssh.exe -tt -o BatchMode=yes "%SSH_HOST%" "bash ~/%REMOTE_SCRIPT%!REMOTE_ARGUMENTS!"
set "BOOTSTRAP_STATUS=!ERRORLEVEL!"
endlocal & set "BOOTSTRAP_STATUS=%BOOTSTRAP_STATUS%"

ssh.exe -o BatchMode=yes "%SSH_HOST%" "rm -f ~/%REMOTE_SCRIPT%" >nul 2>&1
if not "%BOOTSTRAP_STATUS%"=="0" (
    echo ERROR: Remote Scarab bootstrap failed with exit code %BOOTSTRAP_STATUS%.
    exit /b %BOOTSTRAP_STATUS%
)

echo Remote Scarab bootstrap completed successfully.
exit /b 0

:show_help
echo Usage:
echo   scarab-bootstrap.bat --host SSH_HOST [OPTIONS]
echo.
echo Mandatory arguments:
echo   --host SSH_HOST
echo       SSH host or alias for a reachable Linux container host. Key-based
echo       authentication must already be configured.
echo.
echo Conditionally mandatory arguments:
echo   --app-image IMAGE --db-image IMAGE
echo       The two image arguments must be supplied together. They are optional
echo       in test; production requires both --app-image and --db-image.
echo.
echo Optional arguments:
echo   --branch BRANCH
echo       Git branch to clone instead of the latest published release.
echo   --instance NAME
echo       Instance namespace. Default: scarab.
echo   --environment test^|production
echo       Deployment environment. Default: test.
echo   --service-user USER
echo       Rootless Linux service account. Default: the remote invoking user.
echo   --db-port PORT
echo       Host port published to PostgreSQL port 5432. Default: 5432.
echo   --db-bind-address IPV4
echo       Optional non-loopback unicast IPv4 address assigned to the Linux
echo       host. If omitted, a single such address is detected automatically;
echo       multiple addresses require this argument.
echo   --check
echo       Validate access, prerequisites, source, and arguments without
echo       installing or updating the instance.
echo   -h, --help
echo       Show this help message.
echo.
echo Defaults:
echo   current local Git branch when this script is inside a checkout;
echo   otherwise the latest published GitHub release; environment test;
echo   remote SSH user; no --instance argument, so scarab-deploy uses its
echo   default instance scarab.
echo.
echo The Windows script requires ssh.exe and scp.exe with key-based access. It
echo uploads scarab-bootstrap.sh to the Linux user's home and runs it there.
exit /b 0