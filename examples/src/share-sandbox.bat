@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "SANDBOX_DIR=%~dp0..\sandbox"
set "SHARE_NAME=ScarabSandbox"
set "SHARE_USER=%USERDOMAIN%\%USERNAME%"

:parse_arguments
if "%~1"=="" goto arguments_parsed
if /I "%~1"=="-h" goto show_help
if /I "%~1"=="--help" goto show_help
if /I "%~1"=="--share-name" (
    if "%~2"=="" goto missing_value
    set "SHARE_NAME=%~2"
    shift
    shift
    goto parse_arguments
)
if /I "%~1"=="--user" (
    if "%~2"=="" goto missing_value
    set "SHARE_USER=%~2"
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
if not exist "%SANDBOX_DIR%\." (
    echo ERROR: examples\sandbox was not found: %SANDBOX_DIR%
    exit /b 1
)

where.exe powershell.exe >nul 2>&1 || (
    echo ERROR: Required command not found: powershell.exe
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; if ($env:SHARE_NAME -notmatch '^[A-Za-z][A-Za-z0-9_-]*$') { throw 'Invalid share name.' }; $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent()); if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this script from an elevated terminal.' }; $path = (Resolve-Path -LiteralPath $env:SANDBOX_DIR).Path; $existing = Get-SmbShare -Name $env:SHARE_NAME -ErrorAction SilentlyContinue; if ($existing -and $existing.Path -ne $path) { throw ('SMB share already points to another path: ' + $existing.Path) }; if (-not $existing) { New-SmbShare -Name $env:SHARE_NAME -Path $path -ChangeAccess $env:SHARE_USER -FolderEnumerationMode AccessBased | Out-Null } else { Grant-SmbShareAccess -Name $env:SHARE_NAME -AccountName $env:SHARE_USER -AccessRight Change -Force | Out-Null }; Write-Output ('Shared ' + $path + ' as \\' + $env:COMPUTERNAME + '\' + $env:SHARE_NAME + ' for ' + $env:SHARE_USER)"
if errorlevel 1 exit /b 1

echo Confirm that the Windows network profile and firewall allow SMB only from the trusted host.
exit /b 0

:show_help
echo Usage:
echo   share-sandbox.bat [--share-name NAME] [--user WINDOWS_ACCOUNT]
echo.
echo Publishes examples\sandbox as an SMB share. Run from an elevated terminal.
echo The Windows account password is never requested or stored by this script.
exit /b 0