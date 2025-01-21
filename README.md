<details>
    <summary>Table of Contents</summary>
    <ol>
        <li><a href="#About-File-Sorter">About File Sorter</a></li>
        <li><a href="#Scripts_and_Files">Algorithm Overview</a></li>
        <li><a href="#setup">Setup</a></li>
        <li><a href="#roadmap">Roadmap</a></li>
        <li><a href="#contributing">Contributing</a></li>
        <li><a href="#license">License</a></li>
    </ol>
</details>

# About Scarab

<img align="left" width="100" height="100" src="./docs/images/scarab_glyph.svg"> This app is intended to run as a service and perform basic ESB (Enterprise Service Bus) tasks by moving file between input and output folders while performing basic file processing tasks including: file type checking, backup, metadata aggregation (concatenate tables and row updata based on key columns) and logging.

Application is written in Python and uses the UV package for environment management and intended to run as a service.

<p align="right">(<a href="#indexerd-md-top">back to top</a>)</p>

## Scripts and Files

| Script module | Description |
| --- | --- |
| [config.json](./src/config.json) | define application parameters |
| [scarab.py](./src/scarab.py) | main script to run the service |
| [config_handler.py](./src/config_handler.py) | module responsible for handling the configuration file |
| [file_handler.py](./src/file_handler.py) | module responsible for handling the file operations |
| [log_handler.py](./src/log_handler.py) | module responsible for handling the log operations |
| [metadata_handler.py](./src/metadata_handler.py) | module responsible for handling the metadata operations |


Script is made to run as a service continuously, looking for files at input folders (post folders) at regular intervals.

The configuration file in json format must be specified in the service call to define application parameters, such as folder paths, folder revisit timing, log method, log level, and log file name, among others.

As they are detected, raw data files (that are not processed) are moved to the output folder and metadata files are moved to a temp folder.

Metadata files are expected to be tables in XLSX format, with the first row as the header.

One or several columns might be used as key columns to update the metadata file with new data.

The script will concatenate the tables and update the rows based on the key columns, producing the final metadata file that is published along with the raw data files.

A log is used to keep track of the script execution, being possible to have the log presented in the terminal and/or saved to a file.
Information in the metadata files are consolidated  and cleaning the input and temp folders regularly.

To stop, the script monitor the occurrence of kill signal from the system or ctrl+c if running in the terminal.

<p align="right">(<a href="#indexerd-md-top">back to top</a>)</p>

# Setup

Scripts were intended to be used in a Windows machine with UV package and environment management.

For more details, see the [UV documentation](https://docs.astral.sh/uv/)

# Roadmap

This section presents a simplified view of the roadmap and knwon issues.

For more details, see the [open issues](https://github.com/FSLobao/RF.Fusion/issues)

* [ ] Initial deployment
  * [x] Create the project structure
  * [x] Create the configuration file
  * [x] Create the main script
  * [x] Create the configuration handler
  * [x] Create the file handler
  * [x] Create the log handler
  * [x] Create the metadata handler
  * [ ] Create tests and validate release candidate
  
<p align="right">(<a href="#indexerd-md-top">back to top</a>)</p>

<!-- CONTRIBUTING -->
# Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

<p align="right">(<a href="#indexerd-md-top">back to top</a>)</p>

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

<p align="right">(<a href="#indexerd-md-top">back to top</a>)</p>

<!-- ACKNOWLEDGMENTS -->
## References

* [UV Short Guide](https://www.saaspegasus.com/guides/uv-deep-dive/)
* [Readme Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#indexerd-md-top">back to top</a>)</p>
