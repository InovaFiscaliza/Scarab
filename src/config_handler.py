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
import copy
import traceback

# --------------------------------------------------------------
# Control Constants
MANDATORY_CONFIG_ROOT_KEYS: list[str] = ["log", "folders", "files", "metadata"]
"""Mandatory keys in the root of the configuration file."""
DEFAULT_CONFIG_FILENAME:str = "default_config.json"
"""Default configuration file name."""
FK_KEY:str = "FK"
"""Key to identify foreign key values in table association dictionaries."""
PK_KEY:str = "PK"
"""Key to identify primary key values in table association dictionaries."""
NAME_KEY:str = "name"
"""Key to identify table name values in table association dictionaries."""
INT_TYPE_KEY:str = "int type"
"""Key to indicate that the primary key is a numerical sequence in table association dictionaries."""
RELATIVE_VALUE_KEY:str = "relative value"
"""Key to indicate that the primary key is relative within the file in table association dictionaries."""
REFERENCED_BY_KEY:str = "referenced by"
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
SORT_BY_KEY:str = "by"
"""Key to identify sorting columns in the metadata file."""
ASCENDING_SORT_KEY:str = "ascending"

# --------------------------------------------------------------
# Define the structure of complex types
class PKInfoBase(TypedDict):
    """Base structure of the primary key in the table association."""
    name: str
    """Name of the primary key column."""
    int_type: bool
    """Flag to indicate that key is a numerical sequence. Alternative is the use of UID, either numeric or strings."""
    relative_value: bool
    """Flag to indicate that key is relative within the file. Alternative is absolute, unique to any file that may be loaded."""

class PKInfo(PKInfoBase, total=False):
    """Extended structure of the primary key with reference tracking."""
    referenced_by: set[str]  # List of tables that reference this primary key
    """List of tables that reference this primary key."""

