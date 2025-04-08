
<details>
    <summary>Table of Contents</summary>
    <ol>
        <li><a href="#About_Scarab_Tests">About Scarab Tests</a></li>
        <li><a href="#Creating_new_tests">Creating new tests</a></li>
        <li><a href="#Initial_test">Initial test</a></li>
        <li><a href="#Metadata_update_test">Metadata update test</a></li>
        <li><a href="#Multiple_input_and_output_folders_test">Multiple input and output folders test</a></li>
        <li><a href="#Disable_overwrite_and_with_same_files_coming_from_different_sources">Disable overwrite and with same files coming from different sources</a></li>
        <li><a href="#Change_columns_and_multiple_keys">Change columns and multiple keys</a></li>
        <li><a href="#Heavy_Load_Test">Heavy Load Test</a></li>
        <li><a href="#SCH_Null_Data_Test">SCH Null Data Test</a></li>
        <li><a href="#Special_characters_test">Special characters test</a></li>
        <li><a href="#Mixed_metadata_formats">Mixed metadata formats</a></li>
        <li><a href="#Null_Data_Filename_Test">Null Data Filename Test</a></li>
        <li><a href="#Input_files_and_folders_to_ignore">Input files and folders to ignore</a></li>
    </ol>
</details>

# About Scarab Tests

This folder includes several tests to validate the scripts and modules.

Tests are proposed as a set of cmd scripts to run in windows environment that will set folders and files in the tests\sandbox folder.

Test are described to be run directly from the command line in order to test features such as interruption handling from `ctrl+c` and  `kill -9 <pid>` commands.

If running in debugging mode, using VSCode or other IDE, the interruption may not work and stop debugging command may be required.

For VSCode, the debugger configuration is already set in the .vscode folder to run the script with the config.json file within the sandbox folder.

## Creating new tests

Edit the content of the sandbox folder to create the desired structure, making modifications in the config.json file if necessary.

Run the following command to create the corresponding TGZ file:

```cmd
tar -czvf TEST_NAME.tgz sandbox
```

Where `TEST_NAME` is the name of the test to be used in the batch file.

Create the new test modifying the `xtest_TEST_NAME.bat` file, using the TEST_NAME where required and using the number of the test as prefix for convienience.

<div>
    <a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

# Tests

<br> 

## Initial test

Use `1test_simple_XLSX.bat` to set the sandbox folder structure for the test.

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed from the tests folder in the repository path, the following results are expected:

> * Get metadata content from 2 files in post folder and publish then under the get folder.
> * Raw txt files are moved to the get folder under the raw subfolder.
> * No files or subfolders should remain in temp, trash and post folder, deleting the "folder_to_delete" folder and moving "file_to_trash.empty" to trash.
> * Store folder should contain the original XLSX files.
> * Trash should contain an empty log file renamed with timestamp and another log file moved from the get folder, and the file that was moved from the post folder.

To finish the test use `ctrl+c`. It may take up to 10 seconds to stop the script after the interruption is received and registered in the log.

<div>
    <a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

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

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

## Multiple input and output folders test

Use `3test_multiple_in_out.bat` to set the sandbox folder structure for the test

This tests has the basic same data as the output from the previous tests, adding a new metadata files to be processed from multiple sources and output to multiple folders.

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed, the following results are expected:

> * File `monitorRNI_test_temp_update.xlsx` will be processed and moved from the temp folder to store folder, simulating a missing file due to broken execution.
> * Folder `get_other`, that was initially empty, should have the same content as the `get` folder, including pre-existing files in the raw subfolder.

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

## Disable overwrite and with same files coming from different sources

Use `4test_overwrite_and_conflict.bat` to set the sandbox folder structure for the test

This tests has the basic same data as the output from the previous, adding a new metadata files to be processed from multiple sources and output to multiple folders.

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed, the following results are expected:

> * Test the use of variant names for the log file (if the timestamp is the same) and the use of the `overwrite` flag in the config file.
> * Same file posted in multiple folders are processed only once.

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

## Change columns and multiple keys

Use `5test_multiple_keys_variable_columns.bat` to set the sandbox folder structure for the test

This tests has the basic same data as the output from the second test, adding but the update is done changing columns that are not mapped in the config file. 

* Columns "entidade" and "Endereco" are removed
* Columns "NEW1" and "NEW2" are added
* Column NEW1 is added to the config file
* Key is now defined as a list of columns: ["Fistel","N° estacao","Emax - Data da Medição","Emax - Latitude","Emax - Longitude"]

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed, the following results are expected:

> * File `monitorRNI_test_temp_update.xlsx` will be processed and moved from the post folder to store folder.
> * Lines will be updated in the metadata file `monitorRNI.xlsx` in the get folder. Modifications can be noted in columns `NEW1` and `NEW2`, that should be present only in the updated and new rows.
> New rows should be added whenever one of the columns associated with the keys are changed.

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

## Heavy Load Test

Use `6test_heavy_load_missing_data.bat` to set the sandbox folder structure for the test

This tests has larger catalog file to process and is useful for performance testing. Based on Regulatron test data.

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed, the following results are expected:

Results are expected to be similar to the previous tests, but with a larger file to process and errors such as missing key data, key conflicts and variable columns.

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>


## SCH Null Data Test

Use `7test_sch_null_data.bat` to set the sandbox folder structure for the test

This tests also has larger number of files to process and is useful for performance testing. Based on SCH test data.

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed, the following results are expected:

Different from the previous test, at this time there is no data, but only tables to process. There are conflicts in file naming and missing data to be handled.

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

## Special characters test

Use `8test_special_chars.bat` to set the sandbox folder structure for the test

This tests will try to insert data with special characters in the column names.

The `config.json` file includes a required column with all characters allowed, but and the metadata file has a column with a special character that is not allowed.

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed.

Its expected that all metadata files to be moved to trash. Messages should point that the column with all characters allowed is not present in the metadata file. Check if the name is correct.

If the `config.json` file is changed to remove the column with all characters, the test should run without errors and the column with special characters should be renamed, removing this characters.

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

## Mixed metadata formats

Use `9test_mixed_metadata.bat` to set the sandbox folder structure for the test

This test uses two configuration files, simultaneously processing metadata files with different formats from the same source. POST folder is ommited in the config files and also many configurations are left as default. Json input files uses two distinct dictionaries to represent complementary  metadata of the same data files.

The test need to be run twice using two different configuration files, either using independent terminal instances or sequentially do: `uv run ..\src\scarab.py .\sandbox\config.json` and `uv run ..\src\scarab.py .\sandbox\config_alt.json`.

Two metadata files will be produced, one consolidating the xlsx files that summarize the raw data and other the two different types of json files, that provide metadata fot the raw files.

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

## Null Data Filename Test

Use `Atest_mixed_metadata.bat` to set the sandbox folder structure for the test

This test uses search for data file references where the columns with filenames is null

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed.

Metadata files will be consolidated and data files will be left in the temp folder, waiting for clean operation, which may be triggered according to the files timestamp.

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

## Input files and folders to ignore

Use `Btest_mixed_metadata.bat` to set the sandbox folder structure for the test

This test the same performed in the initial test, adding a folder and a file to be ignored in the input folders.

After `uv run ..\src\scarab.py .\sandbox\config.json` is executed.

The file `.file_to_ignore` and folder `folder_to_ignore` should be ignored in the input folders.

<div>
    < a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="../docs/images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-tests">
        <img align="right" width="40" height="40" src="../docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>