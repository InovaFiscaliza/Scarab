@echo off
REM Extract the tarball, install and initialize UV to run Scarab

REM Extract the tarball to the current directory
tar -xf scarab.tgz 

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract scarab.tgz
    exit /b %errorlevel%
)

REM Install UV
cd scarab
npm install -g .

REM Initialize UV
uv init

