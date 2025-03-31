@echo off
REM Extract the tarball, install and initialize UV to run Scarab

REM Extract the tarball to the current directory
tar -xf scarab_release.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract scarab_release.tgz
    exit /b %errorlevel%
)

REM Install UV
winget install --id=astral-sh.uv  -e


REM Initialize UV
cd scarab
uv sync
