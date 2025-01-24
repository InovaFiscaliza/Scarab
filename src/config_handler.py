#!/usr/bin/python
"""
Module class that handle the configuration file for the script.

Args (stdin): ctrl+c will soft stop the process similar to kill command or systemd stop <service>. kill -9 will hard stop.

Returns (stdout): As log messages, if target_screen in log is set to True.

Raises:
    Exception: If any error occurs, the exception is raised with a message describing the error.
"""

# --------------------------------------------------------------
import json
import os
import pandas as pd
from typing import Any, Dict, List, Set

# --------------------------------------------------------------
class Config:
    """Class to load and store the configuration values from a JSON file."""

    def __init__(self, filename: str) -> None:
        """Load the configuration values from a JSON file encoded with UTF-8.
        
        Args:
            filename (str): Configuration file name.
            
        Returns: None
            
        Raises:
            FileNotFoundError: If the configuration file is not found.
            Exception: If the configuration file is missing parameters.
            
        Example of a configuration file
            {
                "name": "Regulatron",
                "check period in seconds": 30,
                "clean period in hours": 24,
                "last clean": "2024-11-05 20:33:29",
                "overwrite data in trash": true,
                "log": {
                    "level": "INFO",
                    "screen output": true,
                    "file output": true,
                    "file path": "C:/Users/sfi.office365.pd/ANATEL/InovaFiscaliza - DataHub - GET/Regulatron/Logs;log.txt",
                    "format": ["%(asctime)s", "%(module)s: %(funcName)s:%(lineno)d", "%(name)s[%(process)d]", "%(levelname)s", "%(message)s"],
                    "colour sequence": ["32m", "35m", "34m", "30m", "0m"],
                    "separator": " | ",
                    "overwrite log in trash": false
                },
                "folders": {
                    "root": "C:/Users/sfi.office365.pd/ANATEL",
                    "post": "InovaFiscaliza - DataHub - TEMP/Regulatron",
                    "temp": "InovaFiscaliza - DataHub - TEMP/Regulatron",
                    "trash": "InovaFiscaliza - DataHub - TRASH/Regulatron",
                    "store": "InovaFiscaliza - DataHub - STORE/Regulatron",
                    "get" : "InovaFiscaliza - DataHub - GET/Regulatron",
                    "raw": "InovaFiscaliza - DataHub - GET/Regulatron/Screenshots",
                },
                "files" : {
                    "catalogExtension": ".xlsx",
                    "catalogName": "Anuncios",
                    "rawExtension": ".pdf",
                },    
                "columns":{
                    "in":["nome", "preço", "avaliações", "nota", "imagem", "url", "data", "palavra_busca", "página_de_busca", "certificado", "características", "descrição", "ean_gtin", "estado", "estoque", "imagens", "fabricante", "modelo", "product_id", "vendas", "vendedor", "screenshot", "indice", "subcategoria", "nome_sch", "fabricante_sch", "modelo_sch", "tipo_sch", "nome_score", "modelo_score", "passível?", "probabilidade", "marketplace"],
                    "key":"screenshot"}
            }
        """
        self.config_file = filename
        self.raw: Dict[str, Any] = {}
        
        self.__load_config()      
        
        try:
            self.name: str = self.raw["name"]
            """ Name of the configuration, used for logging"""
            self.check_period: int = self.raw["check period in seconds"]
            """ Period to check input folders in seconds """
            self.clean_period: int = self.raw["clean period in hours"]
            """ Period to clean temp folders in hours"""
            self.last_clean: pd.Timestamp = pd.to_datetime(self.raw["last clean"], format="%Y-%m-%d %H:%M:%S")
            """ Timestamp of the last clean operation"""
            self.data_overwrite: bool = self.raw["overwrite data in trash"]
            """ Flag to indicate if data should be overwritten in trash"""
            self.log_level: str = self.raw["log"]["level"]
            """ Logging level"""
            self.log_to_screen: bool = self.raw["log"]["screen output"]
            """ Flag to log to screen"""
            self.log_to_file: bool = self.raw["log"]["file output"]
            """ Flag to log to file"""
            self.log_path: str = self.raw["log"]["file path"]
            """ Log file name with path"""
            self.log_separator: str = self.raw["log"]["separator"]
            """ Log column separator"""
            self.log_file_format: str = self.__log_format_plain()
            """ Data columns to be presented in the log file using logging syntax"""
            self.log_screen_format: str = self.__log_format_colour()
            """ Data columns to be presented in the terminal using logging syntax, with colours"""
            self.log_title: str = self.__log_titles()
            """ Log header line based on the log format"""
            self.log_overwrite: bool = self.raw["log"]["overwrite log in trash"]
            """ Flag to overwrite log in trash"""
            self.post: str = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["post"])
            """ Folder path where users post files"""
            self.temp: str = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["temp"])
            """ Temp folder used form metadata processing"""
            self.trash: str = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["trash"])
            """ Trash folder path used for files posted using wrong format"""
            self.store: str = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["store"])
            """ Store folder path used to store processed files"""
            self.catalog_file: str = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["get"], self.raw["files"]["catalogName"] + self.raw["files"]["catalogExtension"])
            """ Full path to the catalog file, where metadata is stored"""
            self.catalog_extension: str = self.raw["files"]["catalogExtension"]
            """ Extension used to identify the metadata files"""
            self.raw_path: str = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["raw"])
            """ Folder path where raw files are to be stored"""
            self.raw_extension: str = self.raw["files"]["rawExtension"]
            """ Raw file extension"""
            self.columns_in: Set[str] = set(self.raw["columns"]["in"])
            """ Columns required in the input metadata file"""
            self.columns_key: List[str] = self.raw["columns"]["key"]
            """ Key columns"""

        except Exception as e:
            print(f"Configuration files missing arguments: {e}")
            exit(1)
                
        if not self.is_config_ok():
            exit(1)

    # --------------------------------------------------------------
    def __load_config(self) -> None:
        """Load the configuration values from a JSON file encoded with UTF-8.
        
        Args: None
        
        Returns: None
        
        Raises:
            FileNotFoundError: If the configuration file is not found.
        """
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as json_file:
                self.raw = json.load(json_file)
        except FileNotFoundError:
            print(f"Config file not found in path: {self.config_file}")
            exit(1)
    
    # --------------------------------------------------------------
    def __log_format_colour(self) -> str:
        """Return the log format string.

        Args: None
            
        Returns:
            str: Log format string.
            
        Raises: None
        """
        
        output_format = ""
        colour_format = self.raw["log"]["colour sequence"]
        colour_count = 0
        colour_set = '\x1b['
        separator = f"{colour_set}0m{self.log_separator}"
        for item in self.raw["log"]["format"]:
            output_format = f"{output_format}{colour_set}{colour_format[colour_count]}{item}{separator}"
            colour_count += 1
            if colour_count == len(colour_format):
                colour_count = 0
                        
        return output_format[:-len(self.raw['log']['separator'])]

    # --------------------------------------------------------------
    def __log_format_plain(self) -> str:
        """Return the log format string.

        Args: None
            
        Returns:
            str: Log format string.
        
        Raises: None
        """
        
        output_format = ""
        for item in self.raw["log"]["format"]:
            output_format = f"{output_format}{item}{self.log_separator}"
        
        return output_format[:-len(self.log_separator)]

    # --------------------------------------------------------------
    def __log_titles(self) -> str:
        """Return the log column titles as a string.
        
        Args: None
            
        Returns:
            str: Log titles stringÇ
                "%(asctime)s" result title = "asctime"
                "%(module)s: %(funcName)s:%(lineno)d" result title = "module: funcName:lineno"
                "%(name)s[%(process)d]" result title = "name [process]"
                "%(levelname)s" result title = "levelname"
                "%(message)s" result title = "message"

        Raises: None
        """
        
        non_title = ["%(", ")s", ")d"]
        output_format = ""
        for item in self.raw["log"]["format"]:

            for non in non_title:
                item = item.replace(non, "")
            
            output_format = f"{output_format}{item}{self.raw['log']['separator']}"
        
        return output_format[:-len(self.raw['log']['separator'])]
    # --------------------------------------------------------------
    def set_last_clean(self) -> None:
        """Write current datetime to JSON file.
        
        Args: None
            
        Returns: None

        Raises:
            Exception: Config file write error.
        """
        
        self.raw["last clean"] = pd.to_datetime("now").strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as json_file:
                json.dump(self.raw, json_file, indent=4)
        except Exception as e:
            print(f"Error writing to config file: {e}")
            
    
    # --------------------------------------------------------------
    def is_config_ok(self) -> bool:
        """Test if the configuration folders and files exist. Test if log folder is writable. Test if config file is writable.

        Args: None
            
        Returns:
            bool: True if all folders and files exist and are writable.
        
        Raises: None
        """
        test_result = True
        
        msg = f"\nError in {self.config_file}:"
        
        if not os.path.exists(self.post):
            msg += f"\n  - Post folder not found: {self.post}"
            test_result = False
        
        if not os.path.exists(self.store):
            msg += f"\n  - Store folder not found: {self.store}"
            test_result = False
        
        if not os.path.exists(self.temp):
            msg += f"\n  - Temp folder not found: {self.temp}"
            test_result = False
        
        if not os.path.exists(self.trash):
            msg += f"\n  - Trash folder not found: {self.trash}"
            test_result = False
        
        if not os.path.exists(self.raw_path):
            msg += f"\n  - Raw folder not found: {self.raw_path}"
            test_result = False
        
        if not os.path.exists(self.catalog_file):
            msg += f"\n  - Catalog file not found: {self.catalog_file}"
            test_result = False
        
        if self.log_path:
            if not os.path.exists(os.path.dirname(self.log_path)):
                msg += f"\n  - Log folder not found: {os.path.dirname(self.log_path)}"
                test_result = False
            else:
                try:
                    with open(self.log_path, 'a') as log_file:
                        log_file.writable()
                except Exception as e:
                    msg += f"\n  - Error writing to log file: {e}"
                    test_result = False
        
        try:
            with open(self.config_file, 'a') as json_file:
                json_file.writable()
        except Exception as e:
            msg += f"\n  - Error writing to config file: {e}"
            test_result = False
        
        if not test_result:
            msg += "\n\nPlease correct the errors and restart the script."
            print(msg)
        
        return test_result

