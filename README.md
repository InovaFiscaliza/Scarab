[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/InovaFiscaliza/Scarab)

<details>
    <summary>Table of Contents</summary>
    <ol>
        <li><a href="#about-scarab">About Scarab</a></li>
        <li><a href="#scripts-and-files">Scripts and Files</a></li>
        <li><a href="#how-it-works">How it works</a></li>
        <li><a href="#tests">Tests</a></li>
        <li><a href="#setup">Setup</a></li>
        <li><a href="#roadmap">Roadmap</a></li>
        <li><a href="#contributing">Contributing</a></li>
        <li><a href="#license">License</a></li>
    </ol>
</details>

<!-- ABOUT THE PROJECT -->
# About Scarab

<div>
<img align="left" width="100" height="100" src="./docs/images/scarab_glyph.svg"> </div>

This app is intended to run as a service and perform ESB (Enterprise Service Bus) tasks by moving file between input and output folders while performing basic file processing tasks including: file type checking, backup, metadata aggregation and logging.

Metadata files are expected to be tables in XLSX or CSV format, with the first row as the column headers, or JSON arrays and dictionaries.

XLSX and JSON files may contain multiple tables defined in sheets or dictionaries entries in the first level, respectively. Association between the tables is defined by "Primary Key" and "Foreign Key" columns, and may be defined with absolute (UI) or relative values (specific to each file).

Metadata may also be extracted from the filenames using regex patterns and the filename itself may be stored in the metadata file.

Application is written in Python and uses the UV package for environment management and intended to run as a service. Exemples of service configuration files for the Windows Task Manager are provided in the [data/examples](./data/examples/) folder.

<div>
    <a href="#about-scarab">
        <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>


<!-- SCRIPTS AND FILES -->
# Scripts and Files

| Script module | Description |
| --- | --- |
| [scarab.py](./src/scarab.py) | main script to run the service |
| [config_handler.py](./src/config_handler.py) | module responsible for handling the configuration file parsing, validation and processing into the used configuration object |
| [default_config.json](./src/default_config.json) | default configuration file, used by the script to fill optional values in user configuration files. May be edited to change the default values. |
| [log_handler.py](./src/log_handler.py) | module responsible for handling configuration of the standard python logging module from the configured parameters, such as enabling the selected output channels and message formatting |
| [file_handler.py](./src/file_handler.py) | module responsible for handling the file operations such as copy, move and delete |
| [metadata_handler.py](./src/metadata_handler.py) | module responsible for handling the metadata operations, including reading, merging and storing |
| | | 

Apart from scripts, the application uses a configuration file to define the application parameters, such as folder paths, folder revisit timing, log method, log level, and log file name, among others.

Please check Scarab [documentation](./docs/README.md) for more details on the configuration file.

Examples of configuration files can be found in the defined [tests](./tests/README.md).

<div>
    <a href="#about-scarab">
        <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

<!-- How it works -->
# How it works

Script is made to run as a windows service reading for the task definition in a configuration file that uses JSON format.

The script can monitor multiple folders. As soon as any content is changed, the script sort the content into 3 groups, corresponding to data files to be moved, metadata files to be processed and other files or folders that may be deleted or ignored.

Identification of the files is based on their names using a regex pattern defined in the configuration file. Metadata files are further evaluated by their content, which is expected to contain a minimum set of data columns, otherwise the file will be considered invalid and treated as an unknown file.

Metadata files are expected to be tables (XLSX or CSV format), with the first row as the header, arrays and dictionaries in JSON format.

One or several columns might be used as key columns to uniquely identify each row.

The script will concatenate tables and update the rows based on the key columns. During updates, columns with `null` values are ignored. To entirely remove data, the service must be stopped and the consolidated metadata file manually edited.

Column order in the consolidated metadata file is the same as the last metadata file processed. Columns existing in previous metadata files but not in the new one are kept with minimal order changes, as close as possible to the original neighborhood, otherwise, they are appended to the end of the table.

Additional columns may be added to the consolidated metadata file, including the filename itself and parsed information from the filename using regex groupby.

Rows may be ordered by any indicated column, by default they will be sorted following the order by which they were created when processing the input files.

