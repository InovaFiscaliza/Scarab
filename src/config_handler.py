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
                "name": "Teste Simple",
                "check period in seconds": 10,
                "clean period in hours": 1,
                "last clean": "2024-11-05 20:33:29",
                "overwrite data in trash": true,
                "log": {
                    "level": "INFO",
                    "screen output": true,
                    "file output": true,
                    "file path": "./tests/sandbox/get/log.txt",
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
                    "post": "./tests/sandbox/post",
                    "temp": "./tests/sandbox/temp",
                    "trash": "./tests/sandbox/trash",
                    "store": "./tests/sandbox/store",
                    "get" : "./tests/sandbox/get/raw"
                },
                "files" : {
                    "metadata extension": ".xlsx",
                    "data extension": ".txt",
                    "catalog names": "./tests/sandbox/get/monitorRNI.xlsx"
                },
                "metadata": {
                    "in columns": [ "ID", "UD", "UF", "Município", "Tipo", "Serviço", "Entidade", "Fistel", "N° estacao", "Endereco", "Lat", "Long", "Áreas Críticas", "Qtd. medidas", "Qtd. medidas > 14.0 V/m", "Distância mínima (km)", "Emin (V/m)", "Emean (V/m)", "Emax (V/m)", "Emax - Data da Medição", "Emax - Latitude", "Emax - Longitude", "Fonte de dados", "Justificativa", "Observações"],
                    "key": "N° estacao",
                    "data filenames": "Fonte de dados",
                    "data published flag": "Fontes Disponíveis"
                }
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
            self.store_data_overwrite: bool = self.raw["overwrite data in store"]
            """ Flag to indicate if data should be overwritten in store folder"""
            self.get_data_overwrite: bool = self.raw["overwrite data in get"]
            """ Flag to indicate if data should be overwritten in get folders"""
            self.trash_data_overwrite: bool = self.raw["overwrite data in trash"]
            """ Flag to indicate if data should be overwritten in trash folder"""
            self.discard_invalid_data_files: bool = self.raw["discard invalid data files"]
            """ Flag to indicate if invalid data files should be discarded"""
            self.log_level: str = self.raw["log"]["level"]
            """ Logging level"""
            self.log_to_screen: bool = self.raw["log"]["screen output"]
            """ Flag to log to screen"""
            self.log_to_file: bool = self.raw["log"]["file output"]
            """ Flag to log to file"""
            self.log_file_path: str = self.__ensure_list(self.raw["log"]["file path"])
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
            self.post: List[str] = self.__ensure_list(self.raw["folders"]["post"])
            """ Folder path where users post files"""
            self.temp: str = self.raw["folders"]["temp"]
            """ Temp folder used form metadata processing"""
            self.trash: str = self.raw["folders"]["trash"]
            """ Trash folder path used for files posted using wrong format"""
            self.store: str = self.raw["folders"]["store"]
            """ Store folder path used to store processed files"""
            self.catalog_files: List[str] = self.__ensure_list(self.raw["files"]["catalog names"])
            """ Full path to the catalog file, where metadata is stored"""
            self.metadata_extension: str = self.raw["files"]["metadata extension"]
            """ Extension used to identify the metadata files"""
            self.get: List[str] = self.__ensure_list(self.raw["folders"]["get"])
            """ Folder path where data files are to be stored"""
            self.data_extension: str = self.raw["files"]["data extension"]
            """ Data file extension, used to identify the raw data files"""
            self.columns_in: Set[str] = set(self.raw["metadata"]["in columns"])
            """ Columns required in the input metadata file"""
            self.columns_key: List[str] = self.__ensure_list(self.raw["metadata"]["key"])
            """ Columns that define the uniqueness of each row in the metadata file"""
            self.columns_data_filenames: List[str] = self.__ensure_list(self.raw["metadata"]["data filenames"])
            """ Columns that contain the names of data files associated with each row metadata"""
            self.columns_data_published: str = self.raw["metadata"]["data published flag"]
            """ Columns that contain the publication status of each row"""
            # TODO: #2 Parse file metadata separated from the data metadata since data may be aggregated from multiple files

        except Exception as e:
            print(f"Configuration files missing arguments: {e}")
            exit(1)
                
        if not self.is_config_ok():
            exit(1)

    # --------------------------------------------------------------
    def __ensure_list(self, item: Any) -> List[str]:
        """Create a list from a string or a list, adding a root path if it exists.
        
        Args:
            item (Any): Input string or list.
            
        Returns:
            List[str]: List of strings.
        
        Raises: None
        """
        
        if isinstance(item, str):
            return [item]
        else:
            return item
            
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
        except Exception as e:
            print(f"Error reading config file: {e}")
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
    def __test_folder(self, folder: str, folder_type: str, message: str) -> tuple[bool, str]:
        """Test if the folder exists and add an error message if it does not.

        Args:
            folder (str): folder path to be tested.
            folder_type (str): folder type to be mentioned in the error message.
            msg (str): error message to be updated.

        Returns:
            msg: error message with the folder test result.
        """
        test_result = True
        if not os.path.exists(folder):
            message += f"\n  - {folder_type} folder not found: {folder}"
            test_result = False
        
        return test_result, message
    
    # --------------------------------------------------------------
    def __test_file(self, filename: str, file_type: str, message: str, required:bool=False) -> tuple[bool, str]:
        """Test if the file exists and add an error message if it does not.

        Args:
            file (str): file path to be tested.
            file_type (str): file type to be mentioned in the error message.
            msg (str): error message to be updated.
            required (bool): flag to indicate if the file is required.

        Returns:
            msg: error message with the file test result.
        """
        
        try:
            test_result = True
            
            with open(filename, 'a') as file:
                # use tell() to check if the file at the beginning, thus, has been just created by the file open function call
                file_is_empty = (file.tell() == 0)
                if not file.writable():
                    raise Exception(f"{filename} not writable")
        
            if file_is_empty:
                if required:
                    message += f"\n  - {file_type} file is empty: {filename}"
                    test_result = False
                    
                os.remove(filename)
                
        except (FileNotFoundError, OSError) as e:
            message += f"\n  - {file_type} file [{filename}] not available {e}"
            test_result = False

        except Exception as e:
            message += f"\n  - {file_type} error. {e}"
            test_result = False
    
        return test_result, message
    
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
                
        for folder in self.post:
            test_result, msg = self.__test_folder(folder, "Post", msg)
        
        test_result, msg = self.__test_folder(self.store, "Store", msg)
        
        test_result, msg = self.__test_folder(self.temp, "Temp", msg)
        
        test_result, msg = self.__test_folder(self.trash, "Trash", msg)
        
        for folder in self.get:
            test_result, msg = self.__test_folder(folder=folder,
                                                folder_type="Get",
                                                message=msg)

        for file in self.catalog_files:
            test_result, msg = self.__test_file(filename=file,
                                                file_type="Catalog",
                                                message=msg)
        
        for file in self.log_file_path:
            test_result, msg = self.__test_file(filename=file,
                                                file_type="Log",
                                                message=msg)
            
        test_result, msg = self.__test_file(filename=self.config_file,
                                            file_type="Config",
                                            message=msg,
                                            required=True)
                
        if not test_result:
            msg += "\n\nPlease correct the errors and restart the script."
            print(msg)
        
        return test_result

