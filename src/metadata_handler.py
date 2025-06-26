#!/usr/bin/python
"""
Module class that handle file operations for the script.

Args (stdin): ctrl+c will soft stop the process similar to kill command or systemd stop <service>. kill -9 will hard stop.

Returns (stdout): As self.log.messages, if target_screen in self.log.is set to True.

Raises:
    Exception: If any error occurs, the exception is raised with a message describing the error.
"""

import config_handler as cm
import file_handler as fm

import logging
import os
import pandas as pd
import numpy as np
import uuid
import base58
import json

# ---------------------------------------------------------------
# Constants used only in this module and not affected by the config file
POST_ORDER_COLUMN_PREFIX = "post_order-"
INDEX_COLUMN_PREFIX = "index-"
DATA_FILE_COLUMN_PREFIX = "file-"

# --------------------------------------------------------------
class DataHandler:

    def __init__(self, config: cm.Config, log: logging.Logger) -> None:
        """Initialize the FileHandler object with the configuration and self.log.er objects.

        Args:
            config (cm.Config): Configuration object.
            log.(lm.Logger): self.log.er object.
        """
        self.config : cm.Config = config
        """Configuration object."""
        self.log : logging.Logger = log
        """Application log object."""
        self.file : fm.FileHandler = fm.FileHandler(config=config, log=log)
        """FileHandler object."""

        self.pending_metadata_processing : bool = True
        """Flag to indicate that there is metadata needs to be processed."""
        self.data_files_to_ignore : dict[str,set[str]] = { k :set() for k in self.config.data_file_regex.keys() }
        """List of data files that were processed but not found in the reference data. To be processed only if the reference data is updated."""
        
        self.unique_id : str = base58.b58encode(uuid.uuid4().bytes).decode('utf-8')
        """Unique identifier for the in class column naming."""
        self.index_column : str = f"{INDEX_COLUMN_PREFIX}{self.unique_id}"
        """Index column name. Used to concatenate the values of the columns defined as keys."""
        self.data_file_column : str = f"{DATA_FILE_COLUMN_PREFIX}{self.unique_id}"
        """Data file control column name. Used to concatenate the filenames of the data files when multiple columns are defined."""
        self.post_order_column : str = f"{POST_ORDER_COLUMN_PREFIX}{self.unique_id}"
        """Post order column name. Used to keep ordering of the rows in the DataFrame."""
        self._replace_empty_sorting_value()
        self.ordering_index : dict[str, int] = {}
        """Index used for sequentially ordering rows in the various tables if no ordering column is defined. """        
        
        df, col = self.read_reference_df()
        
        self.ref_df : dict[str,pd.DataFrame] = df
        """Dictionary with various dataframes containing the reference metadata in various tables."""
        self.ref_cols : dict[str,list[str]] = col
        """Dictionary with list of columns in in each reference DataFrame."""

        self.next_pk_counter : dict[str, int] = self._initialize_next_pk_counter()
        """ Dictionary with initial number to be used as primary keys in each table. The key is the table name and the value is the number of free primary keys. """
        self.pk_mod_table : dict[str,dict[str,str]] = {}
        """ Dictionary with the table name and key associated with the primary key in relative (in file) indexing and absolute (in reference data) indexing. """
        self.pk_int_offset : dict[str, int] = {}
        """ Dictionary with the table name and offset value to be used to convert the relative primary key to absolute primary key. """
        
        # --------------------------------------------------------------
    def _replace_empty_sorting_value(self) -> None:
        """Process the row sorting dictionary to ensure all values are lists.
        
        Args:
            sort_by (Dict[str, str]): The original dictionary with sorting values.
            
        Returns:
            Dict[str, str]: The processed dictionary with lists as values.
        """
        
        # Use dictionary comprehension to identify keys needing default values
        empty_keys = {k for k, v in self.config.rows_sort_by.items() if not v}
        
        # Bulk update only the keys that need changing
        if empty_keys:
            self.config.rows_sort_by.update({k: self.post_order_column for k in empty_keys})
    
    # --------------------------------------------------------------
    def _initialize_next_pk_counter(self) -> dict[str, int]:
        """Initialize the free primary key counter for each table in the reference data.

        Returns:
            dict[str, int]: Dictionary with the initial number to be used as primary keys in each table.
        """
        
        next_pk_counter = {}
        for table in self.ref_df.keys():
            # get the maximum value of the primary key column in the reference DataFrame
            try:
                pk_column = self.config.table_associations[table][cm.PK_KEY][cm.NAME_KEY]                
            except KeyError:
                self.log.debug(f"Table {table} does not have a primary key column defined in the config file.")
                continue
            
            try:
                if not pd.api.types.is_integer_dtype(self.ref_df[table][pk_column]):
                    self.ref_df[table][pk_column] = self.ref_df[table][pk_column].astype(int)

                max_pk = self.ref_df[table][pk_column].max()
            except Exception as e:
                self.log.debug(f"Using 1 as starting primary key value for table {table}: {e}")
                max_pk = np.int64(0)
            
            next_pk_counter[table] = max_pk + 1
            
            
        return next_pk_counter
    
    # --------------------------------------------------------------
    def drop_na(self, df: pd.DataFrame, table: str, file: str) -> pd.DataFrame:
        """Drop rows from the DataFrame where the ID column has a null value in any variant form, including NA, NaN, strings such as '<NA>', 'NA', 'N/A', 'None', 'null' and empty strings.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table (str): Name of the table to be used in the log message.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the rows where the ID column is not null.
        """
        
        rows_before = df.shape[0]
        
        df = df[~df[self.index_column].isin(self.config.null_string_values)]
        
        df = df.dropna(subset=[self.index_column])
        
        removed_rows = rows_before - df.shape[0]
        if removed_rows:
            self.log.info(f"Removed {removed_rows} rows with null values in key column(s) in table {table}, file '{file}'")
        
        return df
    
    # --------------------------------------------------------------
    def _custom_agg(self, series: pd.Series) -> str:
        """Custom aggregation function to be used in the groupby method. Null is kept as Null, single value is kept as is, and multiple values are concatenated with a comma separator.
        
        Args:
            series (pd.Series): Series to be aggregated.
            
        Returns:
            str: Aggregated value.
        """
        
        non_null_values = series.dropna().unique()
        
        match len(non_null_values):
            case 0:
                return None
            case 1:
                return non_null_values[0]
            case _:
                return ', '.join(non_null_values)            

    # --------------------------------------------------------------
    def _create_index(self, df: pd.DataFrame, table_name: str, file: str) -> pd.DataFrame:
        """Create an index for the DataFrame based on the columns defined in the config file. The index is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the index column created.
        """
        
        if self.config.key_columns is None:
            self.log.debug("No key columns defined in config. No index will be created.")
            return df
        
        if table_name not in self.config.key_columns:
            self.log.debug(f"No key columns defined for table {table_name} to use for processing file {file}")
            return df
        
        columns = list(self.config.key_columns[table_name])
        
        try:
            # create a column to be used as index, merging the columns in index_column list
            df = df.assign(**{self.index_column: df[columns].astype(str).agg('-'.join, axis=1)})
            
            # drop rows in which the column with name defined in the self.index_column has value null
            df = self.drop_na(df=df, table=table_name, file=file)
        
            # Identify rows with duplicate unique_name values
            duplicate_ids = df[self.index_column].duplicated(keep=False)
            duplicate_rows = df[duplicate_ids]
            
            if not duplicate_rows.empty:
                self.log.warning(f"Duplicated keys in {len(duplicate_rows)} rows in {file}, table {table_name}. Rows will be merged")
                # Apply the custom aggregation function to the duplicate rows
                aggregated_rows = duplicate_rows.groupby(self.index_column).agg(self._custom_agg)
                
                # get the rows that are not duplicated
                unique_rows = df[~duplicate_ids]
                unique_rows = unique_rows.set_index(self.index_column)
                
                # Combine the unique rows with the aggregated rows
                df = pd.concat([unique_rows, aggregated_rows])
            else:
                df = df.set_index(self.index_column)
                
        except KeyError as e:
            self.log.error(f"Key error in dataframe from file {file}, table {table_name}: {e}")
            return pd.DataFrame()
        except Exception as e:
            self.log.error(f"Error creating index in dataframe from file {file}, table {table_name}: {e}")
            return pd.DataFrame()
        
        return df

    # --------------------------------------------------------------
    def _set_types(self, df: pd.DataFrame, table_name: str, file: str) -> pd.DataFrame:
        """Set the types of the columns in the DataFrame based on the config file.
        The types are set according to the config file for table association

        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the types set.
        """
        
        assoc = self.config.table_associations.get(table_name, None)
        if assoc:
            pk_info = assoc.get(cm.PK_KEY, None)
            if pk_info:
                pk_column = pk_info.get(cm.NAME_KEY, None)
                if pk_column and pk_column in df.columns and pk_info.get(cm.INT_TYPE_KEY, False):
                    df[pk_column] = df[pk_column].astype(int)
            fk_info = assoc.get(cm.FK_KEY, None)
            if fk_info:
                for fk_table, fk_column in fk_info.items():
                    if self.config.table_associations[fk_table][cm.PK_KEY].get(cm.INT_TYPE_KEY, False):
                        df[fk_column] = df[fk_column].astype(int)
        else:
            self.log.debug(f"No table association defined for table {table_name}. No types will be set.")
            
        return df
    # --------------------------------------------------------------
    def _sort_dataframe(self, df: pd.DataFrame, table_name: str, file: str) -> pd.DataFrame:
        """Sort the DataFrame by the columns defined in the config file. The index is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the index column created.
        """
        
        if self.config.rows_sort_by is None:
            self.log.debug("No sorting columns defined in config. No sorting will be applied.")
            return df
        
        if table_name not in self.config.rows_sort_by:
            self.log.debug(f"No sorting columns defined for table {table_name}. No sorting will be applied.")
            return df
        
        index_value = self.ordering_index.get(table_name,0)
        df[self.post_order_column] = range(index_value, index_value + len(df))
        self.ordering_index[table_name] = index_value + len(df)
        
        # sort the DataFrame by the columns defined in the config file
        df = df.sort_values(by=self.config.rows_sort_by[table_name], ascending=True)
        
        return df
    
    # --------------------------------------------------------------
    def _create_data_file_control_column(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """Create a column with the filenames of the data files to which the metadata refers to. 
        The column is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.

        Returns:
            pd.DataFrame: DataFrame with the filenames column created.
        """
                
        if self.config.columns_data_filenames is None:
            self.log.debug("No data filenames control column defined in config.")
            return df
        
        if  table_name not in self.config.columns_data_filenames:
            self.log.debug(f"No data filenames control column defined for table {table_name}. No data files to process.")
            return df
        
        columns_in_df = [col for col in self.config.columns_data_filenames[table_name] if col in df.columns]
        
        if not columns_in_df:
            self.log.debug(f"No data filenames column in {table_name}. No data files to process.")
            return df
        
        # create a column to be used as index, merging the columns in index_column list
        data = {self.data_file_column: df[self.config.columns_data_filenames[table_name]].astype(str).agg('-'.join, axis=1)}
        df = df.assign(**data)
            
        return df
    
    # --------------------------------------------------------------
    def _fix_create_data_published_column(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """Create a column with the filenames of the data files to which the metadata refers to.
        The column is created by replacing the values in the column defined in the config file with "False" if the value is null or empty.
        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.
        Returns:
            pd.DataFrame: DataFrame with the data published column created.
        """

        if self.config.columns_data_published is None:
            self.log.debug("No data published control column defined in config.")
            return df
        
        if table_name not in self.config.columns_data_published:
            self.log.debug(f"No data published control column defined for table {table_name}. No data files to process.")
            return df

        for col in self.config.columns_data_published[table_name]:
            if col not in df.columns:
                df[col] = "False"
            else:
                df[col] = df[col].fillna("False")
                            
        df[self.config.columns_data_published[table_name]] = (
            df[self.config.columns_data_published[table_name]]
            .replace(self.config.null_string_values, "False")
        )
        
        return df
    
    # --------------------------------------------------------------
    def _id_and_validate_table(self, df: pd.DataFrame, assigned_table: str, file: str) -> tuple[bool, str]:
        """Identify and validate the table in the DataFrame according to required columns (columns in and keys) defined in the config file
        Args:
            df (pd.DataFrame): DataFrame to process.
            assigned_table (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.
            
        Returns:
            tuple[bool, str]: Tuple with a boolean indicating if the table is valid and the name of the table.

        """

        df_columns = set(df.columns.tolist())

        distance = {k: float('inf') for k in self.config.expected_columns_in_files.keys()}
        
        if assigned_table == self.config.default_multiple_object_key:
            assigned_table = None
        
        for table, required_columns in self.config.expected_columns_in_files.items():
            # compute the distance between the DataFrame columns and the required columns.
            # Required columns must be a subset of the DataFrame columns.
            # Smaller distance correspond to the dataframe that is the smaller superset of the required columns.
            # An empty column list will be a subset to all tables and the table with smallest number of columns will be returned.
            if required_columns.issubset(df_columns):
                distance[table] = len(df_columns - required_columns)
        
        # Find the table with minimum distance value
        min_distance_value = min(distance.values())
        
        # Find all tables with this minimum distance
        tables_with_min_distance = [table for table, dist in distance.items() if dist == min_distance_value]
        
        # If there's only one table with minimum distance, use it
        if len(tables_with_min_distance) == 1:
            assigned_table = tables_with_min_distance[0]
        # If there are multiple tables with same minimum distance (tie)
        elif len(tables_with_min_distance) > 1:
            # If assigned_table is already set and is among the minimum distance tables, keep it
            if assigned_table and assigned_table in tables_with_min_distance:
                # Keep the current assigned_table value (no change needed)
                pass
            else:
                # Raise error if no predefined table is available for tie-breaking
                self.log.error(f"Multiple tables ({tables_with_min_distance}) match the data equally well in file {file}")
                raise ValueError(f"Ambiguous table assignment in file {file}: {tables_with_min_distance}")
        
        # Check if the assigned table has an infinite distance (no match)
        if distance[assigned_table] == float('inf'):
            self.log.warning(f"No valid table found in file {file}. Columns do not match any table.")
            return False, assigned_table
        
        return True, assigned_table
    
    # --------------------------------------------------------------
    def process_table(self, df: pd.DataFrame, table_name: str, file: str) -> tuple[pd.DataFrame, list, str]:
        """Process the DataFrame to create, clean column names and other adjustments.
        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.
            
        Returns:
            pd.DataFrame: DataFrame with the data from the Excel file.
            list: List of columns in the DataFrame.
            str: Name of the table to be used as defined in the config file.
        """

        # Add columns based ob the filename
        transformations = [
            lambda df: self._add_filename_column(df, table_name, file),
            lambda df: self._add_filename_data(df, table_name, file),
        ]
        
        [df := transform(df) for transform in transformations]

        # If the DataFrame still empty, log a message and return an empty DataFrame
        if df.empty:
            self.log.debug(f"No data in DataFrame for table {table_name}. No data files to process.")
            return pd.DataFrame(), [], table_name
        
        # Validate the table based on the required columns and keys defined in the config file
        valid_table, table_name = self._id_and_validate_table(df, table_name, file)
        
        if not valid_table:
            self.log.warning(f"No valid table data found in file {file}.")
            return pd.DataFrame(), [], table_name
        
        # Remove escaped characters from column names
        df.columns = self.config.limit_character_scope(df.columns.tolist())

        # Performa additional table transformation considering existing data
        transformations = [
            lambda df: self._create_data_file_control_column(df, table_name),
            lambda df: self._fix_create_data_published_column(df, table_name),
            lambda df: self._create_index(df, table_name, file),
            lambda df: self._set_types(df, table_name, file),
            lambda df: self._sort_dataframe(df, table_name, file)
        ]
        
        [df := transform(df) for transform in transformations]

        # Get columns after all transformations
        columns = df.columns.tolist()

        return df, columns, table_name

    # --------------------------------------------------------------
    def create_dataframe(self, data: dict) -> pd.DataFrame:
        """Create a DataFrame from list of dictionaries.
        The dictionary keys are the column names and the values are the column values.
        If the input is a list of dictionaries, each dictionary will be a row in the DataFrame.
        If the input is a single dictionary, the DataFrame will have a single row.

        Args:
            data (dict): Dictionary with the data to create the DataFrame.

        Returns:
            pd.DataFrame: DataFrame with the data from the dictionary.
        """
        
        if isinstance(data, list):
            return pd.DataFrame(data, dtype="string")
        elif isinstance(data, dict):
            return pd.DataFrame([data], dtype="string")
        elif data is None:
            self.log.debug("Input data is None. Returning an empty DataFrame.")
            return pd.DataFrame()
        else:
            self.log.error(f"Unsupported data type: {type(data)}. Expected list, dict, or None.")
            raise ValueError(f"Unsupported data type: {type(data)}")

    # --------------------------------------------------------------
    def read_metadata(self, file: str, table: str) -> tuple[dict[str,pd.DataFrame], dict[str,list]]:
        """Read an metadata file and return a list of tuples with the DataFrame and the columns in the DataFrame.
        The file can be an Excel file, a CSV file or a JSON file.

        Args:
            file (str): Excel file to read.
            table (str): Name of the table to be used as defined in the config file.
            
        Returns:
            dict[str,pd.DataFrame]: Dictionary with the DataFrames containing various tables.
            dict[str,list]: Dictionary with the lists of columns for each table.
        """

        new_data_df = {key: pd.DataFrame() for key in self.config.table_names}
        new_data_columns = {key: [] for key in self.config.table_names}
        default_table_not_loaded =  True
        
        filetype = os.path.splitext(file)[1]
        
        try:
            match filetype:
                case '.xlsx':
                    # Read all worksheets from Excel file
                    with pd.ExcelFile(file) as excel_file:
                        sheet_names = excel_file.sheet_names
                        
                        # create a copy of sheet_names to avoid modifying the original list with the for loop
                        sheet_names_copy = sheet_names.copy()
                        
                        # If there are multiple worksheets
                        if len(sheet_names) > 1:
                            self.log.info(f"XLSX file {file} contains multiple worksheets: {sheet_names}")
                            
                            # Process each worksheet separately.
                            for sheet_name in sheet_names:
                                if sheet_name in new_data_df.keys():
                                    # Read the worksheet into a DataFrame
                                    new_df = excel_file.parse(sheet_name, dtype="string")
                                    
                                    table_name = self.config.sheet_names.get(sheet_name, sheet_name)

                                    if table_name == self.config.default_worksheet_key:
                                        default_table_not_loaded = False
                                    
                                    # Process the worksheet data
                                    new_df,  columns, table_name = self.process_table(
                                        df=new_df,
                                        table_name=table_name,
                                        file=file
                                    )
                                    new_data_df[table_name] = new_df
                                    new_data_columns[table_name] = columns
                                    
                                    # remove the processed sheet name from the list of new_data_df
                                    sheet_names_copy.remove(sheet_name)
                            
                        if len(sheet_names_copy) == 1 and default_table_not_loaded:
                            new_df = excel_file.parse(sheet_names_copy[0], dtype="string")                        
                        else:
                            self.log.warning("Multiple worksheets in file {file}. Check configuration to include table names to all worksheets.")
                                            
                case '.csv':
                    new_df = pd.read_csv(file, dtype="string")
                    
                case '.json':
                    # get data from the json file
                    with open(file, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    
                    # look for each defined table name in the json file and create a corresponding DataFrame
                    for table in new_data_df.keys():
                        if data and table in data:
                            new_df = self.create_dataframe(data[table])

                            new_df, columns, table_name = self.process_table(   df=new_df,
                                                                                table_name=table,
                                                                                file=file)
                            new_data_df[table_name] = new_df
                            new_data_columns[table_name] = columns

                            del data[table]
                    
                    # set flag if the default table was loaded
                    if not new_data_df[self.config.default_worksheet_key].empty:
                        default_table_not_loaded = False
                    else:
                        # add the remaining data from the json file to the default base_key table
                        if data:
                            new_df = self.create_dataframe(data)
                        else:
                            new_df = pd.DataFrame()
                            
                        table = self.config.default_worksheet_key
                    
                case _:
                    self.log.error(f"Unsupported metadata file type: {filetype}")
                    
            if default_table_not_loaded:
                new_df, columns, table_name = self.process_table(   df=new_df,
                                                                    table_name=table,
                                                                    file=file)
                new_data_df[table_name] = new_df
                new_data_columns[table_name] = columns
            
            if not self.config.required_tables.issubset(set(new_data_df.keys())):
                self.log.warning(f"File {file} does not contain all required tables: {self.config.required_tables}. No data will be processed from it.")
                return {}, {}
            
            return new_data_df, new_data_columns
            
        except Exception as e:
            self.log.error(f"Error reading metadata file {file}: {e}")
            return {}, {}

    # --------------------------------------------------------------
    def merge_lists(self, new_list: list, legacy_list: list) -> list:
        """Merge two lists into a single list
        Order of the elements in new_list keep minimum distance to the element order in the legacy_list.
        
        Args:
            new_list (list): List that will be the basis for the merged result.
            legacy_list (list): List that will be included.            
            
        Returns:
            list: Merged list.
        """

        new_set = set(new_list)
        legacy_set = set(legacy_list)
        items_not_in_new = legacy_set - new_set
        
        merged_list = new_list
        
        if items_not_in_new:
            self.log.debug(f"Items present in the existing list that are not in the new list: {items_not_in_new}")
            
            legacy_order = {item: i for i, item in enumerate(legacy_list)}
            new_order = {item: i for i, item in enumerate(new_list)}
            
            for item in items_not_in_new:
                
                keep_neighbor_search = True
                reached_beginning = False
                reached_end = False
                
                distance_to_neighbor = 1
                direction = 1 # 1 to previous, -1 to next
                position = legacy_order[item] - 1
                
                
                # If the first element in the legacy list is missing in the new list, the previous neighbor is None
                if position < 0:
                    direction = -1
                    position = legacy_order[item] + 1
                    reached_beginning = True
                
                while keep_neighbor_search:
                    
                    try:
                        # if neighbor is found in the new list, insert the item in the new list at the same relative position, update the new_set and new_order and stop the search
                        if legacy_list[position] in new_set:
                            position = new_order[legacy_list[position]]+direction
                            merged_list.insert(position, item)
                            new_set.add(item)
                            new_order = {item: i for i, item in enumerate(new_list)}
                            keep_neighbor_search = False
                        else:
                            # if moving to the end of the list, increase distance to the neighbor and if not reached the beginning, try the other direction
                            if direction == -1:
                                distance_to_neighbor += 1
                                if not reached_beginning:
                                    direction = 1
                            # if moving to the beginning of the list, keep the distance and try the other direction except if reached the end, then keep the direction and increase distance
                            else:
                                if reached_end:
                                    distance_to_neighbor += 1
                                else: 
                                    direction = -1
                                
                            position = legacy_order[item] - (distance_to_neighbor*direction)
                    except IndexError:
                        # if hit one of the ends, change direction and try again, marking the end reached
                        if position < 0:
                            reached_beginning = True
                            direction = -1
                        else:
                            reached_end = True
                            distance_to_neighbor += 1
                            direction = 1
                        
                        # if no neighbor is not found in the new list (maybe possible with empty initial list), insert the item at end and stop the search
                        if reached_beginning and reached_end:
                            merged_list.append(item)
                            keep_neighbor_search = False
                            reached_beginning = False
                            reached_end = False
                        
                        # update the current search position considering the direction taken
                        position = legacy_order[item] - (distance_to_neighbor*direction)
                        
        return merged_list

    # --------------------------------------------------------------
    def merge_dicts(self, new_dict: dict[str,list[str]], legacy_dict: dict[str,list[str]]) -> dict[str,list[str]]:
        """Merge dictionaries with column lists from multiple tables.
        Column lists with the same key are combined into single list,
        The order of the elements in new_dict keeps minimum distance to the element order in the legacy_dict.
        
        Args:
            new_dict: Incoming dict with table lists.
            legacy_dict: Existing dict with table lists.
            
        Returns:
            Merged dictionary.
        """
        
        legacy_dict_copy = legacy_dict.copy()
        # merge keys that are both in the legacy and the new column list
        for key in new_dict.keys():
            if key in legacy_dict:
                new_dict[key] = self.merge_lists(new_list=new_dict[key], legacy_list=legacy_dict[key])
                legacy_dict_copy.pop(key, None)
                
        # add any remaining table column list, not present in the new dict, to the result dict.
        if legacy_dict_copy:
            new_dict.update(legacy_dict_copy)
            
        return new_dict

    # --------------------------------------------------------------
    def update_reference_data(self, new_data_df: dict[str, pd.DataFrame], file: str) -> None:
        """Update reference data with new data from a processed metadata file, maintaining PK/FK integrity.
        
        Args:
            new_data_df (dict[str,pd.DataFrame]): Dictionary with the DataFrames containing various tables.
            file (str): The metadata file being processed.
            
        Returns:
            None
        """
        pk_mappings, update_dfs, add_dfs = self.df_split_update(new_data_df, file)
        
        self._update_primary_keys_for_new_rows(pk_mappings, add_dfs, file)
        
        self._update_foreign_keys(pk_mappings, update_dfs, add_dfs)
        
        self._apply_updates_to_reference_data(update_dfs, add_dfs, file)

    # --------------------------------------------------------------
    def df_split_update(self, new_data_df: dict[str, pd.DataFrame], file: str) -> tuple[dict, dict, dict]:
        """Identify existing/new rows, build primary key mappings and update primary keys of existing rows.
        
        Args:
            new_data_df: Dictionary with DataFrames containing various tables.
            
        Returns:
            tuple: (pk_mappings, update_dfs, add_dfs)
                - pk_mappings: Dictionary mapping old PKs to new PKs by table
                - update_dfs: Dictionary of DataFrames with rows to update
                - add_dfs: Dictionary of DataFrames with rows to add
        """
        pk_mappings = {}  # table -> {old_pk -> new_pk}
        update_dfs = {}   # table -> DataFrame with rows to update
        add_dfs = {}      # table -> DataFrame with rows to add
        
        for table, df in new_data_df.items():
            # Skip empty tables
            if df.empty or table not in self.ref_df:
                continue
                
            # Find common indexes between new data and reference data
            common_indexes = df.index.intersection(self.ref_df[table].index)
            
            if not common_indexes.empty:
                # Rows to update (existing in both dataframes)
                update_df = df.loc[common_indexes].copy()
                
                # Rows to add (only in new data)
                add_df = df.drop(common_indexes).copy()
                
                # Store split dataframes into the corresponding dictionaries
                update_dfs[table] = update_df
                if not add_df.empty:
                    add_dfs[table] = add_df
                    
                # Check if this table has primary key definition in the association dictionary
                if table in self.config.table_associations and cm.PK_KEY in self.config.table_associations[table]:
                    
                    pk_column = self.config.table_associations[table][cm.PK_KEY][cm.NAME_KEY]
                    
                    # Create mapping for primary keys that need to be updated
                    pk_mappings[table] = {}
                    
                    for idx in common_indexes:
                        old_pk = df.loc[idx, pk_column]
                        new_pk = self.ref_df[table].loc[idx, pk_column]
                        
                        if old_pk != new_pk:
                            logging.debug(f"Updating PK for {table} at index {idx}: {old_pk} -> {new_pk}, for data file {file}")  
                            pk_mappings[table][old_pk] = new_pk
                            # Update the PK in the update dataframe
                            update_dfs[table].loc[idx, pk_column] = new_pk
            else:
                # All rows are new
                add_dfs[table] = df.copy()
        
        return pk_mappings, update_dfs, add_dfs

    # --------------------------------------------------------------
    def _update_primary_keys_for_new_rows(self, pk_mappings: dict[str, dict[str, str]], df: dict[str,pd.DataFrame], file: str) -> None:
        """Update the primary key when relative association is used.
        
        Args:
            pk_mappings (dict[str, dict[str, str]]): Dictionary with primary key mappings for each table.
            df (dict[str,pd.DataFrame]): Dictionary with the DataFrames containing various tables.
            file (str): The metadata file being processed.
            
        Returns:
            None
        """
        for primary_table, association in self.config.table_associations.items():

            try:
                # if PK is int, get the minimum value of the PK column as offset to be discounted
                # and add the corresponding next_pk_counter value
                association_pk = association[cm.PK_KEY]
                
                # If keys are absolute, skip the processing
                if not association_pk[cm.RELATIVE_VALUE_KEY]:
                    continue
                
                # Initialize the primary_table entry in pk_mod_primary_table if it doesn't exist
                if primary_table not in pk_mappings:
                    pk_mappings[primary_table] = {}

                # If PK is relative to the file and defined as a sequential int number
                if association_pk[cm.INT_TYPE_KEY]:
                    
                    # test if type of df[primary_table][association_pk[cm.NAME_KEY]] is int, if not, convert to int
                    if not pd.api.types.is_integer_dtype(df[primary_table][association_pk[cm.NAME_KEY]]):
                        df[primary_table][association_pk[cm.NAME_KEY]] = df[primary_table][association_pk[cm.NAME_KEY]].astype(int)

                    distinct_pks = df[primary_table][association_pk[cm.NAME_KEY]].drop_duplicates().tolist()
                    min_value = df[primary_table][association_pk[cm.NAME_KEY]].min()
                    max_value = df[primary_table][association_pk[cm.NAME_KEY]].max()
                    
                    offset = self.next_pk_counter[primary_table] - min_value
                        
                    # if the PK is relative and an int, add the next_pk_counter value to the minimum value
                    df[primary_table][association_pk[cm.NAME_KEY]] = df[primary_table][association_pk[cm.NAME_KEY]] + offset
                        
                    # update the next_pk_counter value for the primary_table
                    self.next_pk_counter[primary_table] += max_value
                    
                    self.pk_int_offset[primary_table] = offset
                    
                    # update pk_mappings dict with values from distinct_pks with added offset
                    pk_mappings[primary_table].update({original_pk: original_pk + offset for original_pk in distinct_pks})
                    
                
                # else, if PK is relative but not a sequential int, generate a new UI
                else:
                    # Get the primary key column name
                    pk_column = association_pk[cm.NAME_KEY]
                    
                    # Extract original primary key values
                    original_pks = df[primary_table][pk_column].tolist()
                    
                    # Create a list of IDs sequentially counting from self.next_pk_counter[primary_table] until self.next_pk_counter[primary_table] + len(original_pks)
                    new_pks = list(range(self.next_pk_counter[primary_table], self.next_pk_counter[primary_table] + len(original_pks)))
                                        
                    # Store mapping of original to new primary keys
                    pk_mappings[primary_table].update({original_pk: new_pk for original_pk, new_pk in zip(original_pks, new_pks)})
                    
                    # Replace the primary key column values with the new keys
                    df[primary_table][pk_column] = df[primary_table][pk_column].map(pk_mappings[primary_table])
                    
                    # update self.next_pk_counter[primary_table]
                    self.next_pk_counter[primary_table] += len(original_pks)
                        
            except KeyError as e:
                self.log.debug(f"Key error in table {primary_table}, file {file}. {e}.")
                continue
            except TypeError as e:
                self.log.debug(f"Type error in table {primary_table}, file {file}. {e}.")
                continue

    # --------------------------------------------------------------
    def _update_foreign_keys(self, pk_mappings: dict, update_dfs: dict, add_dfs: dict) -> None:
        """Update foreign keys in existing rows based on primary key mappings.
        
        Args:
            pk_mappings: Dictionary mapping old PKs to new PKs by table
            update_dfs: Dictionary of DataFrames with rows to update
            add_dfs: Dictionary of DataFrames with rows to add
            
        Returns:
            None
        """
        for table, mappings in pk_mappings.items():
            if not mappings:  # Skip if no mappings for this table
                continue
                
            # Get the list of tables that reference this table
            pk_info = self.config.table_associations[table][cm.PK_KEY]
            if cm.REFERENCED_BY_KEY not in pk_info:
                continue
                
            referenced_by = pk_info[cm.REFERENCED_BY_KEY]
            
            # Update foreign keys in all referencing tables (update set)
            for ref_table in referenced_by:
                fk_column = self.config.table_associations[ref_table][cm.FK_KEY][table]
                if ref_table in update_dfs:
                    update_dfs[ref_table][fk_column] = update_dfs[ref_table][fk_column].map(
                    lambda x: mappings.get(x, x)
                    )
                elif ref_table in add_dfs:
                    add_dfs[ref_table][fk_column] = add_dfs[ref_table][fk_column].map(
                    lambda x: mappings.get(x, x)
                    )

    # --------------------------------------------------------------
    def _apply_updates_to_reference_data(self, update_dfs: dict, add_dfs: dict, file: str) -> None:
        """Apply updates to reference data from both updated and new rows.
        
        Args:
            update_dfs: Dictionary of DataFrames with rows to update
            add_dfs: Dictionary of DataFrames with rows to add
            file: The metadata file being processed
            
        Returns:
            None
        """
        tables_processed = set(update_dfs.keys()) | set(add_dfs.keys())
        
        for table in tables_processed:
            if table in update_dfs:
                # Update existing rows
                self.ref_df[table].update(update_dfs[table])
            
            if table in add_dfs:
                # Add new rows
                self.ref_df[table] = pd.concat([self.ref_df[table], add_dfs[table]])
            
            # Update column tracking for data filenames
            if len(self.config.columns_data_filenames.get(table, [])) > 1:
                self.ref_cols[table].append(self.config.columns_data_filenames[table])
            
            self.log.info(f"Reference data updated for table {table} with data from file: {file}")

    # --------------------------------------------------------------
    def _add_filename_column(self, df: pd.DataFrame, table: str, file: str) -> pd.DataFrame:
        """Complement the data in the reference DataFrame with metadata extracted from the filename and the file itself.
        
        Args:
            df : Dataframe into the new column with filename may be created.
            table (str): Name of the table to be used as defined in the config file.
            file (str): The metadata file being processed.
            
        Returns:
            pd.DataFrame: Updated DataFrame with the new data.
        """
        
        if self.config.add_filename is None:
            self.log.debug("No filename column required in the config file.")
            return df
        
        if table in self.config.add_filename.keys():
            new_column_name = self.config.add_filename[table]
            basename = os.path.basename(file)
            
            if df.empty:
                # Create a new DataFrame with one row for empty DataFrames
                df = pd.DataFrame({new_column_name: [basename]})
            else:
                # Use assign for non-empty DataFrames
                df = df.assign(**{new_column_name: basename})
        else:
            self.log.debug(f"No filename column required in table `{table}`.")
        
        return df
    
    # --------------------------------------------------------------
    def _apply_filename_data_processing_rules(self, key:str, value:str) -> str:
        """Apply the filename data processing rules to the value.
        
        Args:
            key (str): Key of the filename data.
            value (str): Value of the filename data.
            
        Returns:
            str: Processed value.
        """
        
        if key in self.config.filename_data_processing_rules:

            for rule in self.config.filename_data_processing_rules[key].keys():
                match rule:
                    case cm.REPLACE_KEY:
                        for replacement in self.config.filename_data_processing_rules[key][cm.REPLACE_KEY]:
                            old_char = replacement[cm.OLD_KEY]
                            new_char = replacement[cm.NEW_KEY]
                            value = value.replace(old_char, new_char)
                            
                    case cm.ADD_SUFFIX_KEY:
                        suffix = self.config.filename_data_processing_rules[key][cm.ADD_SUFFIX_KEY]
                        value = f"{value}{suffix}"
                        
                    case cm.ADD_PREFIX_KEY:
                        prefix = self.config.filename_data_processing_rules[key][cm.ADD_PREFIX_KEY]
                        value = f"{prefix}{value}"
                    case _:
                        self.log.error(f"Unknown rule '{rule}' in filename data processing rules. Ignoring")
                
        return value
    
    # --------------------------------------------------------------
    def _add_filename_data(self, df: pd.DataFrame, table: str, file: str) -> pd.DataFrame:
        """Complement the data with metadata extracted from the filename using regex groups.
        
        Args:
            df: DataFrame into which the filename data may be added.
            table: Name of the table to be used as defined in the config file.
            file: The metadata file being processed
            
        Returns:
            pd.DataFrame: Updated DataFrame with the filename data
        """
        
        if self.config.filename_data_format is None:
            self.log.debug("No filename data format defined in the config file.")
            return df
        
        basename = os.path.basename(file)
        
        if table in self.config.filename_data_format.keys():
            # Get regex pattern for this table (already a compiled re.Pattern)
            re_formatting = self.config.filename_data_format[table]
            
            # Extract data from filename using compiled regex pattern
            match_result = re_formatting.match(basename)
            if not match_result:
                self.log.debug(f"Filename '{basename}' doesn't match pattern for table '{table}'")
                return df
                
            filename_data = match_result.groupdict()
            
            if not filename_data:
                self.log.debug(f"No named groups matched in filename '{basename}' for table '{table}'")
                return df
            
            # Assign each extracted group as a new column for all rows in the DataFrame
            # Prepare a dict with processed filename data
            processed_data = {key: self._apply_filename_data_processing_rules(key=key, value=value) for key, value in filename_data.items()}
            if df.empty:
                df = pd.DataFrame([processed_data])
            else:
                df = df.assign(**processed_data)
                
            self.log.debug(f"Added {len(filename_data)} metadata fields from filename to table '{table}'")
        
        else:
            self.log.debug(f"No filename data format defined for table '{table}'. No metadata added from filename.")
                
        return df
    
    # --------------------------------------------------------------
    def read_reference_df(self) -> tuple[dict[str,pd.DataFrame], dict[str,list]]:
        """Read the most recently updated reference DataFrame from the list of catalog files.

        Args: None

        Returns:
            dict[str,pd.DataFrame]: Dictionary with the DataFrames containing various tables.
            dict[str,list]: Dictionary with the lists of columns for each table.
        """
        
        # find the newest file in the list of catalog files
        latest_time:float = 0.0
        latest_file:str = None
        ref_df: dict[str, pd.DataFrame] = {}
        ref_cols: dict[str, list] = {}
        
        for file in self.config.catalog_files:
            if os.path.isfile(file):
                if os.path.getmtime(file) > latest_time:
                    latest_time = os.path.getmtime(file)
                    latest_file = file
        
        if latest_file:
            self.log.info(f"Reference data loaded from file: {latest_file}")
            ref_df, ref_cols = self.read_metadata(  file=latest_file,
                                                    table=self.config.default_worksheet_key)
            
        if not latest_file or not ref_df:
            self.log.warning("No reference data found. Starting with a blank reference.")
            ref_df = {key: pd.DataFrame() for key in self.config.table_names}
            ref_cols = {key: [] for key in self.config.table_names}

        return ref_df, ref_cols

    # --------------------------------------------------------------
    def process_metadata_files(self,  metadata_files: dict[str,set[str]]) -> None:
        """Process a set of xlsx files and update the reference data file.

        Args:
            metadata_files (dict[str,set[str]]): Dictionary of xlsx files to process, keyed by table name.
            config (Config): Configuration object.
            log (logging.Logger): Logger object.
            
        Returns: None            
        """
        
        files_to_move_to_store = []

        for table, files in metadata_files.items():
            for file in files:
                new_data_df, column_in = self.read_metadata(file=file, table=table)

                # If data was loaded, put the file in the list to be moved to store, otherwise may move it to trash
                if new_data_df:
                    files_to_move_to_store.append(file)
                elif self.config.discard_invalid_data_files:
                    self.file.trash_it(file=file, overwrite=self.config.trash_data_overwrite)
                    continue

                # Compute the new column order for the reference DataFrame
                self.ref_cols = self.merge_dicts(new_dict=column_in, legacy_dict=self.ref_cols)
                            
                # Update reference data with new data from the file
                self.update_reference_data(new_data_df=new_data_df, file=file)

        if files_to_move_to_store:
            if self.persist_reference():
                self.file.move_to_store(files_to_move_to_store)

                # Reset set of data files to ignore, since the reference data has been updated
                self.data_files_to_ignore = { k :set() for k in self.config.data_file_regex.keys() }

    # --------------------------------------------------------------
    def process_data_files(self, files_to_process: dict[str,set[str]]) -> None:
        """Process the set of data files and update the reference metadata file, if necessary.

        Args:
            files_to_process (set[str]): List of pdf files to process.
            reference_df (pd.DataFrame): Reference data DataFrame.
            log (logging.Logger): Logger object.
            
        Returns: None
        """
        files_not_counted = {}
        
        for target_folder_key, file_set in files_to_process.items():
        
            if file_set is None or not file_set:
                continue
            
            self.log.info(f"Processing {len(file_set)} data files")
            
            files_found_in_ref = set()

            for file in file_set:
                
                for table in self.ref_df.keys():
                    
                    data_file_column = self.config.columns_data_filenames[table]
                    
                    for column in data_file_column:
                        match = self.ref_df[table][self.ref_df[table][column].str.contains(os.path.basename(file))]
                    
                        if not match.empty:
                            for status_column in self.config.columns_data_published[table]:
                                self.ref_df[table].loc[match.index, status_column] = "True"
                                files_found_in_ref.add(file)
            
            files_not_counted = file_set - files_found_in_ref
            
            if files_not_counted:
                self.data_files_to_ignore[target_folder_key] = files_not_counted
                self.log.warning(f"Not all data files were considered. Leaving {len(files_not_counted)} in TEMP folder.")
            
            if files_found_in_ref:
                if self.persist_reference():
                    if self.file.publish_data_file(files_found_in_ref, target_folder_key):
                        self.file.remove_file_list(files_found_in_ref)

    # --------------------------------------------------------------
    def persist_reference(self) -> bool:
        """Persist the reference DataFrame to the catalog file.

        Args: None
        
        Returns:
            bool: True if the reference data is saved successfully
        """

        for table in self.ref_df.keys():
            # sort the reference DataFrame by the columns defined in the config file
            self.ref_df[table] = self.ref_df[table].sort_values(by=self.config.rows_sort_by[table], ascending=True)
        
            # get selected columns in the defined order
            self.ref_df[table] = self.ref_df[table][self.ref_cols[table]]
        
        # loop through the target catalog files and save the reference data, 
        # ensuring that at least one file is saved successfully before returning True
        # TODO TRANSLATE SHEET NAMES FOR SAVING TO EXCEL
        save_at_least_one = False
        for catalog_file in self.config.catalog_files:
            try:
                with pd.ExcelWriter(catalog_file, engine='openpyxl') as writer:
                    # Write each table to a separate sheet in the Excel file
                    for table in self.ref_df.keys():
                        self.ref_df[table].to_excel(writer, sheet_name=self.config.table_names[table], index=False)

                self.log.info(f"Reference data file updated: {catalog_file}")
                save_at_least_one = True
            except Exception as e:
                self.log.error(f"Error saving reference data: {e}")
        
        if not save_at_least_one:
            self.log.error("No reference data file was saved. No changes were made.")
        
        return save_at_least_one
        

# --------------------------------------------------------------