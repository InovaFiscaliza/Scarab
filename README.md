<details>
    <summary>Table of Contents</summary>
    <ol>
        <li><a href="#About-Scarab">About Scarab</a></li>
        <li><a href="#Scripts_and_Files">Scripts and Files</a></li>
        <li><a href="#Tests">Tests</a></li>
        <li><a href="#setup">Setup</a></li>
        <li><a href="#roadmap">Roadmap</a></li>
        <li><a href="#contributing">Contributing</a></li>
        <li><a href="#license">License</a></li>
    </ol>
</details>

<!-- ABOUT THE PROJECT -->
# About Scarab

<div>
<img align="left" width="100" height="100" src="./docs/images/scarab_glyph.svg"> This app is intended to run as a service and perform basic ESB (Enterprise Service Bus) tasks by moving file between input and output folders while performing basic file processing tasks including: file type checking, backup, metadata aggregation and logging.

Metadata files are expected to be tables in XLSX format, with the first row as the header.

Application is written in Python and uses the UV package for environment management and intended to run as a service.
</div>

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

Script is made to run as a windows tasks, looking for files at input folders (post folders) at regular intervals.

As they are detected, data files (that are not processed) are moved to the output folder and metadata files are moved to a temp folder.

Metadata files are expected to be tables (XLSX or CSV format), with the first row as the header or dictionaries in JSON format.

One or several columns might be used as key columns to update the metadata file with new data.

The script will concatenate the tables and update the rows based on the key columns, producing the final metadata file that is published along with the raw data files.

Any rows that do not have value within the assigned key columns are discarded and an error message is logged.

During updates, columns with `null` values are ignored. To entirely remove data, the service must be stopped and the consolidated metadata file manually edited.

Column order in the consolidated metadata file is the same as the last metadata file processed. Columns existing in previous metadata files but not in the new one are kept with minimal order changes, as close as possible to the original neighborhood, otherwise, they are appended to the end of the table.

A log is used to keep track of the script execution, being possible to have the log presented in the terminal and/or saved to a file.
Information in the metadata files are consolidated  and cleaning the input and temp folders regularly.

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

* [x] Initial deployment
  * [x] Create the project structure
  * [x] Create the configuration file
  * [x] Create the main script
  * [x] Create the configuration handler
  * [x] Create the file handler
  * [x] Create the log handler
  * [x] Create the metadata handler
  * [x] Expand functionality to handle multiple input and output folders
  * [x] Create tests and validate release candidate
  * [x] Release version 1.0.0
  
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
