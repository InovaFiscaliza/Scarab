@echo off
setlocal

REM Set the target directory
set "target_dir=C:\Users\sfi.office365.pd\github\scarab\tests\sandbox\post"

REM Change to the target directory
cd /d "%target_dir%"

REM Loop through all .pdf files in the target directory
for %%f in (*.pdf) do (
    REM Create an empty file with the same name
    echo.> "%%f"
)

echo All .pdf files have been replaced with empty files.
endlocal