class TableAssociation(TypedDict, total=False):
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
        config: Dict[str, Any] = self._load_into_config(filename)
        self.raw: Dict[str, Any] = copy.deepcopy(config)
        """Raw configuration values."""
        # Ensure mandatory keys exist in config
        config = self._ensure_mandatory_structure(config)
        
        # Get config file path from the script path
        source_path = os.path.dirname(os.path.abspath(__file__))
        default_conf_file = os.path.join(source_path, DEFAULT_CONFIG_FILENAME)
        default_conf = self._load_into_config(default_conf_file)
        
        try:
            self.name: str = config.pop("name", default_conf["name"])
            """ Name of the config.pop(uration, used for logging"""
            self.scarab_version: str = config.pop("scarab version", default_conf["scarab version"])
            """ Version of the scarab script"""
            self.check_period: int = config.pop("check period in seconds", default_conf["check period in seconds"])
            """ Period to check input folders in seconds """
            self.clean_period: pd.Timedelta = pd.Timedelta(hours=config.pop("clean period in hours", default_conf["clean period in hours"]))
            """ Period to clean temp folders in hours"""
            self.last_clean: pd.Timestamp = self._build_last_clean_time(config.pop("last clean", default_conf["last clean"]),
                                                                        config.pop("delay first clean", default_conf["delay first clean"]))
            """ Timestamp of the last clean operation"""
            self.maximum_errors_before_exit: int = config.pop("maximum errors before exit", default_conf["maximum errors before exit"])
            """ Maximum number of errors before exiting with raised error"""
            self.maximum_file_variations: int = config.pop("maximum file variations", default_conf["maximum file variations"])
            """ Maximum number of file variations before exiting with raised error"""
            self.character_scope: str = config.pop("character scope", default_conf["character scope"])
            """ characters that will be retained from the column names. Characters not in the scope will be removed"""
            self.null_string_values: list[str] = self._ensure_list(config.pop("null string values", default_conf["null string values"]))
            """ List of strings that will be considered as null values in the metadata file"""
            self.default_worksheet_key:str = config.pop("default worksheet key", default_conf["default worksheet key"])
            """Default key to be used for the worksheet that will retain single table values or non mapped values in the json root."""
            self.default_multiple_object_key:str = config.pop("default multiple object key", default_conf["default multiple object key"])
            """Default key to be used to designate operations that are applicable to multiple tables/worksheets."""
            self.default_unlimited_characters_scope: str = config.pop("default unlimited characters scope", default_conf["default unlimited characters scope"])
            """Default value for the unlimited characters scope. If the character scope uses this character, no restriction to the characters in the column names will be applied."""
            self.default_worksheet_name:str = config.pop("default worksheet name", default_conf["default worksheet name"])
            """Default value for the worksheet name. If value of assigned to the default key is equal to this value, will use the name of the config.pop(uration."""
            self.store_data_overwrite: bool = config.pop("overwrite data in store", default_conf["overwrite data in store"])
            """ Flag to indicate if data should be overwritten in store folder"""
            self.get_data_overwrite: bool = config.pop("overwrite data in get", default_conf["overwrite data in get"])
            """ Flag to indicate if data should be overwritten in get folders"""
            self.trash_data_overwrite: bool = config.pop("overwrite data in trash", default_conf["overwrite data in trash"])
            """ Flag to indicate if data should be overwritten in trash folder"""
            self.discard_invalid_data_files: bool = config.pop("discard invalid data files", default_conf["discard invalid data files"])
            """ Flag to indicate if invalid data files should be discarded"""
            
            log_separator: str = config["log"].pop("separator", default_conf["log"]["separator"])
            """ Log column separator"""
            log_format: list[str] = config["log"].pop("format", default_conf["log"]["format"])
            """ Data columns to be presented in the log file using logging syntax"""
            colour_sequence: list[str] = config["log"].pop("colour sequence", default_conf["log"]["colour sequence"])
            """ Colour sequence to be used in the log file using logging syntax"""
            
            self.log_level: str = config["log"].pop("level", default_conf["log"]["level"])
            """ Logging level"""
            self.log_to_screen: bool = config["log"].pop("screen output", default_conf["log"]["screen output"])
            """ Flag to log to screen"""
            self.log_to_file: bool = config["log"].pop("file output", default_conf["log"]["file output"])
            """ Flag to log to file"""
            self.log_file_path: str = self._ensure_list(config["log"].pop("file path", default_conf["log"]["file path"]))
            """ Log file name with path"""            
            self.log_file_format: str = self._log_format_file(log_format, log_separator)
            """ Data columns to be presented in the log file using logging syntax"""
            self.log_screen_format: str = self._log_format_colour(log_format, colour_sequence, log_separator)
            """ Data columns to be presented in the terminal using logging syntax, with colours"""
            self.log_title: str = self._log_titles(log_format, log_separator)
            """ Log header line based on the log format"""
            self.log_overwrite: bool = config["log"].pop("overwrite log in trash", default_conf["log"]["overwrite log in trash"])
            """ Flag to overwrite log in trash"""

            self.temp: str = default_conf["folders"].get("temp", config["folders"].pop("temp"))
            """ Folder used for file storage while processing is taking place. [! Mandatory]"""
            self.input_path_list: list[str] = [self.temp] + self._ensure_list(config["folders"].pop("post", default_conf["folders"]["post"]))
            """ File input paths. Include all post folders and the temp folder as the first element."""
            self.trash: str = default_conf["folders"].get("trash", config["folders"].pop("trash"))
            """ Trash folder path used for files posted using wrong format. [! Mandatory]"""
            self.store: str = default_conf["folders"].get("store", config["folders"].pop("store"))
            """ Store folder path used to store processed files. [! Mandatory]"""
            self.get: Dict[str:list[str]] = self._build_list_dict(config["folders"].pop("get", default_conf["folders"]["get"]),"folders/get")
            """ For each key associated with a matching pattern defined in the "data file regex", a list of target folders is defined, to which matching files should be moved."""
            
            self.catalog_files: list[str] = self._ensure_list(config["files"].pop("catalog names", default_conf["files"]["catalog names"]))
            """ Full path to the catalog file, where metadata is stored"""
            self.metadata_file_regex: Dict[str, re.Pattern] = self._build_re_dict(config["files"].pop("metadata file regex", default_conf["files"]["metadata file regex"]),"metadata file regex")
            """ Regex pattern to be used to select files that may contain metadata."""
            self.data_file_regex: Dict[str, re.Pattern] = self._build_re_dict(config["files"].pop("data file regex", default_conf["files"]["data file regex"]),"data file regex")
            """ Dictionary with regex formatting to be used to select filenames to be processed as raw data files"""
            self.catalog_extension: str = os.path.splitext(self.catalog_files[0])[1]
            """ Extension used to identify the catalog files"""
            self.input_to_ignore: set[str] = set(self._ensure_list(config["files"].pop("input to ignore", default_conf["files"]["input to ignore"])))
            """ Set with files and folders to ignore in the input folders. Files within ignored folders will not be ignored. Use exact names only, including relative path to the input folder."""

            self.table_names: Dict[str,str] = self._set_default_table_name(config["files"].pop("table names", default_conf["files"]["table names"]))
            """ Table names to be used. {"json_root_table_name": "worksheet_name", ...]"""
            self.sheet_names: Dict[str,str] = { v: k for k, v in self.table_names.items() }
            """ Sheet names to be used. {"worksheet_name": "json_root_table_name", ...]"""

            self.required_tables: set[str] = set(self.limit_character_scope(
                self._ensure_list(
                    config["metadata"].pop("required tables", default_conf["metadata"]["required tables"]))))
            """ Columns that define the tables required in the metadata file"""
            self.table_associations: Dict[str, TableAssociation] = self._validate_table_associations(config["metadata"].pop("association", default_conf["metadata"]["association"]))
            """ Columns that define the tables associations in the metadata file with multiple tables. Example: "{<Table1>": {"PK":"<ID1>","FK": {"<Table2>": "FK2"}},<Table2>": {"PK":"<ID2>","FK": {}}}"""
            self.key_columns: Dict[str,set[str]] = self._build_set_dict(config["metadata"].pop("key", default_conf["metadata"]["key"]),"key")
            """ Columns that define the uniqueness of each row in the metadata file"""
            self.required_columns = self._merge_dict_set(config["metadata"].pop("in columns", default_conf["metadata"]["in columns"]), self.key_columns, "in columns")
            """ Columns required in the input metadata file"""
            self.rows_sort_by: Dict[str,Dict[str, list]] = self._build_row_sorting_dict(config["metadata"].pop("sort by", default_conf["metadata"]["sort by"]))
            """ Columns that define the column by which the rows in the metadata file are sorted. Default to None, will sort by the order in which the files were posted adding a column with serial number to the data"""
            self.columns_data_filenames: Dict[str,list[str]] = self.limit_character_scope(
                config["metadata"].pop("data filenames", default_conf["metadata"]["data filenames"]))
            """ Columns that contain the names of data files associated with each row metadata"""
            self.columns_data_published: Dict[str,list[str]] = self.limit_character_scope(
                [config["metadata"].pop("data published flag", default_conf["metadata"]["data published flag"])])[0]
            """ Columns that contain the publication status of each row"""
            self.expected_columns_in_files: Dict[str, set[str]] = self._get_expected_columns_in_files(
                config["metadata"].get("add filename", default_conf["metadata"]["add filename"]),
                config["metadata"].get("filename data format", default_conf["metadata"]["filename data format"]))
            """ Dictionary with table names (keys) and set of new columns to be created from the filename data format and add filename rules."""
            self.add_filename: Dict[str,str] = config["metadata"].pop("add filename", default_conf["metadata"]["add filename"])
            """ Dictionary with table names (keys) in which a column with the defined names (values) should be created to store the source filename. Leave blank if not needed. Example: {"<table>": "<column_name>"}"""
            self.filename_data_format: Dict[str, re.Pattern] = self._build_re_dict(config["metadata"].pop("filename data format", default_conf["metadata"]["filename data format"]),"filename data format")
            """ Dictionary with table names (keys) and regex patterns (values) to extract data from the filename. Use re.match.groupdict() syntax."""
            self.filename_data_processing_rules: Dict[str, Dict[str, Any]] = config["metadata"].pop("filename data processing rules",
                                                                                        default_conf["metadata"]["filename data processing rules"])
            """ Dictionary with old and new characters to be replaced in the data extracted from the filename, defined for each key in the replacement pattern."""

            # Pop empty objects within the config in the dict
            config = self._remove_empty_keys(config)
            if config:
                print(f"\n\nError: Configuration file contains unknown keys: {json.dumps(config)}")
                exit(1)
                
            self._test_get_regex()

        except KeyError as e:
            print(f"\n\nError: Configuration files missing arguments: {e}")
            exit(1)
        except ValueError as e:
            print(f"\n\nError: Configuration files invalid arguments: {e}")
            exit(1)
        except Exception as e:
            print(f"\n\nError: Unknown error occurred when loading '{filename}': {e}")
            exit(1)

    # --------------------------------------------------------------
    def _ensure_list(self, item: Any) -> list[str]:
        """Create a list from a string or a list, adding a root path if it exists.
        
        Args:
            item (Any): Input string or list.
            
        Returns:
            list[str]: List of strings.
        
        Raises: None
        """
        
        if isinstance(item, str):
            return [item]
        elif isinstance(item, list):
            return item
        else:
            print(f"\n\nError: Invalid type for item: {type(item)}. Expected a string or a list.")
            exit(1)

    # --------------------------------------------------------------
    def _ensure_mandatory_structure(self, config: Dict) -> Dict[str, Any]:
        """Create a dictionary from a string or a dictionary.
        
        Args:
            item (Any): Input string or dictionary.
            
        Returns:
            Dict[str, Any]: Dictionary of strings.
        
        Raises: None
        """
        
        # Ensure required keys exist in config with empty dicts if missing
        for key in MANDATORY_CONFIG_ROOT_KEYS:
            config.setdefault(key, {})
        
        return config

    # --------------------------------------------------------------
    def _get_expected_columns_in_files(  self,
                                        add_filename: dict[str,str],
                                        filename_data_format: dict[str,str]) -> dict[str,set[str]]:
        """Get expected columns in files based on add_filename and filename_data_format.	
        
        Args:
            add_filename (dict[str,str]): Dictionary with table names (keys) and column names (values) to be added to the metadata.
            filename_data_format (dict[str,str]): Dictionary with table names (keys) and regex patterns (values) to extract data from filenames.
            
        Returns:
            dict[str, set[str]]: Dictionary with table names (keys) and sets of expected columns (values).
        """
        
        # Start with columns from add_filename values
        new_columns: dict[str, set[str]] = {table: {col} for table, col in add_filename.items()}
        
        # Extract named capture groups from regex patterns
        pattern: re.Pattern = re.compile(r'<(.*?)>')
        for table, format_string in filename_data_format.items():
            # Find all matches and add them to the set for this table
            matches: list = pattern.findall(format_string)
            new_columns.setdefault(table, set()).update(matches)
        
        all_tables: set = set(self.required_columns.keys()) | set(self.key_columns.keys())

        expected_columns: dict[str, set[str]] = {table: set() for table in all_tables}
        for table in all_tables:
            expected_columns[table] = (self.required_columns.get(table, set())
                                        .union(self.key_columns.get(table, set()))
                                        .difference(new_columns.get(table, set())))
        
        return expected_columns

    # --------------------------------------------------------------
    def _merge_dict_set(self, 
                            new_data: Dict[str, Any],
                            existing_set : Dict[str, set[str]],
                            name: str) -> Dict[str, set[str]]:
        """Merge a dictionary of sets with the key columns to create a unified dictionary of required columns.
        
        Args:
            new_data (Dict[str, Any]): Dictionary with table names as keys and sets of required columns as values.
            existing_set (Dict[str, set[str]]): Existing dictionary with table names as keys and sets of required columns as values.
            name (str): Name of the configuration section for logging purposes.
            
        Returns:
            Dict[str, set[str]]: Merged dictionary with table names as keys and sets of required columns as values.
        """
        
        data = self._build_set_dict(new_data, name)
        
        self.key_columns  # Already built above

        merged_dict: Dict[str, set[str]] = {}
        all_keys = set(data.keys()) | set(existing_set.keys())
        for k in all_keys:
            merged_dict[k] = data.get(k, set()).union(existing_set.get(k, set()))
        
        return merged_dict
    
    # --------------------------------------------------------------
    def _build_last_clean_time(self, last_clean: str, delay_clean: bool) -> pd.Timestamp:
        """Build the last clean time from the configuration value.
        
        Args:
            last_clean (Any): Last clean time from the configuration file.
            
        Returns:
            pd.Timestamp: Last clean time as a pandas Timestamp.
        
        Raises:
            ValueError: If the last clean time is not in a valid format.
        """
        
        try:
            timestamp = pd.to_datetime(last_clean, format="%Y-%m-%d %H:%M:%S")
        except ValueError:
            timestamp = pd.Timestamp.now()
            if last_clean != "none":
                print(f"\n\nError: Invalid 'last clean' time format: {last_clean}. Expected format: YYYY-MM-DD HH:MM:SS")
        
        if delay_clean:
            timestamp += self.clean_period
        
        return timestamp

    # --------------------------------------------------------------
    def _remove_empty_keys(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Remove empty keys from the configuration dictionary.
        
        Args:
            config (Dict[str, Any]): Configuration dictionary.
        
        Returns:
            Dict[str, Any]: Configuration dictionary without empty keys.
        
        Raises: None
        """
        
        return {k: v for k, v in config.items() if v not in [None, {}, []]}

    # --------------------------------------------------------------
    def _validate_table_associations(self, associations: Dict[str, Any]) -> Dict[str, TableAssociation]:
        """Validate table associations and create back references to link the primary keys to tables that reference them.
        
        Args:
            associations (Dict[str, Any]): Table associations from the configuration file.
        
        Returns:
            Dict[str, TableAssociation]: Expanded table associations.
        
        Raises: None
        """
        
        associations = self.limit_character_scope(associations)
        fk_required_keys = {NAME_KEY, INT_TYPE_KEY, RELATIVE_VALUE_KEY}
        
        for table, assoc in associations.items():
            
            if assoc.get(PK_KEY,False):
                if not isinstance(assoc[PK_KEY], dict):
                    # test if assoc[PK_KEY] is an instance of the class PKInfoBase
                    print(f"\n\nError in config file. Invalid primary key data type in table {table}: Used {assoc[PK_KEY]}, expected a dictionary.")
                    exit(1)
                    
                if not fk_required_keys.issubset(assoc[PK_KEY].keys()):
                    print(f"\n\nError in config file. Invalid primary key structure in table {table}: Used {assoc[PK_KEY]}, expected a dictionary with keys: {fk_required_keys}.")
                    exit(1)
                    
            if assoc.get(FK_KEY, False):
                if not isinstance(assoc[FK_KEY], dict):
                    print(f"\n\nError in config file. Invalid foreign key structure in table {table}: Used {assoc[FK_KEY]}, expected a dictionary with table names as keys and column names as values.")
                    exit(1)
            
                for fk_table, fk_column in assoc[FK_KEY].items():
                    if not isinstance(fk_table, str) or not isinstance(fk_column, str):
                        print(f"\n\nError in config file. Invalid foreign key structure in table {table}: Used {fk_table}:{fk_column}, expected a string for table name and column name.")
                        exit(1)
                    
                    # test if fk_table is defined in the associations
                    if fk_table not in associations:
                        print(f"\n\nError in config file. Foreign key table {fk_table} in table {table} points to non defined table.")
                        exit(1)

                    associations[fk_table][PK_KEY].setdefault(REFERENCED_BY_KEY, set())
                    associations[fk_table][PK_KEY][REFERENCED_BY_KEY].add(table)
        
        return associations

    # --------------------------------------------------------------
    def _test_get_regex(self) -> None:
        """Test keys in dictionaries associated with the get folders have corresponding regex patterns defined.
        
        Args:
            None
            
        Returns:
            None
            
        Raises:
            ValueError: If a key in the get folders does not have a corresponding regex pattern defined.
        """
        
        no_regex = not self.data_file_regex and not isinstance(self.data_file_regex, dict)
        no_get = not self.get and not isinstance(self.get, dict)

        if no_regex and no_get:
            return  # Nothing to check
        elif no_regex and not no_get:
            raise ValueError("Config not functional. 'get' folder correctly defined but not the corresponding 'data file regex'")
        elif not no_regex and no_get:
            raise ValueError("Config not functional. 'data file regex' correctly defined but not the corresponding 'get' folders")
        # else: both are present, continue with further checks
        
        data_file_regex_copy = self.data_file_regex.copy()
        for keys in self.get.keys():
            key_found = data_file_regex_copy.pop(keys, None)
            if not key_found:
                raise ValueError(f"Key '{keys}' in 'get' folders does not have a corresponding regex pattern defined in 'data file regex'.")
        
        if data_file_regex_copy:
            raise ValueError(f"Regex patterns defined in 'data file regex' without corresponding keys in 'get' folders: {', '.join(data_file_regex_copy)}. Please check the configuration file.")
                

    # --------------------------------------------------------------
    def _load_into_config(self, filename: str) -> Dict[str, Any]:
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
            # If we reach this point, the file was empty or not valid JSON
            print(f"\n\nError: Config file is empty or invalid JSON: {filename}")
            exit(1)
        except FileNotFoundError:
            print(f"\n\nError: Config file not found in path: {filename}")
            exit(1)
        except Exception as e:
            print(f"\n\nError: When attempting to read file: {e}")
            exit(1)

    # --------------------------------------------------------------
    def _log_format_colour(self,
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
    def _log_format_file(self, format_string:list[str], log_separator:str) -> str:
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
    def _log_titles(self, log_format:list[str], log_separator:str) -> str:
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
    def _build_list_dict(  self, data : Dict[str, Any], name: str) -> Dict[str, list[str]]:
        """Validate serialized input and build a dictionary with set values
        
        Args:
            data (Dict[str, Any]): Input data from serialized json file.
            name (str): Name of the data type being processed, used for error messages.
            
        Returns:
            Dict[str, list[str]]: Dictionary with table names as keys and list of strings as values.
        """
        
        # test if data is of dict type, if not, raise an error
        if not isinstance(data, dict):
            print(f"\n\nError: Invalid data '{type(data)}'. Expected a dictionary in config {name} for list creation.")
            exit(1)
            
        return {k: self._ensure_list(v) for k, v in data.items()}

    # --------------------------------------------------------------
    def _build_set_dict(  self, data : Dict[str, Any], name: str) -> Dict[str, set[str]]:
        """Validate serialized input and build a dictionary with set values
        
        Args:
            data (Dict[str, Any]): Input data from serialized json file.
            name (str): Name of the data type being processed, used for error messages.
            
        Returns:
            Dict[str, set[str]]: Dictionary with table names as keys and sets of strings as values.
        """
        
        # test if data is of dict type, if not, raise an error
        if not isinstance(data, dict):
            print(f"\n\nError: Invalid data: '{type(data)}'. Expected a dictionary in config {name} for set creation.")
            exit(1)
        
        # Use a dictionary comprehension to convert each list to a set directly
        return {k: set(self._ensure_list(v)) for k, v in data.items()}
    
    # --------------------------------------------------------------
    def _build_re_dict(self, data: Dict[str, str], name) -> Dict[str, re.Pattern]:
        """Build a dictionary with regex patterns for extracting data from filenames.
        
        Args:
            data (Dict[str, str]): Input data with table names as keys and regex patterns as values.
            
        Returns:
            Dict[str, re.Pattern]: Dictionary with table names as keys and compiled regex patterns as values.
        """
        
        # test if data is of dict type, if not, raise an error
        if not isinstance(data, dict):
            print(f"\n\nError: Invalid type for filename data format: {type(data)} in config '{name}'. Expected a dictionary.")
            exit(1)

        return {k: re.compile(v) for k, v in data.items()}
    
    # --------------------------------------------------------------
    def _build_row_sorting_dict(self, data: Dict[str,Dict[str, list]]) -> Dict[str,Dict[str, list]]:
        """Build a dictionary with columns to sort rows in the metadata file.
        
        Args:
            data (Dict[str, str]): Input data with table names as keys and column names as values.
            
        Returns:
            Dict[str, str]: Dictionary with table names as keys and column names as values.
        """
        
        # test if data is of dict type, if not, raise an error
        if not isinstance(data, dict):
            print(f"\n\nError: Invalid type for row sorting: {type(data)}. Expected a dictionary.")
            exit(1)
        
        for key in self.key_columns.keys():
            if key not in data:
                data[key] = None
            elif isinstance(data[key], dict):
                if SORT_BY_KEY in data[key]:
                    data[key][SORT_BY_KEY] = self._ensure_list(self.limit_character_scope(data[key][SORT_BY_KEY]))
                else:
                    print(f"\n\nError: Invalid row sorting value for table '{key}': {data[key]}. Expected a dict with '{SORT_BY_KEY}' key.")
                    exit(1)
                if ASCENDING_SORT_KEY in data[key]:
                    if isinstance(data[key][ASCENDING_SORT_KEY], list):
                        if not all(isinstance(x, bool) for x in data[key][ASCENDING_SORT_KEY]):
                            print(f"\n\nError: Invalid ascending sort value for table '{key}': {data[key][ASCENDING_SORT_KEY]}. Expected a list of boolean.")
                            exit(1)
                        if len(data[key][ASCENDING_SORT_KEY]) != len(data[key][SORT_BY_KEY]):
                            print(f"\n\nError: Invalid ascending sort value for table '{key}': {data[key][ASCENDING_SORT_KEY]}. Expected a list of boolean with the same length as the sort by list.")
                            exit(1)
                    elif not isinstance(data[key][ASCENDING_SORT_KEY], bool):
                        print(f"\n\nError: Invalid ascending sort value for table '{key}': {data[key][ASCENDING_SORT_KEY]}. Expected a boolean or list of booleans.")
                        exit(1)
                else:
                    print(f"\n\nError: Invalid row sorting value for table '{key}': {data[key]}. Expected a dict with '{ASCENDING_SORT_KEY}' key.")
                    exit(1)
            else:
                print(f"\n\nError: Invalid row sorting value for table '{key}': {data[key]}. Expected a dict. For default post order ordering, remove key.")
                exit(1)
                
        return data
    
    # --------------------------------------------------------------
    def _str_clean_recursive(self, data: Any) -> Any:
        """Recursively clean strings in a nested structure by removing characters not in the character_scope.
        Args:
            data (Any): Input data which can be a string, list, or dictionary.
        Returns:
            Any: Cleaned data with only characters in the character_scope kept.
        """
        
        if isinstance(data, str):
            return re.sub(self.character_scope, '', data)
        elif isinstance(data, list):
            return [self._str_clean_recursive(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._str_clean_recursive(v) for k, v in data.items()}
        else:
            return data
    
    # --------------------------------------------------------------
    def limit_character_scope(self, data: Any) -> Any:
        """
        Remove characters that are not in the character_scope from the string(s).
        
        Args:
            data (list[str] | dict): Input list of strings or dictionary to be cleaned.
            
        Returns:
            list[str] | dict: Output with only characters in the character_scope kept.
        """
        if self.character_scope == self.default_unlimited_characters_scope:
            return data
        
        return self._str_clean_recursive(data)
    
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
    def _test_folder(self, folder: str, folder_type: str, message: str) -> tuple[bool, str]:
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
    def _test_file(self, filename: str, file_type: str, message: str, required:bool=False) -> tuple[bool, str]:
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
    def _set_default_table_name(self, tables: dict) -> dict:
        """Set the default worksheet name to the config name if the default worksheet key is present in the tables dictionary.

        Args:
            tables (list[str]): List of tables to be used in the data files.

        Returns:
            list[dict]: List of dictionaries with the tables.
        """
        
        if tables.get(self.default_worksheet_key) == self.default_worksheet_name:
            tables[self.default_worksheet_key] = self.name
        else:
            if self.log_level == "DEBUG":
                print(f"\n\nDebug: default_worksheet_key '{self.default_worksheet_key}' not found in tables. No default table name set. This may cause errors.")
        
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
        msg = f"\nError: In {self.config_file}:"
                
        for folder in self.post:
            test_result, msg = self._test_folder(folder, "Post", msg)
        
        test_result, msg = self._test_folder(self.store, "Store", msg)
        
        test_result, msg = self._test_folder(self.temp, "Temp", msg)
        
        test_result, msg = self._test_folder(self.trash, "Trash", msg)
        
        for folder in self.get:
            test_result, msg = self._test_folder(folder=folder,
                                                folder_type="Get",
                                                message=msg)

        for file in self.catalog_files:
            test_result, msg = self._test_file(filename=file,
                                                file_type="Catalog",
                                                message=msg)
        
        for file in self.log_file_path:
            test_result, msg = self._test_file(filename=file,
                                                file_type="Log",
                                                message=msg)
            
        test_result, msg = self._test_file(filename=self.config_file,
                                            file_type="Config",
                                            message=msg,
                                            required=True)
                
        if not test_result:
            msg += "\n\nPlease correct the errors and restart the script."
            print(msg)
        
        return test_result

    # --------------------------------------------------------------
    def exception_message_handling(self, msg:str) -> str:
        """Handle exceptions by logging the error message and traceback.

        Args:
            e (Exception): The exception to handle.
            frame (FrameType): The frame where the exception occurred.

        Returns:
            None

        Raises: None
        """
        
        tb = traceback.format_exc()
        msg += "\nFull traceback:"
        tb_lines = tb.splitlines()
        for line in tb_lines:
            msg += f"\n{line}"
            
        return msg