For XLSX files with multiple sheets, JSPN files with multiple dictionaries in the root, or CSV files with significantly different column set or respecting different regex rules, the script can create a multi table consolidated result, including relational association between tables using Primary Key (PK) and Foreign Key (FK) relationships. Such relationships may be relative, within a single file, or absolute, across multiple files.

The consolidated metadata file is stored in multiple output folder. 

Data files may be of any type and may be moved to multiple output folders. Different output folders may be set for different file regex.

References to the data files within the consolidated metadata file may be used to add additional metadata information, indicating that the data file was moved to the output folder.

Data files without the corresponding metadata may be hold in temp folders and eventually moved to trash.

Input folder cleaning policies may be defined in the configuration file, including moving files to a trash folder or deleting them, thus handling unidentified files.

Exception to the cleaning policies may be defined to allow the use of specific input folder structure or permanence of files that may not be processed.

A log is used to keep track of the script execution, being possible to have the log presented in the terminal and/or saved to a file.

To stop, the script monitor the occurrence of kill signal from the system or ctrl+c if running in the terminal.

<div>
    <a href="#about-scarab">
        <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

<!-- TESTS -->
# Tests

Testes are proposed for different scenarios to validate the scripts and modules.

Please check the [tests folder](./tests/README.md) for more details.


<div>
    <a href="#about-scarab">
        <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

<!-- SETUP -->
# Setup

Scripts were intended to be used in a Windows machine with UV package and environment management.

You may simply clone the repository and run the script with the following command or follow the [install procedures](./install/README.md)

For more details about UV, please check the [UV documentation](https://docs.astral.sh/uv/)

Please check Scarab [documentation](./docs/README.md) for more details on the configuration file.

Additional examples can be found in the [data folder](./data/examples/) of the repository.

These examples include.

- `.json` configuration files for the application in some scenarios currently in use.
- `.xml` files for the Windows task manager to run the application as a service.
- `zip` file with a companion script to be used with [PowerAutomate](https://en.wikipedia.org/wiki/Microsoft_Power_Automate) to extract data from [MS Sharepoint](https://en.wikipedia.org/wiki/SharePoint) repositories and post them to the input folders.

<div>
    <a href="#about-scarab">
        <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>


<!-- ROADMAP -->
# Roadmap

This section presents a simplified view of the roadmap and knwon issues.

For more details, see the [open issues](https://github.com/FSLobao/RF.Fusion/issues)

* [x] Version 1.0.0: Completed in 21/02/2025
  * [x] version 1.0.1: Completed in 31/03/2025, bug fix
  * [x] version 1.1.0: Completed in 14/04/2025, bug fix and scarab companion
* [ ] Version 2.0.0
  * [x] Define new configuration format for multi table input 
  * [x] Code new features
  * [ ] Test, debug and release
  
<div>
    <a href="#about-scarab">
        <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

<!-- CONTRIBUTING -->
# Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

<div>
    <a href="#about-scarab">
        <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

<!-- LICENSE -->
# License

Distributed under the GNU General Public License (GPL), version 3. See [`LICENSE.txt`](../../LICENSE).

For additional information, please check <https://www.gnu.org/licenses/quick-guide-gplv3.html>

This license model was selected with the idea of enabling collaboration of anyone interested in projects listed within this group.

It is in line with the Brazilian Public Software directives, as published at: <https://softwarepublico.gov.br/social/articles/0004/5936/Manual_do_Ofertante_Temporario_04.10.2016.pdf>

Further reading material can be found at:

* <http://copyfree.org/policy/copyleft>
* <https://opensource.stackexchange.com/questions/9805/can-i-license-my-project-with-an-open-source-license-but-disallow-commercial-use>
* <https://opensource.stackexchange.com/questions/21/whats-the-difference-between-permissive-and-copyleft-licenses/42#42>

<div>
    <a href="#about-scarab">
        <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>

<!-- REFERENCES -->
## References

* [UV Short Guide](https://www.saaspegasus.com/guides/uv-deep-dive/)
* [Readme Template](https://github.com/othneildrew/Best-README-Template)

<div>
    <a href="#about-scarab">
        <img align="right" width="40" height="40" src="./docs/images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>
