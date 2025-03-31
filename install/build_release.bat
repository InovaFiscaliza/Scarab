@echo off
rmdir /S /Q .\temp
mkdir temp
cd temp
mkdir .\scarab
mkdir .\scarab\src
mkdir .\scarab\config
mkdir .\scarab\task_manager
mkdir .\scarab\temp
copy /V /Y ..\..\src\*.py .\scarab\src\
copy /V /Y ..\..\*.toml .\scarab\
copy /V /Y ..\..\data\examples\*.json .\scarab\config\
copy /V /Y ..\..\data\examples\*.xml .\scarab\task_manager\
tar -czvf ..\scarab_release.tgz .\scarab
cd ..
rmdir /S /Q .\temp

REM Release package ready in the temp folder. You may delete it after use.