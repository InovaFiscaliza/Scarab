
<div id="navigation-template" style="display: none;">
    <br><br>
    <a href="../README.md">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#indexerd-md-top">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

<details>
    <summary>Table of Contents</summary>
    <ol>
        <li><a href="#About_Scarab_Tests">About Scarab Tests</a></li>
        <li><a href="#Scripts_and_Files">Scripts and Files</a></li>
        <li><a href="#Tests">Tests</a></li>
        <li><a href="#setup">Setup</a></li>
        <li><a href="#roadmap">Roadmap</a></li>
        <li><a href="#contributing">Contributing</a></li>
        <li><a href="#license">License</a></li>
    </ol>
</details>

# About Scarab Tests

This folder includes several tests to validate the scripts and modules.

Tests are proposed as a set of cmd scripts to run in windows environment that will set folders and files in the tests\sandbox folder.

Test are described to be run directly from the command line in order to test features such as interruption handling from `ctrl+c` and  `kill -9 <pid>` commands.

If running in debbuging mode, using VSCode or other IDE, the interruption may not work and stop debbuging command may be required.

For VSCode, the debugger configuration is already set in the .vscode folder to run the script with the config.json file within the sandbox folder.

<script>insertNavigation();</script>

## Initial test

Use `1test_simple_XLSX.bat` to set the sandbox folder structure for the test.

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed from the tests folder in the repository path, the following results are expected:

> * Get metadata content from 2 files in post folder and publish then under the get folder.
> * Raw txt files are moved to the get folder under the raw subfolder.
> * No files or subfolders should remain in temp, trash and post folder, deleting the "folder_to_delete" folder and moving "file_to_trash.empty" to trash.
> * Store folder should contain the original XLSX files.
> * Trash should contain an empty log file renamed with timestamp and another log file moved from the get folder, and the file that was moved from the post folder.

To finish the test use `ctrl+c`. It may take up to 10 seconds to stop the script after the interruption is received and registered in the log.


## Metadata update test

Use `2test_update_XLSX.bat` to set the sandbox folder structure for the test

This tests has the basic same data as the output from the first test, adding a new metadata file to be processed.

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed from the tests folder in the repository path, the following results are expected:

> * File `monitorRNI_test_temp_update.xlsx` will be processed and moved from the temp folder to store folder, simulating a missing file due to broken execution.
> * Lines will be updated in the metadata file `monitorRNI.xlsx` in the get folder. Modifications are indicated in column `entidade`.
> * File `monitorRNI_test_temp_update.xlsx` will be moved to the store folder.
> * Trash should contain two log files renamed with timestamp and another log file moved from the get folder.

To finish the test you may use the command `kill -9 <pid>` from another terminal. This will test script termination equivalent to service stop command.

The pid is number displayed in the log file and screen, between square brackets after the script name.

## Multiple input and output folders test

Use `3test_multiple_in_out.bat` to set the sandbox folder structure for the test

This tests has the basic same data as the output from the previous tests, adding a new metadata files to be processed from multiple sources and output to multiple folders.

After `uv run .\src\scarab.py .\tests\sandbox\config.json` is executed from the root repository path, the following results are expected:

> * File `monitorRNI_test_temp_update.xlsx` will be processed and moved from the temp folder to store folder, simulating a missing file due to broken execution.
> * Folder `get_other`, that was initially empty, should have the same content as the `get` folder, including pre-existing files in the raw subfolder.

## Disable overwrite and with same files coming from different sources

Use `4test_overwrite_and_conflict.bat` to set the sandbox folder structure for the test

This tests has the basic same data as the output from the previous, adding a new metadata files to be processed from multiple sources and output to multiple folders.

After `uv run .\src\scarab.py .\tests\sandbox\config.json` is executed from the root repository path, the following results are expected:

> * Test the use of variant names for the log file (if the timestamp is the same) and the use of the `overwrite` flag in the config file.
> * Same file posted in multiple folders are processed only once.

## Change columns and multiple keys

Use `5test_multiple_keys_variable_columns.bat` to set the sandbox folder structure for the test

This tests has the basic same data as the output from the second test, adding but the update is done changing columns that are not mapped in the config file. 

* Columns "entidade" and "Endereco" are removed
* Columns "NEW1" and "NEW2" are added
* Column NEW1 is added to the config file
* Key is now defined as a list of columns: ["Fistel","N° estacao","Emax - Data da Medição","Emax - Latitude","Emax - Longitude"]

After `uv run .\src\scarab.py .\tests\sandbox\config.json` is executed from the root repository path, the following results are expected:

> * File `monitorRNI_test_temp_update.xlsx` will be processed and moved from the post folder to store folder.
> * Lines will be updated in the metadata file `monitorRNI.xlsx` in the get folder. Modifications can be noted in columns `NEW1` and `NEW2`, that should be present only in the updated and new rows.
> New rows should be added whenever one of the columns associated with the keys are changed.

## Heavy Load Test

Use `6test_heavy_load_missing_data.bat` to set the sandbox folder structure for the test

This tests has larger catalog file to process and is usefull for performance testing. Based on Regulatron test data.

## Creating new tests

Edit the content of the sandbox folder to create the desired structure, making modifications in the config.json file if necessary.

Run the following command to create the corresponding TGZ file:

```cmd
tar -czvf TEST_NAME.tgz sandbox
```

Where `TEST_NAME` is the name of the test to be used in the batch file.

Create the new test modifying the `TEST_NAME.bat` file, using the TEST_NAME where required.

<script>
    function insertNavigation() {
        var template = document.getElementById('navigation-template').innerHTML;
        document.write(template);
    }
</script>
