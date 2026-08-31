@echo off
REM Updates a selected test archive in examples\data using contents of examples\sandbox.
REM One argument must be provided.
REM It must contain only digits and represent a number from 0 through 99.

setlocal EnableExtensions EnableDelayedExpansion

where.exe tar.exe >nul 2>&1
if errorlevel 1 (
	echo ERROR: tar.exe was not found in PATH.
	exit /b 1
)

set "SCRIPT_DIR=%~dp0"
set "EXAMPLES_DIR=%SCRIPT_DIR%.."
set "SANDBOX_DIR=%EXAMPLES_DIR%\sandbox"
set "DATA_DIR=%EXAMPLES_DIR%\data"

if not exist "%SANDBOX_DIR%\." (
	echo ERROR: Sandbox directory not found: "%SANDBOX_DIR%"
	exit /b 1
)

if not exist "%DATA_DIR%\." (
	echo ERROR: Data directory not found: "%DATA_DIR%"
	exit /b 1
)

if not "%~2"=="" (
	echo ERROR: Only one archive number may be specified.
	exit /b 1
)

if "%~1"=="" (
	echo ERROR: Archive number must be specified.
	exit /b 1
)

set "input=%~1"
set "invalid="
for /f "delims=0123456789" %%A in ("!input!") do set "invalid=%%A"
if defined invalid (
	echo ERROR: Archive number must contain only digits and represent a number from 0 through 99.
	exit /b 1
)

set "normalized="
for /f "tokens=* delims=0" %%A in ("!input!") do set "normalized=%%A"
if not defined normalized set "normalized=0"
set /a number=normalized

if !number! LSS 0 (
	echo ERROR: Archive number must be between 0 and 99.
	exit /b 1
)
if !number! GTR 99 (
	echo ERROR: Archive number must be between 0 and 99.
	exit /b 1
)

if !number! LSS 10 (
	set "serial=0!number!"
) else (
	set "serial=!number!"
)

:select_archive
set "archive=%DATA_DIR%\test_!serial!.tgz"

if not exist "!archive!" (
	echo ERROR: Archive not found: "!archive!"
	exit /b 1
)

tar.exe -czf "!archive!" -C "%EXAMPLES_DIR%" sandbox
if errorlevel 1 (
	echo ERROR: Failed to update archive: "!archive!"
	exit /b 1
)

echo Updated archive: "!archive!"
exit /b 0
