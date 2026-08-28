@echo off
REM Creates a gzip-compressed tar archive of the examples\sandbox directory.
REM Saves the archive in examples\store as test_XX.tgz, using the next serial after
REM the highest numeric suffix found in existing test_*.tgz files. Serial numbers are
REM limited to 01 through 99.
REM Requires tar.exe in PATH and exits with an error if validation or archive creation fails.

setlocal enabledelayedexpansion

where.exe tar.exe >nul 2>&1
if errorlevel 1 (
	echo ERROR: tar.exe was not found in PATH.
	exit /b 1
)

set "SCRIPT_DIR=%~dp0"
set "EXAMPLES_DIR=%SCRIPT_DIR%.."
set "SANDBOX_DIR=%EXAMPLES_DIR%\sandbox"
set "STORE_DIR=%EXAMPLES_DIR%\store"

if not exist "%SANDBOX_DIR%\." (
	echo ERROR: Sandbox directory not found: "%SANDBOX_DIR%"
	exit /b 1
)

if not exist "%STORE_DIR%\." (
	echo ERROR: Store directory not found: "%STORE_DIR%"
	exit /b 1
)

set /a highest=0
for %%F in ("%STORE_DIR%\test_*.tgz") do (
	if exist "%%~fF" call :consider_archive "%%~nxF"
)

set /a next=highest+1
if !next! GTR 99 (
	echo ERROR: This script supports only up to 99 examples.
	exit /b 1
)
if !next! LSS 10 (
	set "serial=0!next!"
) else (
	set "serial=!next!"
)
set "archive=%STORE_DIR%\test_!serial!.tgz"

if exist "!archive!" (
	echo ERROR: Archive already exists: "!archive!"
	exit /b 1
)

tar.exe -czf "!archive!" -C "%EXAMPLES_DIR%" sandbox
if errorlevel 1 (
	echo ERROR: Failed to create archive: "!archive!"
	exit /b 1
)

echo Created archive: "!archive!"
exit /b 0

:consider_archive
set "suffix="
set "non_digit="
for /f "tokens=1,* delims=_" %%A in ("%~n1") do (
	if /i "%%A"=="test" set "suffix=%%B"
)
if not defined suffix exit /b 0

for /f "delims=0123456789" %%A in ("!suffix!") do set "non_digit=%%A"
if defined non_digit exit /b 0

set "normalized="
for /f "tokens=* delims=0" %%A in ("!suffix!") do set "normalized=%%A"
if not defined normalized set "normalized=0"
set /a current=normalized
if !current! GTR !highest! set /a highest=current
exit /b 0


