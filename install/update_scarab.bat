echo off
echo.
echo Updating files in the deployment directory from the local repository
echo.

echo Copying the updated files to the deployment directory
copy /Y ..\src\*.py C:\ProgramData\Anatel\Scarab\src
echo ..\src\default_config.json
copy /Y ..\src\default_config.json C:\ProgramData\Anatel\Scarab\src\default_config.json
echo ..\data\examples\*.json
copy /Y ..\data\examples\*.json C:\ProgramData\Anatel\scarab\config
echo ..\pyproject.toml
copy /Y ..\pyproject.toml C:\ProgramData\Anatel\scarab
echo ..\uv.lock
copy /Y ..\uv.lock C:\ProgramData\Anatel\scarab

echo.
echo Updating the virtual environment
pushd C:\ProgramData\Anatel\Scarab
uv sync
popd

echo.
echo Update finished
echo.


