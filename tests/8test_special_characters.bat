@echo off
REM Clean sandbox folder
if exist sandbox (
    rmdir /s /q sandbox
)

REM Extract test_basic.zip using 7zip
tar -xf test_8.tgz

REM Check if extraction was successful
if %errorlevel% neq 0 (
    echo Failed to extract test_basic.zip
    exit /b %errorlevel%
)

echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
echo.
echo Test with special characters in columns name.
echo.
echo First run will give warnings and not upload the data. 
echo In the second run, will update the output and remove invalid characters
echo    from column names
echo.
echo Run the script twice, either using two terminals or sequentially using:
echo.
echo     uv run ..\src\scarab.py .\sandbox\config.json
echo.
echo     move .\sandbox\trash\Anuncios.xlsx .\sandbox\get\Anuncios.xlsx
echo.
echo     uv run ..\src\scarab.py .\sandbox\config_alt.json
echo.
echo Check if the output is as described in README.md.
echo.
echo ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

exit /b 0