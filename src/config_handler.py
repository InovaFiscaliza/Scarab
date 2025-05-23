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
from typing import Any, Dict, TypedDict
import re

# --------------------------------------------------------------
# Control Constants
DEFAULT_CONFIG_FILENAME:str = "default_config.json"
"""Default configuration file name."""
FK_KEY:str = "FK"
"""Key to identify foreign key values in table association dictionaries."""
PK_KEY:str = "PK"
"""Key to identify primary key values in table association dictionaries."""
NAME_KEY:str = "name"
"""Key to identify table name values in table association dictionaries."""
REPLACE_KEY:str = "replace"
"""Key to identify replacement rules in filename data replacement dictionaries."""
OLD_KEY:str = "old"
"""key to identify character to be replaced (old) in filename data replacement dictionaries."""
NEW_KEY:str = "new"
"""Key to state character to be used in replacement (new) in filename data replacement dictionaries."""
ADD_SUFFIX_KEY:str = "add suffix"
"""Key to identify suffix to be added in filename data replacement dictionaries."""
ADD_PREFIX_KEY:str = "add prefix"
"""Key to identify prefix to be added in filename data replacement dictionaries."""

# --------------------------------------------------------------
# Define the structure of complex objects
class PKInfo(TypedDict):
    """Structure of the primary key in the table association."""
    name: str
    int_type: bool
    relative_value: bool

