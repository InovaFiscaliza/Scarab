
<details>
    <summary>Table of Contents</summary>
    <ol>
        <li><a href="#About_Scarab_Documentation">About Scarab Documentation</a></li>
    </ol>
</details>

# About Scarab Documentation

Scarab is configured through a json file

You may get examples in the test setups. Check the [tests folder](../tests/README.md) for more details.

Optional parameters are set to default values if not included in the configuration file. These default parameters are defined in the [default_config.json](../src/default_config.json) file.

Keys in the json file are described in the table below:

| json key [root] | json key [branch] | Description | Use | Example |
| --- | --- | --- | --- | --- |
| **name** | | `String`. Configuration name to be used in log messages | Optional | default: "unnamed" |
| **check period in seconds** | | `Integer`. Time in seconds between checks of post and temp folders | Optional | default: 10 |
| **clean period in hours** | | `Integer`. Time in hours between cleaning post and temp folders to remove to trash files with the correct extension but not processed, due to missing metadata | Optional | default: 1 |
| **last clean** | | `String`. Date and time of the last clean operation. Is updated whenever the clean methods is executed using the format _"%Y-%m-%d_ _%H:%M:%S"_. Should not be manually edited, but can be left blank or even not included in the initial configuration file, condition in which the clean operation will be executed in the initial verifications and a new value will be set. | Optional | default: "2025-02-21 12:00:00" |
| **maximum errors before exit** | | `Integer`. Maximum number of errors before the program exits. Attempts will be made at intervals defined by _"check_ _period_ _in_ _seconds"_ | Optional | default: 5 |
| **maximum file variations** | | `Integer`. Maximum number of filename variations before an error is raised and the program exits. Filename variations are used when trash overright is set to false and files with the same name are saved with added number at the end, which will vary from 1 to the maximum defined number of variations. | Optional | default: 100 |
| **character scope** | | `String`. Characters allowed in column names. If set to _"all"_, any character is allowed, including invisible signaling characters. Otherwise, Characters should be defined as in a regex string. | Optional | default to include latin chars and a bit more "[^A-Za-z0-9çÇãÃõÕáÁéÉíÍóÓúÚàÀèÈêùÙÊôÔîÎôÔûÛëËïÏüÜÿŒœÆæ%\|?!.,><"-_ ]+" |
| **null string values** | | `List of Strings`. List of strings to be considered as null values. If not included, the default list will be used. | Optional | default: ["\<NA>", "NA", "N/A", "na", "Na", "n/a", "None", "null", "", "pd.NA", "pd.NaT", "pd.NA", "pd.NaT", "nan", "NaN", "NAN", "missing value", "Missing Value", "MISSING VALUE"] |
| **default worksheet key** | | `String`. Default key to be used for the worksheet that will retain single table values or non mapped values in the json root. Default configuration and may be changed if the defined default string key needs to be used for other purposes. | Optional | default: "\_" |
| **default worksheet name** | | `String`. Default value for the worksheet name. If the value assigned in **table names** object to the default key is equal to this value, the name of the configuration (**name**) will be used for the worksheet. This is de default configuration and may be changed if the defined default string needs to be used for other purposes. | Optional | default: "\<name>" |
| **overwrite data in store** | | `Boolean`. if _True_, new files with the same name will overwrite files in store folder, if _False_, previously existing files will be moved to trash. | Optional | default: false |
| **overwrite data in get** | | `Boolean`. if _True_, new files with the same name will overwrite files in get folder, if _False_, previously existing files will be moved to trash. | Optional | default: true |
| **overwrite data in trash** | | `Boolean`. if _True_, new files with the same name will overwrite files in trash folder, if _False_, previously existing files will be moved to trash. | Optional | default: false |
| **discard invalid data files** | | `Boolean`. if _True_, files with the unrecognized extension or content will me moved to trash as soon as detected, if _False_ files will be moved to trash only during clean operations. | Optional | default: false |
| | | | | |
| **log** | - | Root key to log configuration keys | Optional | - |
| log | **level** | `String`. Log level to be used. Possible values are _DEBUG_, _INFO_, _WARNING_, _ERROR_ or _CRITICAL_ | Optional | default: "debug" |
| log | **screen output** | `Boolean`. If _True_, log messages will be printed to the screen | Optional | default: true |
| log | **file output** | `Boolean`. If _True_, log messages will be written to a file | Optional | default: false |
| log | **file path** | `List of Strings`. Path to the log file. More than one path may be supplied in order to simultaneously store log events into multiple files | Optional | default: []. example ["./sandbox/get/log.txt", "./sandbox/get_other/log.txt"] |
| log | **format** | `List of Strings`. Format of the log message as defined in [logging](https://docs.python.org/3/howto/logging.html#formatters)  | Optional | default: ["%(asctime)s", "%(module)s: %(funcName)s:%(lineno)d", "%(name)s[%(process)d]", "%(levelname)s", "%(message)s"] |
| log | **colour sequence** | `List of Strings`. Colour sequence to be used in the log message. List should have the same size as the one used for format and colours will be assigned in the respective elements. See [advanced logging](https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output) for more information. | Optional | default: ["32m", "35m", "34m", "30m", "0m"] |
| log | **separator** | `String`. Separator to be used between log message elements. If required, spaces must be added to this string. | Optional | default: " \| " |
| log | **overwrite log in trash** | `Boolean`. If _True_, log files in trash will be overwritten, if _False_, new log files will be created with a timestamp suffix | Optional | default: false |
| | | | | |
| **folders** | - | Root key to folder configuration keys | Mandatory | - |
| folders | **post** | `List of Strings`. Path to the post folders. More than one path may be supplied in order to simultaneously process files from multiple folders. POST folder may not be required if files are posted directly in the temp folder, reducing file operations. | Optional | default: []. example: ["./sandbox/post","./sandbox/post_other"] |
| folders | **temp** | `String`. Path to the temp folder | Mandatory | example: "./sandbox/temp" |
| folders | **trash** | `String`. Path to the trash folder | Mandatory | example: "./sandbox/trash" |
| folders | **store** | `String`. Path to the store folder | Mandatory | example: "./sandbox/store" |
| folders | **get** | `Dict with Lists of Strings`. Dictionary in which for each key associated with a regex pattern defined in the "data file regex", a list of target folders to which matching files should be moved to. GET folders may not be required if only metadata files are handled | Optional | default: {}. example: {"json":["C:/users/johnson/json"]} |
| | | | | |
| **files** | | Root key to file configuration keys | Mandatory | - |
| files | **metadata file regex** | `String`. Regex pattern to be used to select files that may contain metadata. May not be required if only file move operations are performed. Valid options include MS Excel, JSON and CSV files. | Optional | default: "". example: ".\*\\\\.json\$" for json files, or ".\*\\\\.(xlsx\|csv)\$" for CSV or XLSX files |
| files | **data file regex** | `Dict with Strings`. Dictionary with keys for association with the folders listed in the GET item, with regex string patterns to be used to select files that should be moved to the indicated destination folders. Operations with data files are performed after operation with metadata files, so if the same matching regex is used, only files that do not contain metadata will be moved to the indicated folders. Metadata files are moved to the store folders after processing. In this case is also essential to set the option _"discard_ _invalid_ _data_ _files"_ must be set to _False_. This will allow the processing of the data files after they fail to be recognized as metadata files. May not be required if only metadata operations are performed. | Optional | default: {}. example: {"json":".\*\\\\.json\$"}  |
| files | **catalog names** | `List of Strings`. Path to the catalog XLSX files. More than one path may be supplied in order to simultaneously process files from multiple folders | Optional | default: [] |
| files | **table names** | `Dict`. Dictionaries containing keys to be found in the json input metadata files and the corresponding human readable name to be used as worksheet names in the XLSX output. e.g [{"json_root_table_name": "table_name"}, ...]. Key "\_" is the default value and used to reference all data in the first level of the json tree, for keys are not defined as other elements dictionary. The value associated with the default "\_" will be used for CSV and XLSX input. If not defined, will use the value of the `name` tag in the configuration file as the table name. | Optional | default: {"_":"\<name>"} |
| files | **input to ignore** | `List of Strings`. List with files and folders to ignore in the input folders. Files within ignored folders will not be ignored. Use exact names only, including relative path to the input folder. | Optional | default: [] |
| | | | | |
| **metadata** | | Root key to metadata configuration keys | Optional | - |
| metadata | **key** | `List of Dict`. `Dict with List values`. Each table key will include a list of strings with columns to be used as key in the metadata for each table. This is used for merging data and allow update. Default key "_" is to be used to define required columns for single table input metadata. Each row will have a single combination of the key columns in the output tables. If new data is posted with the same key column combination, the data will be updated. | Optional | default: {"_":[]} |
| metadata | **association** | `Dict of Dict`. List containing dictionaries for table association through the use of "Primary Keys" (PK) and "Foreign Keys" (FK) when processing multi-table data. The value associated with the `PK` key corresponds to the column name to be used as primary key for that table, and the dictionary associated with the `FK` key indicates the name of columns with data association with other tables through their PK values. A table may have none or a single PK column, and may include none or multiple columns with references to other tables. The PK and FK values are valid only within a single file. To use multiple files, an external indexing system must be used and Scarab may be used with multiple workflows, one for each table. e.g. `{"DimData1": {"PK": "PK1", "FK":{}},"FactData": {"PK":"","FK": {"DimData1": "FK1"}}}`, where `DimData1` and `FactData` are table names defined in the json data file in which the `FactData` table includes a column named `FK1` that contains values that associate each row with row in the `DimData1` table by the column `PK1`. | Optional | default: {} |
| metadata | **in columns** | `Dict with List of string values`. Each table key will include a list of strings with columns required. Default key "_" is to be used to define required columns for single table input metadata. May not include all existing columns, mus be limited to the essential ones. Columns defined in the "key" and "association" data are automatically required and may not be included in the list. | Optional | default: {"_":[]} |
| metadata | **required tables** | `List of Strings`. List of tables that must be present in the metadata file. If not present, the file will be moved to trash. Default to "_" which will handle any data in the root json path and also CSV and XLSX input files. | Optional | default: ["_"] |
| metadata | **sort by** | `Dict with string values`. For each table, define the name of the column in tha should used for ordering. Default will sort by the order in which the data is posted | Optional | default: {"_":""} |
| metadata | **data filenames** | `Dict with lists of string values`. For each table, define a list of the columns that contain data filenames | Optional | default: {"_":[]} |
| metadata | **data published flag** | `Dict with lists of string values`. For each table, that store a boolean flag that indicates if data files are available at the _GET_ folder. This column will be added to the output, regardless of being present in the input files | Optional | default: "" |
| metadata | **add filename** | `Dict with string values`. Specify how the filename of the metadata file will be added to the output, regardless of being present as a datafield in input files. Defined in the form of a dictionary using the structure: `{"<table name>":"<column name>"}` containing the name of the column to be created to hold the filename within each table. If left empty, will not create any column. | Optional | default: {} |
| metadata | **filename format** | `Dict with string values`. Specify data that should be extracted from the filename. Use a dictionary to specify the table in which the data should be created and the format string used to parse information from the filename. Based in the re.match.groupdict method. See [re](https://docs.python.org/3/library/re.html#re.Match.groupdict) for more information. | Optional | default: {}. example: {"\_":"(?P\<name>\\\w+)\_(?P\<date>\\\d{4}\\\.\\\d{2}\\\.\\\d{2})\_T(?P\<time>\\\d{2}\\\.\\\d{2}\\\.\\\d{2})\_(?P\<Inspection>\\\d+)"} will create 4 columns with name, date, time and inspection data. |
| metadata | **filename data processing rules** | `Dict with Dict values`. Define rules for post processing of the data metadata retrieved from the filename as a dict using as root keys the same names defined in the "filename format" configuration. Post processing options include: "replace", "add prefix", "add suffix". Replace rule expects to receive a list of dictionaries with old and new characters to be replaced. Add suffix and prefix rules expect to receive a single string value to be added after of before the retrieved vale. See example for specific formatting. | Optional | default: {}. example: {"name": {"replace": [{"old": "_", "new": " "}]},"time": {"replace": [{"old": ".", "new": ":"}],"add suffix": "Z"},"Inspection": {"add prefix": "#"}} |
| | | | | |

<div>
    <a href="https://github.com/InovaFiscaliza/Scarab">
        <img align="left" width="50" height="50" src="./images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#about-scarab-documentation">
        <img align="right" width="40" height="40" src="./images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>