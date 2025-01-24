# Tests

This folder includes several tests to validate the scripts and modules.

Tests are proposed as a set of cmd scripts to run in windows environment that will set folders and files in the test folder.

Afterwards, test can be performed by running the script in CMD or using the debugger configuration in Visual Studio Code.

```cmd
uv run ..\src\scarab.py config.json
```

## TEST_BASIC.bat

Use `TEST_BASIC.bat` to deploy and reset the sandbox folder structure.

- Expected results for a first execution of scara.py:

> Get metadata content from 2 files in post folder and  publish then under the get folder.
> Raw txt files are moved to the get folder under the raw subfolder.
> No files or subfolders should remain in temp, trash and post folder.
> Store folder should contain the original files.
> trash should contain the en empty log file and the file "file_to_trash.empty" that was moved from the post folder under the delete subfolder "folder_to_delete".

To test script termination you maypressing `ctrl+c` 

- Second execution:

> The script will start. Log file should be moved to trash and a new log file created.

To test script termination equivalent to service stop use the command `kill -9 <pid>` in another terminal.

Where pid is number displayed in the log file and screen, between square brackets after the script name.