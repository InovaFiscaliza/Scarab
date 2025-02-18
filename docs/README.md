
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
| `name` | | String. Configuration name to be used in log messages | "Sandbox Complete Text Example" |
| `check period in seconds` | | Integer. Time in seconds between checks of post and temp folders | 10 |
| `clean period in hours` | | Integer. Time in hours between cleaning post and temp folders to remove to trash files with the correct extension but not processed, due to missing metadata | 1 |
| `last clean` | | String. Date and time of the last clean operation. Is updated whenever the clean methods is executed. Should not be manually edited | "2024-11-05 20:33:29" |
| `overwrite data in store` | | Boolean. if `True`, new files with the same name will overwrite files in store folder, if `False`, previously existing files will be moved to trash. | true |
| `overwrite data in get` | | Boolean. if `True`, new files with the same name will overwrite files in get folder, if `False`, previously existing files will be moved to trash. | false |
| `overwrite data in trash` | | Boolean. if `True`, new files with the same name will overwrite files in trash folder, if `False`, previously existing files will be moved to trash. | true |
| `discard invalid data files` | | Boolean. if `True`, files with the unrecognized extension or content will me moved to trash as soon as detected, if `False` files will be moved to trash only during clean operations. | false |
| `log` | | Root key to log configuration keys | |
| `log` | `level` | String. Log level to be used. Possible values are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | "INFO" |
| `log` | `screen output` | Boolean. If `True`, log messages will be printed to the screen | true |
| `log` | `file output` | Boolean. If `True`, log messages will be written to a file | false |
| `log` | `file path` | List of Strings. Path to the log file | ["./sandbox/get/log.txt", "./sandbox/get_other/log.txt"] |
| `log` | `format` | List of Strings. Format of the log message as defined in [logging](https://docs.python.org/3/howto/logging.html#formatters)  | ["%(asctime)s", "%(module)s: %(funcName)s:%(lineno)d", "%(name)s[%(process)d]", "%(levelname)s", "%(message)s"] |
| `log` | `colour sequence` | List of Strings. Colour sequence to be used in the log message [advanced logging](https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output) | ["32m", "35m", "34m", "30m", "0m"] |



```json
{
    "name": "Sandbox Complete Text Example",
    "check period in seconds": 10,
    "clean period in hours": 1,
    "last clean": "2024-11-05 20:33:29",
    "overwrite data in store": true,
    "overwrite data in get": true,
    "overwrite data in trash": true,
    "discard invalid data files": true,
    "log": {
        "level": "INFO",
        "screen output": true,
        "file output": true,
        "file path": "./sandbox/get/log.txt",
        "format": [
            "%(asctime)s",
            "%(module)s: %(funcName)s:%(lineno)d",
            "%(name)s[%(process)d]",
            "%(levelname)s",
            "%(message)s"
        ],
        "colour sequence": [
            "32m",
            "35m",
            "34m",
            "30m",
            "0m"
        ],
        "separator": " | ",
        "overwrite log in trash": false
    },
    "folders": {
        "post": ["./sandbox/post","./sandbox/post_other"],
        "temp": "./sandbox/temp",
        "trash": "./sandbox/trash",
        "store": "./sandbox/store",
        "get" : ["./sandbox/get/raw","./sandbox/get_other/raw"]
    },
    "files" : {
        "metadata extension": ".xlsx",
        "data extension": ".txt",
        "catalog names": ["./sandbox/get/monitorRNI.xlsx","./sandbox/get_other/monitorRNI.xlsx"]
    },
    "metadata": {
        "in columns": [ "ID",
                "UD",
                "UF",
                "Município",
                "Tipo",
                "Serviço",
                "NEW1",
                "Fistel",
                "N° estacao",
                "Lat",
                "Long",
                "Áreas Críticas",
                "Qtd. medidas",
                "Qtd. medidas > 14.0 V/m",
                "Distância mínima (km)",
                "Emin (V/m)",
                "Emean (V/m)",
                "Emax (V/m)",
                "Emax - Data da Medição",
                "Emax - Latitude",
                "Emax - Longitude",
                "Fonte de dados",
                "Justificativa",
                "Observações"
        ],
        "key": ["Fistel","N° estacao","Emax - Data da Medição","Emax - Latitude","Emax - Longitude"],
        "data filenames": ["Fonte de dados","Justificativa"],
        "data published flag": "Fontes Disponíveis"
    }
}

```

<div>
    <a href="../README.md">
        <img align="left" width="50" height="50" src="./images/scarab_glyph.svg" style="transform: rotate(-90deg);" title="Go back to Scarab main repo page">
    </a>
    <a href="#indexerd-md-top">
        <img align="right" width="40" height="40" src="./images/up-arrow.svg" title="Back to the top of this page">
    </a>
    <br><br>
</div>