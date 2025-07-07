@echo off
copy /Y ..\src\*.py C:\ProgramData\Anatel\Scarab\src
copy /Y ..\src\default_config.json C:\ProgramData\Anatel\Scarab\src\default_config.json
copy /Y ..\data\examples\*.json C:\ProgramData\Anatel\scarab\config
copy /Y ..\pyproject.toml C:\ProgramData\Anatel\scarab
copy /Y ..\uv.lock C:\ProgramData\Anatel\scarab

REM.
REM Updated files in the deployment directory from the local repository
REM.



