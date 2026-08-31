@echo off
REM Extracts a selected test archive from the examples\data directory into the current directory.
REM With no argument, extracts test_00.tgz. Otherwise, the argument must be
REM a number from 1 through 99, with or without leading zeroes.

setlocal EnableExtensions EnableDelayedExpansion

where.exe tar.exe >nul 2>&1
if errorlevel 1 (
	echo ERROR: tar.exe was not found in PATH.
	exit /b 1
)

set "SCRIPT_DIR=%~dp0"
set "EXAMPLES_DIR=%SCRIPT_DIR%.."
set "DATA_DIR=%EXAMPLES_DIR%\data"
set "TARGET_DIR=%EXAMPLES_DIR%"

if not "%~2"=="" (
	echo ERROR: Only one archive number may be specified.
	exit /b 1
)

if "%~1"=="" (
	set "serial=00"
	goto select_archive
)

set "input=%~1"
set "invalid="
for /f "delims=0123456789" %%A in ("!input!") do set "invalid=%%A"
if defined invalid (
	echo ERROR: Archive number must contain only digits from 1 through 99.
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

rmdir /s /q "%TARGET_DIR%\sandbox" >nul 2>&1

tar.exe -xzf "!archive!" -C "%TARGET_DIR%"
if errorlevel 1 (
	echo ERROR: Failed to extract archive: "!archive!"
	exit /b 1
)

echo Extracted archive: "!archive!"
exit /b 0
