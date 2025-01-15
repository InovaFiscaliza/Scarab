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

# About Simple File Cataloger

This script monitor at regular intervals an input folder (post), consolidating metadata from files in XLSX format and moving files to an output folder (get).

Incoming files in XLSX format containing metadata are posted by users using a sync application (onedrive).

Files in XLSX format contain metadata associated with PDF files, that are placed in the same folder or subfolders.

Data in XLSX format is consolidate into a single file.

Using one column as key, rows might be updated.

The consolidated metadata is published as a XLSX file at an output folder (get)

PDF files associated with rows in the consolidated XLSX are also moved to a subfolder branching from the output path.

Rows in the consolidated XLSX are marked to indicate if the associated PDF is present or not in the output publish folder.

While processing, files are moved to a temporary folder (temp) to avoid changes by users.

After processing, files are moved to a backup folder (store) to keep track of changes.

If file are found to be not compatible with the script, they are moved to a trash folder (trash).

PDF files that are not associated with any row in the consolidated XLSX are also moved to a trash folder (trash) after a period of time.

Script is made to run as a service continuously, looking for files at regular intervals and cleaning the input and temp folders regularly.

To stop, the script monitor the occurrence of kill signal from the system or ctrl+c if running in the terminal.

A log file is also generated to keep track of the script execution, being also possible to have the log presented in the terminal.

<p align="right">(<a href="#indexerd-md-top">back to top</a>)</p>

## Scripts and Files

| Script module | Description |
| --- | --- |
| [config.json](./src/config.json) | get the value used to represent no data in a geotiff |
| [file_catalog.py](./src/file_catalog.py) | merge overlapping tiles and delete empty tiles from a list of geotiff files. |
| [environment.yml](./src/environment.yml) | Conda environment to run the geoprocessing scripts. Core includes OSWGeo GDAL and Python |
| 


<p align="right">(<a href="#indexerd-md-top">back to top</a>)</p>

# Setup

Scripts were intended to be used in a Windows machine with conda installed.

To install Miniconda as described in the [conda website](https://docs.anaconda.com/free/miniconda/)

create the environment

```powershell
(base) conda env create -f environment.yml
```

Activate the environment

```powershell
conda activate regulatron-catalog
```

Create the expected folder structure. You may use the test example in the [test](./test) folder.

Configure the script by editing the [config.json](./src/config.json) file.

Call the desired script, for example

```powershell
(regulatron-catalog).\python file_catalog.py
```

# Roadmap

This section presents a simplified view of the roadmap and knwon issues.

For more details, see the [open issues](https://github.com/FSLobao/RF.Fusion/issues)

* [ ] Configure service and update documentation
  
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

* [Conda Cheat Sheet](https://docs.conda.io/projects/conda/en/4.6.0/_downloads/52a95608c49671267e40c689e0bc00ca/conda-cheatsheet.pdf)
* [Readme Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#indexerd-md-top">back to top</a>)</p>
