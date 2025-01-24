# Tests

This folder includes several tests to validate the scripts and modules.

Tests are proposed as a set of cmd scripts to run in windows environment that will set folders and files in the test folder.

Afterwards, test can be performed by running the script in CMD or using the debugger configuration in Visual Studio Code.

```cmd
uv run ..\src\scarab.py config.json
```

## TEST_BASIC.bat

- First execution:

> Get metadata content from 2 files in post folder and  publish then under the get folder.
> Raw txt files are moved to the get folder under the raw subfolder.
> No files or subfolders should remain in temp, trash and post folder.
> Store folder should contain the original files.
> trash should contain the en empty log file and the file "file_to_trash.empty" that was moved from the post folder under the delete subfolder "folder_to_delete".
>
> Terminal will not be closed and to finish the test, press ctrl+c.

- Second execution:

> The script will start. Log file should be moved to trash and a new log file created.