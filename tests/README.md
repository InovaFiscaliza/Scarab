# Tests

This folder includes several tests to validate the scripts and modules.

Tests are proposed as a set of cmd scripts to run in windows environment.

## TEST_BASIC.bat

- First execution:

> Get metadata content from 2 files in post folder and  publish then under the get folder. Raw txt files are moved to the output folder as well. No files should remain in temp, trash and post folder. Store folder should contain the original files.
> 
> Terminal will not be closed and to finish the test, press ctrl+c.

- Second execution:

> use the command 'uv run ..\src\scarab.py config.json' under the same terminal executed before. The script will start. Log file should be moved to trash and a new log file created.