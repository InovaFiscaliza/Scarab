
<div>
    <a href="../README.md">
        <img align="left" width="50" height="50" src="./images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <br><br>
</div>
<details>
    <summary>Table of Contents</summary>
    <ol>
        <li><a href="#About_Scarab_Documentation">About Scarab Documentation</a></li>
    </ol>
</details>

# About Scarab Documentation

Scarab is configured through a json file

You may get examples in the test setups. Check the [tests folder](./tests/README.md) for more details.

| json key [root] | json key [branch] | Description | Example |
| --- | --- | --- | --- |
| **name** | | `String`. Configuration name to be used in log messages | "Sandbox Complete Text Example" |
| **check period in seconds** | | `Integer`. Time in seconds between checks of post and temp folders | 10 |
| **clean period in hours** | | `Integer`. Time in hours between cleaning post and temp folders to remove to trash files with the correct extension but not processed, due to missing metadata | 1 |
| **last clean** | | `String`. Date and time of the last clean operation. Is updated whenever the clean methods is executed using the format _"%Y-%m-%d_ _%H:%M:%S"_. Should not be manually edited, but can be left blank or even not included in the initial configuration file, condition in which the clean operation will be executed in the initial verifications and a new value will be set. | "2024-11-05 20:33:29" |
| **overwrite data in store** | | `Boolean`. if _True_, new files with the same name will overwrite files in store folder, if _False_, previously existing files will be moved to trash. | true |
| **overwrite data in get** | | `Boolean`. if _True_, new files with the same name will overwrite files in get folder, if _False_, previously existing files will be moved to trash. | false |
| **overwrite data in trash** | | `Boolean`. if _True_, new files with the same name will overwrite files in trash folder, if _False_, previously existing files will be moved to trash. | true |
| **discard invalid data files** | | `Boolean`. if _True_, files with the unrecognized extension or content will me moved to trash as soon as detected, if _False_ files will be moved to trash only during clean operations. | false |
| | | | |
| **log** | | Root key to log configuration keys | |
| log | **level** | `String`. Log level to be used. Possible values are _DEBUG_, _INFO_, _WARNING_, _ERROR_ or _CRITICAL_ | "INFO" |
| log | **screen output** | `Boolean`. If _True_, log messages will be printed to the screen | true |
| log | **file output** | `Boolean`. If _True_, log messages will be written to a file | false |
| log | **file path** | `List of Strings`. Path to the log file. More than one path may be supplied in order to simultaneously store log events into multiple files | ["./sandbox/get/log.txt", "./sandbox/get_other/log.txt"] |
| log | **format** | `List of Strings`. Format of the log message as defined in [logging](https://docs.python.org/3/howto/logging.html#formatters)  | ["%(asctime)s", "%(module)s: %(funcName)s:%(lineno)d", "%(name)s[%(process)d]", "%(levelname)s", "%(message)s"] |
| log | **colour sequence** | `List of Strings`. Colour sequence to be used in the log message. List should have the same size as the one used for format and colours will be assigned in the respective elements. See [advanced logging](https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output) for more information. | ["32m", "35m", "34m", "30m", "0m"] |
| log | **separator** | `String`. Separator to be used between log message elements. If required, spaces must be added to this string. | " \| " |
| log | **overwrite log in trash** | `Boolean`. If _True_, log files in trash will be overwritten, if _False_, new log files will be created with a timestamp suffix | false |
| | | | |
| **folders** | | Root key to folder configuration keys | |
| folders | **post** | `List of Strings`. Path to the post folders. More than one path may be supplied in order to simultaneously process files from multiple folders | ["./sandbox/post","./sandbox/post_other"] |
| folders | **temp** | `String`. Path to the temp folder | "./sandbox/temp" |
| folders | **trash** | `String`. Path to the trash folder | "./sandbox/trash" |
| folders | **store** | `String`. Path to the store folder | "./sandbox/store" |
| folders | **get** | `List of Strings`. Path to the get folders. More than one path may be supplied in order to simultaneously process files from multiple folders | ["./sandbox/get/raw","./sandbox/get_other/raw"] |
| | | | |
| **files** | | Root key to file configuration keys | |
| files | **metadata extension** | `String`. Extension used to find the metadata filenames in the POST and TEMP folders. Valid options are _.XLSX_, _.CSV_, _.JSON_ | ".xlsx" |
| files | **data extension** | `String`. Extension used to find the data filenames in the POST and TEMP folders. If used the same extension of the metadata files, the option _"discard_ _invalid_ _data_ _files"_ must be set to _False_. This will allow the processing of the data files after they fail to be recognized as metadata files. | ".bin" |
| files | **catalog names** | `List of Strings`. Path to the catalog files. More than one path may be supplied in order to simultaneously process files from multiple folders | ["./sandbox/get/metadata.xlsx","./sandbox/get_other/metadata.xlsx"] |
| | | | |
| **metadata** | | Root key to metadata configuration keys | |
| metadata | **in columns** | `List of Strings`. List of columns required for posted metadata file. Will be used to validate the new files. May not include all existing columns, but only the essential ones. Keys are automatically required and may not be included in the list. | ["SourceID", "TargetID", "SourceFile", "TargetFile", "User", "Service", "Timestamp", "Measurement", "Latitude", "Longitude", "Tags"] |
| metadata | **key** | `List of Strings`. List of columns to be used as key in the metadata file. This is used for merging data. Each row will have a single combination of the key columns. If new data is posted with the same key column combination, the data will be updated | ["SourceID", "TargetID"] |
| metadata | **data filenames** | `List of Strings`. List of columns with filenames of data files associated with the metadata in the row | ["SourceFile", "TargetFile"] |
| metadata | **data published flag** | `String`. Column that store a boolean flag that indicates if data files are available at the _GET_ folder. This column will be added to the output, regardless of being present in the input files | "DataFileAvailable" |
| | | | |

<div>
    <a href="../README.md">
        <img align="left" width="50" height="50" src="./images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#indexerd-md-top">
        <img align="right" width="40" height="40" src="./images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>