class TableAssociation(TypedDict):
    """Structure of the table association."""
    PK: PKInfo
    FK: Dict[str, str]  # Foreign key mapping: table name -> column name

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
        """
        
        # define default values        
        self.config_file = filename
        """Configuration file name."""
        config: Dict[str, Any] = self.__load_into_config(filename)
        
        self.raw: Dict[str, Any] = config
        """Raw configuration values."""
        
        # Get config file path from the script path
        source_path = os.path.dirname(os.path.abspath(__file__))
        default_config = os.path.join(source_path, DEFAULT_CONFIG_FILENAME)
        default_conf = self.__load_into_config(default_config)
        
        self.__load_into_config(filename)
        
        try:
            self.name: str = config.pop(["name"], default_conf["name"])
            """ Name of the config.pop(uration, used for logging"""
            self.scarab_version: str = config.pop(["scarab version"], default_conf["scarab version"])
            """ Version of the scarab script"""
            self.check_period: int = config.pop(["check period in seconds"], default_conf["check period in seconds"])
            """ Period to check input folders in seconds """
            self.clean_period: pd.Timedelta = pd.Timedelta(hours=config.pop(["clean period in hours"], default_conf["clean period in hours"]))
            """ Period to clean temp folders in hours"""
            self.last_clean: pd.Timestamp = pd.to_datetime(config.pop(["last clean"], default_conf["last clean"]), format="%Y-%m-%d %H:%M:%S")
            """ Timestamp of the last clean operation"""
            self.maximum_errors_before_exit: int = config.pop(["maximum errors before exit"], default_conf["maximum errors before exit"])
            """ Maximum number of errors before exiting with raised error"""
            self.maximum_file_variations: int = config.pop(["maximum file variations"], default_conf["maximum file variations"])
            """ Maximum number of file variations before exiting with raised error"""
            self.character_scope: str = config.pop(["character scope"], default_conf["character scope"])
            """ characters that will be retained from the column names. Characters not in the scope will be removed"""
            self.null_string_values: list[str] = self.__ensure_list(config.pop(["null string values"], default_conf["null string values"]))
            """ List of strings that will be considered as null values in the metadata file"""
            self.default_worksheet_key:str = config.pop(["default worksheet key"], default_conf["default worksheet key"])
            """Default key to be used for the worksheet that will retain single table values or non mapped values in the json root."""
            self.default_worksheet_name:str = config.pop(["default worksheet name"], default_conf["default worksheet name"])
            """Default value for the worksheet name. If value of assigned to the default key is equal to this value, will use the name of the config.pop(uration."""
            self.store_data_overwrite: bool = config.pop(["overwrite data in store"], default_conf["overwrite data in store"])
            """ Flag to indicate if data should be overwritten in store folder"""
            self.get_data_overwrite: bool = config.pop(["overwrite data in get"], default_conf["overwrite data in get"])
            """ Flag to indicate if data should be overwritten in get folders"""
            self.trash_data_overwrite: bool = config.pop(["overwrite data in trash"], default_conf["overwrite data in trash"])
            """ Flag to indicate if data should be overwritten in trash folder"""
            self.discard_invalid_data_files: bool = config.pop(["discard invalid data files"], default_conf["discard invalid data files"])
            """ Flag to indicate if invalid data files should be discarded"""

            log_separator: str = config.pop(["log"]["separator"], default_conf["log"]["separator"])
            """ Log column separator"""
            log_format: list[str] = config.pop(["log"]["format"], default_conf["log"]["format"])
            """ Data columns to be presented in the log file using logging syntax"""
            colour_sequence: list[str] = config.pop(["log"]["colour sequence"], default_conf["log"]["colour sequence"])
            """ Colour sequence to be used in the log file using logging syntax"""
            
            self.log_level: str = config.pop(["log"]["level"], default_conf["log"]["level"])
            """ Logging level"""
            self.log_to_screen: bool = config.pop(["log"]["screen output"], default_conf["log"]["screen output"])
            """ Flag to log to screen"""
            self.log_to_file: bool = config.pop(["log"]["file output"], default_conf["log"]["file output"])
            """ Flag to log to file"""
            self.log_file_path: str = self.__ensure_list(config.pop(["log"]["file path"], default_conf["log"]["file path"]))
            """ Log file name with path"""            
            self.log_file_format: str = self.__log_format_file(log_format, log_separator)
            """ Data columns to be presented in the log file using logging syntax"""
            self.log_screen_format: str = self.__log_format_colour(log_format, colour_sequence, log_separator)
            """ Data columns to be presented in the terminal using logging syntax, with colours"""
            self.log_title: str = self.__log_titles(log_format, log_separator)
            """ Log header line based on the log format"""
            self.log_overwrite: bool = config.pop(["log"]["overwrite log in trash"], default_conf["log"]["overwrite log in trash"])
            """ Flag to overwrite log in trash"""

            self.input_path_list: list[str] = [config.pop(["folders"]["temp"], default_conf["folders"]["temp"])] + self.__ensure_list(config.pop(["folders"]["post"], default_conf["folders"]["post"]))
            """ File input paths. Include all post folders and the temp folder as the first element"""
            self.temp: str = config.pop(["folders"]["temp"], default_conf["folders"]["temp"])
            """ Folder used for file storage while processing is taking place"""
            self.trash: str = config.pop(["folders"]["trash"], default_conf["folders"]["trash"])
            """ Trash folder path used for files posted using wrong format"""
            self.store: str = config.pop(["folders"]["store"], default_conf["folders"]["store"])
            """ Store folder path used to store processed files"""
            self.catalog_files: list[str] = self.__ensure_list(config.pop(["files"]["catalog names"], default_conf["files"]["catalog names"]))
            """ Full path to the catalog file, where metadata is stored"""
            self.metadata_file_regex: re.Pattern = re.compile(config.pop(["files"]["metadata file regex"], default_conf["files"]["metadata file regex"]))
            """ Regex pattern to be used to select files that may contain metadata."""
            self.catalog_extension: str = os.path.splitext(self.catalog_files[0])[1]
            """ Extension used to identify the catalog files"""
            self.input_to_ignore: list[str] = set(self.__ensure_list(config.pop(["files"]["input to ignore"], default_conf["files"]["input to ignore"])))
            """ Set with files and folders to ignore in the input folders. Files within ignored folders will not be ignored. Use exact names only, including relative path to the input folder."""

            self.get: Dict[str:list[str]] = config.pop(["folders"]["get"], default_conf["folders"]["get"])
            """ For each key associated with a matching pattern defined in the "data file regex", a list of target folders is defined, to which matching files should be moved."""
            self.data_file_regex: Dict[str, re.Pattern] = {
                k: re.compile(v) for k, v in config.pop(["files"]["data file regex"], default_conf["files"]["data file regex"]).items()
            }
            """ Dictionary with regex formatting to be used to select filenames to be processed as raw data files"""
            self.table_names: Dict[str,str] = self.__build_worksheet_dict(config.pop(["files"]["table_names"], default_conf["files"]["table_names"]))
            """ Table names to be used. {"json_root_table_name": "worksheet_name", ...]"""

            self.required_tables: list[str] = self.limit_character_scope(
                self.__ensure_list(
                    config.pop(["metadata"]["required tables"], default_conf["metadata"]["required tables"])))
            """ Columns that define the tables required in the metadata file"""
            self.key_columns: Dict[str,list[str]] = self.limit_character_scope(
                config.pop(["metadata"]["key"], default_conf["metadata"]["key"]))
            """ Columns that define the uniqueness of each row in the metadata file"""
            self.tables_associations: Dict[str, TableAssociation] = self.limit_character_scope(
                config.pop(["metadata"]["association"], default_conf["metadata"]["association"]))
            """ Columns that define the tables associations in the metadata file with multiple tables. Example: "{<Table1>": {"PK":"<ID1>","FK": {"<Table2>": "FK2"}},<Table2>": {"PK":"<ID2>","FK": {}}}"""
            self.required_columns: Dict[str,list[str]] = self.limit_character_scope(
                config.pop(["metadata"]["in columns"]), default_conf["metadata"]["in columns"])
            """ Columns required in the input metadata file"""
            self.rows_sort_by: Dict[str,str] = self.limit_character_scope(
                config.pop(["metadata"]["sort by"]), default_conf["metadata"]["sort by"])
            """ Columns that define the column by which the rows in the metadata file are sorted. Default to None, will sort by the order in which the files were posted adding a column with serial number to the data"""
            self.columns_data_filenames: Dict[str,list[str]] = self.limit_character_scope(
                config.pop(["metadata"]["data filenames"]), default_conf["metadata"]["data filenames"])
            """ Columns that contain the names of data files associated with each row metadata"""
            self.columns_data_published: Dict[str,list[str]] = self.limit_character_scope(
                [config.pop(["metadata"]["data published flag"], default_conf["metadata"]["data published flag"])])[0]
            """ Columns that contain the publication status of each row"""
            self.add_filename: Dict[str,str] = config.pop(["metadata"]["add filename"], default_conf["metadata"]["add filename"])
            """ Dictionary with table names (keys) in which a column with the defined names (values) should be created to store the source filename. Leave blank if not needed. Example: {"<table>": "<column_name>"}"""
            self.filename_data_format: Dict[str, re.Pattern] = {
                k: re.compile(v) for k, v in config.pop(["metadata"]["filename data format"], default_conf["metadata"]["filename data format"]).items()
            }
            """ Dictionary with table names (keys) and regex patterns (values) to extracted data from the filename and add to the indicated table. Use re.match.groupdict() syntax."""
            self.filename_data_processing_rules: Dict[str, Dict[str, Any]] = config.pop(["metadata"]["filename data processing rules"],
                                                                                        default_conf["metadata"]["filename data processing rules"])
            """ Dictionary with old and new characters to be replaced in the data extracted from the filename, defined for each key in the replacement pattern."""

            # Pop empty objects within the config in the dict
            if not config["log"]:
                config.pop("log")
            if not config["files"]:
                config.pop("files")
            if not config["metadata"]:
                config.pop("metadata")
            if config:
                print(f"Configuration file contains unknown keys: {json.dumps(config)}")
                exit(1)

        except Exception as e:
            print(f"Configuration files missing arguments: {e}")
            exit(1)

    # --------------------------------------------------------------
    def __ensure_list(self, item: Any) -> list[str]:
        """Create a list from a string or a list, adding a root path if it exists.
        
        Args:
            item (Any): Input string or list.
            
        Returns:
            list[str]: List of strings.
        
        Raises: None
        """
        
        if isinstance(item, str):
            return [item]
        else:
            return item

    # --------------------------------------------------------------
    def __load_into_config(self, filename: str) -> Dict[str, Any]:
        """Load;update the configuration values from a JSON file encoded with UTF-8.
        
        Args:
            filename (str): Configuration file name.
        
        Returns:
            Dict[str, Any]: Configuration values.
        
        Raises: None
        """
        
        try:
            with open(filename, 'r', encoding='utf-8') as json_file:
                return json.load(json_file)
            
        except FileNotFoundError:
            print(f"Config file not found in path: {filename}")
            exit(1)
        except Exception as e:
            print(f"Error reading config file: {e}")
            exit(1)

    # --------------------------------------------------------------
    def __log_format_colour(self,
                            log_format: list[str],
                            colour_format: list[str],
                            log_separator: str) -> str:
        """Return the log format string.

        Args:
            log_format (list[str]): The log format.
            colour_format (list[str]): The colour format.
            log_separator (str): The log separator.

        Returns:
            str: Log format string.
            
        Raises: None
        """
        
        output_format = ""
        colour_count = 0
        colour_set = '\x1b['
        separator = f"{colour_set}0m{log_separator}"
        for item in log_format:
            output_format = f"{output_format}{colour_set}{colour_format[colour_count]}{item}{separator}"
            colour_count += 1
            if colour_count == len(colour_format):
                colour_count = 0
                        
        return output_format[:-len(log_separator)]

    # --------------------------------------------------------------
    def __log_format_file(self, format_string:list[str], log_separator:str) -> str:
        """Return the log format string.

        Args:
            format_string (list[str]): The format string.
            log_separator (str): The log separator.

        Returns:
            str: Log format string.
        
        Raises: None
        """
        
        output_format = ""
        for item in format_string:
            output_format = f"{output_format}{item}{log_separator}"
        
        return output_format[:-len(log_separator)]

    # --------------------------------------------------------------
    def __log_titles(self, log_format:list[str], log_separator:str) -> str:
        """Return the log column titles as a string.

        Args:
            log_format (list[str]): The log format.
            log_separator (str): The log separator.

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
        for item in log_format:

            for non in non_title:
                item = item.replace(non, "")
            
            output_format = f"{output_format}{item}{log_separator}"
        
        return output_format[:-len(log_separator)]
    
    # --------------------------------------------------------------
    def limit_character_scope(self, data: Any) -> Any:
        """
        Remove characters that are not in the character_scope from the string(s).
        
        Args:
            data (list[str] | dict): Input list of strings or dictionary to be cleaned.
            
        Returns:
            list[str] | dict: Output with only characters in the character_scope kept.
        """
        if self.character_scope == "all":
            return data

        # Serialize input to JSON string
        json_data = json.dumps(data)
        # Remove unwanted characters using re.sub
        cleaned_json = re.sub(self.character_scope, '', json_data)
        # Deserialize back to original structure
        try:
            return json.loads(cleaned_json)
        except Exception:
            # If deserialization fails, return original data
            return data
    
    # --------------------------------------------------------------
    def set_last_clean(self) -> None:
        """Update object attribute and store state to JSON file
        
        Args:
            None
            
        Returns:
            None

        Raises:
            Exception: Config file write error.
        """
        
        self.last_clean = pd.to_datetime("now")
        
        self.raw["last clean"] = self.last_clean.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as json_file:
                json.dump(self.raw, json_file, indent=4)
        except Exception as e:
            raise Exception(f"File write error: {e}")
            
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
    def __build_worksheet_dict(self, tables: dict) -> dict:
        """Build a dictionary with the tables to be used in the data files.

        Args:
            tables (list[str]): List of tables to be used in the data files.

        Returns:
            list[dict]: List of dictionaries with the tables.
        """
        
        if tables[self.default_worksheet_key] == self.default_worksheet_name:
            tables[self.default_worksheet_key] = self.name
        
        return tables

    
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

