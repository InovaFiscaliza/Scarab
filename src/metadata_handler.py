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
import uuid
import base58
import json

# ---------------------------------------------------------------
# Constants used only in this module and not affected by the config file
SCARAB_POST_ORDER_COLUMN = "Scarab Post Order"
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
        self.data_files_to_ignore : set[str] = set()
        """List of data files that were processed but not found in the reference data. To be processed only if the reference data is updated."""
        
        self.unique_id : str = base58.b58encode(uuid.uuid4().bytes).decode('utf-8')
        """Unique identifier for the in class column naming."""
        self.index_column : str = f"{INDEX_COLUMN_PREFIX}{self.unique_id}"
        """Index column name. Used to concatenate the values of the columns defined as keys."""
        self.data_file_column : str = f"{DATA_FILE_COLUMN_PREFIX}{self.unique_id}"
        """Data file control column name. Used to concatenate the filenames of the data files when multiple columns are defined."""
        self.post_order_column : str = SCARAB_POST_ORDER_COLUMN
        """Post order column name. Used to keep ordering of the rows in the DataFrame."""
        if not self.config.rows_sort_by:
            self.config.rows_sort_by = [self.post_order_column]
        
        self.ordering_index : int = 0
        """Index user for sequentially ordering rows in the DataFrame if no ordering column is defined."""
        
        df, col = self.read_reference_df()
        
        self.ref_df : dict[str:pd.DataFrame] = df
        """Dictionary with various dataframes containing the reference metadata in various tables."""
        self.ref_cols : dict[str:list[str]] = col
        """Dictionary with list of columns in in each reference DataFrame."""
        
        self.next_pk_counter : dict[str, int] = self.initialize_next_pk_counter()
        """ Dictionary with initial number to be used as primary keys in each table. The key is the table name and the value is the number of free primary keys. """
        self.pk_mod_table : dict[str,dict[str:str]] = {}
        """ Dictionary with the table name and key associated with the primary key in relative (in file) indexing and absolute (in reference data) indexing. """
        
    # --------------------------------------------------------------
    def initialize_next_pk_counter(self) -> dict[str, int]:
        """Initialize the free primary key counter for each table in the reference data.

        Returns:
            dict[str, int]: Dictionary with the initial number to be used as primary keys in each table.
        """
        
        next_pk_counter = {}
        for table in self.ref_df.keys():
            # get the maximum value of the primary key column in the reference DataFrame
            try:
                pk_column = self.config.tables_associations[table]["PK"]["name"]
            except KeyError:
                self.log.debug(f"Table {table} does not have a primary key column defined in the config file.")
            
            try:
                max_pk = self.ref_df[table][pk_column].max()
            except Exception as e:
                self.log.warning(f"Could not getting maximum primary key value for table {table}: {e}")
                max_pk = 0
            
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
    def create_index(self, df: pd.DataFrame, table_name: str, file: str) -> pd.DataFrame:
        """Create an index for the DataFrame based on the columns defined in the config file. The index is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the index column created.
        """
        
        columns = self.config.columns_key[table_name]
        if not columns:
            self.log.debug(f"No key columns defined for table {table_name} to use for processing file {file}")
            return df
        try:
            # create a column to be used as index, merging the columns in index_column list
            df[self.index_column] = df[columns].astype(str).agg('-'.join, axis=1)
            
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
            if not df.empty:
                self.log.error(f"Key error in dataframe from file {file}, table {table_name}: {e}")
            return pd.DataFrame()
        except Exception as e:
            self.log.error(f"Error creating index in dataframe from file {file}, table {table_name}: {e}")
            return pd.DataFrame()
        
        return df

    # --------------------------------------------------------------
    def sort_dataframe(self, df: pd.DataFrame, table_name: str, file: str) -> pd.DataFrame:
        """Sort the DataFrame by the columns defined in the config file. The index is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the index column created.
        """
        
        df[self.post_order_column] = range(self.ordering_index, self.ordering_index + len(df))
        self.ordering_index += len(df)
        
        try:
            # sort the DataFrame by the columns defined in the config file
            df = df.sort_values(by=self.config.rows_sort_by[table_name], ascending=True)
        except AttributeError as e:
            if df.empty:
                self.log.info(f"No data in file {file}")
            else:
                self.log.error(f"Attribute error in sorting metadata from file {file}, table {table_name}: {e}")
            return pd.DataFrame()
        except KeyError as e:
            if not df.empty:
                self.log.error(f"Key error in sorting metadata from file {file}, table {table_name}: {e}")
            return pd.DataFrame()
        except Exception as e:
            self.log.error(f"Error sorting metadata from file {file}, table {table_name}: {e}")
            return pd.DataFrame()
        
        return df
    # --------------------------------------------------------------
    def create_data_file_control_column(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """Create a column with the filenames of the data files to which the metadata refers to. 
        The column is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.

        Returns:
            pd.DataFrame: DataFrame with the filenames column created.
        """
        
        try:
            # create a column to be used as index, merging the columns in index_column list
            df[self.data_file_column] = df[self.config.columns_data_filenames[table_name]].astype(str).agg('-'.join, axis=1)
        except ValueError as e:
            self.log.warning(f"No data file column found in {self.config.columns_data_filenames[table_name]}. Error: {e}")
            return df
        except Exception as e:	
            self.log.error(f"Error creating data filenames column: {e}")
            return pd.DataFrame()
        
        # if column self.config.columns_data_published is not present in the reference_df, create it with false string values
        if self.config.columns_data_published[table_name] not in df.columns:
            df[self.config.columns_data_published[table_name]] = pd.Series(dtype='string')
            
        # Replace the Null values in the self.config.columns_data_published column with the string "False"
        df[self.config.columns_data_published[table_name]] = df[self.config.columns_data_published[table_name]].fillna("False")
                    
        df[self.config.columns_data_published[table_name]] = (
            df[self.config.columns_data_published[table_name]]
            .replace(self.config.null_string_values, "False")
        )
        
        return df
    
    # --------------------------------------------------------------
    def process_table(self, df: pd.DataFrame, table_name: str, file: str) -> tuple[pd.DataFrame, list]:
        """Process the DataFrame to create, clean column names and other adjustments.
        Args:
            df (pd.DataFrame): DataFrame to process.
            table_name (str): Name of the table to be used as defined in the config file.
            file (str): File name to be used in the log message.
            
        Returns:
            pd.DataFrame: DataFrame with the data from the Excel file.
            list: List of columns in the DataFrame.
        """
        
        # Remove escaped characters from column names
        df.columns = self.config.limit_character_scope(df.columns.tolist())
        
        df = self.create_index(df=df, table_name=table_name, file=file)
        
        df = self.sort_dataframe(df=df, table_name=table_name, file=file)

        # get the columns from new_data_df
        columns = df.columns.tolist()
                        
        new_df = self.create_data_file_control_column(df=df)

        return new_df, columns

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
    def read_metadata(self, file: str, filetype: str) -> tuple[dict[str:pd.DataFrame], dict[str:list]]:
        """Read an metadata file and return a list of tuples with the DataFrame and the columns in the DataFrame.
        The file can be an Excel file, a CSV file or a JSON file.

        Args:
            file (str): Excel file to read.
            filetype (str): Type of the file to read. Supported types are '.xlsx', '.csv' and '.json'.

        Returns:
            dict[str:pd.DataFrame]: Dictionary with the DataFrames containing various tables.
            dict[str:list]: Dictionary with the lists of columns for each table.
        """
        
        new_data_df = self.config.table_names.copy()
        new_data_columns = self.config.table_names.copy()
        base_key = self.config.DEFAULT_WORKSHEET_NAME_KEY
        default_table_not_loaded =  True
        
        try:
            match filetype:
                case '.xlsx':
                    # Read all worksheets from Excel file
                    excel_file = pd.ExcelFile(file)
                    sheet_names = excel_file.sheet_names
                    
                    # If there are multiple worksheets
                    if len(sheet_names) > 1:
                        self.log.info(f"XLSX file {file} contains multiple worksheets: {sheet_names}")
                        
                        # create a copy of sheet_names to avoid modifying the original list with the for loop
                        sheet_names_copy = sheet_names.copy()
                        
                        # Process each worksheet separately
                        for sheet_name in sheet_names_copy:
                            if sheet_name in new_data_df:
                                # Read the worksheet into a DataFrame
                                sheet_df = excel_file.parse(sheet_name, dtype="string")
                                
                                if sheet_name == self.config.name:
                                    key = self.config.DEFAULT_WORKSHEET_NAME_KEY
                                    default_table_not_loaded = False
                                else:
                                    key = sheet_name
                                
                                # Process the worksheet data
                                new_data_df[key], new_data_columns[key] = self.process_table(
                                    df=sheet_df,
                                    table_name=sheet_name,
                                    file=file
                                )
                            
                                # remove the processed sheet name from the list of new_data_df
                                sheet_names.remove(sheet_name)
                            
                        if len(sheet_names) == 1 and default_table_not_loaded:
                            new_df = excel_file.parse(sheet_names[0], dtype="string")
                            self.config.table_names[base_key] = sheet_names[0]
                    
                    else:
                        try:
                            self.config.table_names[base_key] = sheet_names[0]
                            new_df = excel_file.parse(sheet_names[0], dtype="string")
                            
                        except IndexError as e:
                            self.log.error(f"Error reading sheet names from file {file}: {e}")
                            return pd.DataFrame(), []
                        
                case '.csv':
                    new_df = pd.read_csv(file, dtype="string")
                    
                case '.json':
                    # get data from the json file
                    with open(file, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    
                    # look for each defined table name in the json file and create a corresponding DataFrame
                    for key in new_data_df.keys():
                        if data and key in data:
                            new_df = self.create_dataframe(data[key])

                            new_data_df[key], new_data_columns[key] = self.process_table(   df=new_df,
                                                                                            table_name=key,
                                                                                            file=file)
                            del data[key]
                    
                    # add the remaining data from the json file to the default base_key table
                    if data:
                        new_df = self.create_dataframe(data)
                    
                case _:
                    self.log.error(f"Unsupported metadata file type: {filetype}")
                    
            if default_table_not_loaded:
                new_data_df[base_key], new_data_columns[base_key] = self.process_table( df=new_df,
                                                                                        table_name=base_key,
                                                                                        file=file)
            
            return new_data_df, new_data_columns
            
        except Exception as e:
            self.log.error(f"Error reading metadata file {file}: {e}")
            return pd.DataFrame(), []
        
    # --------------------------------------------------------------
    def valid_data(self, tables: dict[str:pd.DataFrame], file: str) -> bool:
        """Check if the input dataframe is valid with the following tests:
            - If columns are a superset of the minimum required columns.
            - If columns contain the key columns.
            - If key columns contain any non null values.

        Args:
            df (pd.DataFrame): DataFrame to validate.
            file (str): File name to be used in the log message.

        Returns:
            bool: True if the data is valid.
        """
        
        for table, df in tables.items():
            # processing of the original data may remove rows with null values in the key columns, the resulting DataFrame may be empty
            if df.empty and table in self.config.required_tables:
                if table == self.config.DEFAULT_WORKSHEET_NAME_KEY:
                    self.log.warning(f"File '{file}' is empty or has no data in columns defined as keys.")
                self.log.warning(f"File '{file}' is empty or has nor data in columns defined as keys.")
                return False
            
            df_columns = set(df.columns.tolist())
            
            required_columns = set(self.config.columns_in[table])
            key_columns = set(self.config.columns_key[table])
        
            if not required_columns.issubset(df_columns):
                # find which elements from self.config.columns_in are missing in df_columns
                missing_columns = required_columns - df_columns
                self.log.error(f"File '{file}' does not contain the required metadata columns: {missing_columns}")
                return False
                
            if not key_columns.issubset(df_columns):
                missing_columns = key_columns - df_columns
                self.log.error(f"File '{file}' does not contain the required key columns: {missing_columns}")
                return False        
            
        return True

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
    def merge_dicts(self, new_dict: dict[str:[list[str]]], legacy_dict: dict[str:[list[str]]]) -> dict[str:[list[str]]]:
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
    def update_reference_data(self, new_data_df: dict[str:pd.DataFrame], file: str) -> None:
        """Update reference data with new data from a processed metadata file.
        
        Args:
            new_data_df (dict[str:pd.DataFrame]): Dictionary with the DataFrames containing various tables.
            file (str): The metadata file being processed.
            
        Returns:
            None
        """
        # Add column with combined data filenames string column
        for table in new_data_df.keys():
            if len(self.config.columns_data_filenames[table]) > 1:
                self.ref_cols[table].append(self.config.columns_data_filenames[table])
            
            # Update the reference data with the new data where index matches
            self.ref_df[table].update(new_data_df[table])
            
            # Add new_data_df rows where index does not match
            self.ref_df[table] = self.ref_df[table].combine_first(new_data_df[table])
            
            self.log.info(f"Reference data updated for table {table} with data from file: {file}")

    # --------------------------------------------------------------
    def update_pk(self, new_data_df: dict[str:pd.DataFrame], file: str) -> dict[str:pd.DataFrame]:
        """Update the primary key when relative association is used.
        
        Args:
            new_data_df (dict[str:pd.DataFrame]): Dictionary with the DataFrames containing various tables.
            file (str): The metadata file being processed.
            
        Returns:
            None
        """
        
        for table in new_data_df.keys():
            
            try:
                association = self.config.tables_associations[table]
                
                # if PK is int, get the minimum value of the PK column as offset to be discounted
                # and add the corresponding next_pk_counter value
                if association["PK"]["int_type"]:
                    min_value = new_data_df[table][association["PK"]["name"]].min()
                    max_value = new_data_df[table][association["PK"]["name"]].max()
                    
                    offset = self.next_pk_counter[table] - min_value
                        
                    # if the PK is relative and an int, add the next_pk_counter value to the minimum value
                    new_data_df[table][association["PK"]["name"]] = new_data_df[table][association["PK"]["name"]] + offset
                        
                    # update the next_pk_counter value for the table
                    self.next_pk_counter[table] += max_value
                    
                    self.pk_mod_table[table]["offset"] = offset
                
                # else, if PK is relative but not an int, generate a new UI
                else:
                    # Get the primary key column name
                    pk_column = association["PK"]["name"]
                    
                    # Extract original primary key values
                    original_pks = new_data_df[table][pk_column].tolist()
                    
                    # Create a list of unique IDs with the same length as the DataFrame
                    new_pks = [base58.b58encode(uuid.uuid4().bytes).decode('utf-8') for _ in range(len(new_data_df[table]))]
                    
                    # Initialize the table entry in pk_mod_table if it doesn't exist
                    if table not in self.pk_mod_table:
                        self.pk_mod_table[table] = {}
                    
                    # Store mapping of original to new primary keys
                    for i, (original_pk, new_pk) in enumerate(zip(original_pks, new_pks)):
                        self.pk_mod_table[table][original_pk] = new_pk
                    
                    # Replace the primary key column values with the new unique IDs
                    new_data_df[table][pk_column] = new_pks
                        
            except KeyError:
                self.log.debug(f"Missing configuration for table {table} association. Skipping.")
                continue
            
        return new_data_df
    # --------------------------------------------------------------
    def update_table_associations(self, new_data_df: dict[str:pd.DataFrame], file: str) -> dict[str:pd.DataFrame]:
        """Update the table associations in the reference DataFrame with the new data from a processed metadata file.
        
        Args:
            new_data_df (dict[str:pd.DataFrame]): Dictionary with the DataFrames containing various tables.
            file (str): The metadata file being processed.
            
        Returns:
            dict[str:pd.DataFrame]: Updated DataFrame with the new data.
        """
        
        for table in new_data_df.keys():
            
            try:
                association = self.config.tables_associations[table]
                
                # If PK is an integer relative (not absolute to multiple files) to the file
                if association["PK"]["relative_value"]:
                    new_data_df = self.update_pk(new_data_df=new_data_df, file=file)
                    #! TODO: Implement this function
                    new_data_df = self.update_fk(new_data_df=new_data_df, file=file)
            
            except KeyError:
                self.log.debug(f"Missing configuration for table {table} association. Skipping.")
                continue
        
        return new_data_df

    # --------------------------------------------------------------
    def read_reference_df(self) -> tuple[dict[str:pd.DataFrame], dict[str:list]]:
        """Read the most recently updated reference DataFrame from the list of catalog files.

        Args: None

        Returns:
            dict[str:pd.DataFrame]: Dictionary with the DataFrames containing various tables.
            dict[str:list]: Dictionary with the lists of columns for each table.
        """
        
        # find the newest file in the list of catalog files
        latest_time:float = 0.0
        latest_file:str = None
        
        for file in self.config.catalog_files:
            if os.path.isfile(file):
                if os.path.getmtime(file) > latest_time:
                    latest_time = os.path.getmtime(file)
                    latest_file = file
        
        if latest_file:
            self.log.info(f"Reference data loaded from file: {latest_file}")
            ref_df, ref_cols = self.read_metadata(  file=latest_file,
                                                    filetype=self.config.catalog_extension)
        else:
            self.log.warning("No reference data found. Starting with a blank reference.")
            ref_df = self.config.table_names.copy()
            ref_cols = self.config.table_names.copy()
            for key in self.config.table_names.items():
                ref_df[key] = pd.DataFrame()
                ref_cols[key] = []

        return ref_df, ref_cols

    # --------------------------------------------------------------
    def process_metadata_files(self,  metadata_files: set[str]) -> None:
        """Process a set of xlsx files and update the reference data file.

        Args:
            metadata_files (set[str]): List of xlsx files to process.
            config (Config): Configuration object.
            log (logging.Logger): Logger object.
            
        Returns: None            
        """
        
        files_to_move = metadata_files.copy()
        
        for file in metadata_files:
            new_data_df, column_in = self.read_metadata(file=file,
                                                        filetype=self.config.metadata_extension)
            
            # test the content of the file
            if not self.valid_data(df=new_data_df, file=file):
                if self.config.discard_invalid_data_files:
                    self.file.trash_it(file=file, overwrite=self.config.trash_data_overwrite)
                    files_to_move.remove(file)
                continue
            
            # Compute the new column order for the reference DataFrame
            self.ref_cols = self.merge_dicts(new_list=column_in, legacy_dict=self.ref_cols)
            
            # update relative associations.
            new_data_df = self.update_table_associations(new_data_df=new_data_df, file=file)
            
            #! TODO: Implement this function
            new_data_df = self.complement_data(new_data_df=new_data_df, file=file)
            
            # Update reference data with new data from the file
            self.update_reference_data(new_data_df=new_data_df, file=file)

        if self.persist_reference():
            self.file.move_to_store(files_to_move)
            
            # Reset set of data files to ignore, since the reference data has been updated
            self.data_files_to_ignore = set()

    # --------------------------------------------------------------
    def process_data_files(self, files_to_process: set[str]) -> None:
        """Process the set of data files and update the reference metadata file, if necessary.

        Args:
            files_to_process (set[str]): List of pdf files to process.
            reference_df (pd.DataFrame): Reference data DataFrame.
            log (logging.Logger): Logger object.
            
        Returns: None
        """
        
        self.log.info(f"Processing {len(files_to_process)} data files")
        
        files_found_in_ref = set()

        for file in files_to_process:
            
            for table in self.ref_df.keys():
                
                data_file_column = self.config.columns_data_filenames[table]
                if data_file_column:
                    # Find the row in the reference DataFrame in which the data_file_column contains filename
                    match = self.ref_df[table][self.ref_df[table][data_file_column].str.contains(os.path.basename(file))]
                    
                    # Set column [self.config.columns_data_published] to "Gotcha!" for any matching rows
                    if not match.empty:
                        self.ref_df[table].loc[match.index, data_file_column] = True
                        files_found_in_ref.add(file)
        
        files_not_counted = files_to_process - files_found_in_ref
        if files_not_counted:
            self.data_files_to_ignore = files_not_counted
            self.log.warning(f"Not all data files were considered. Leaving {len(files_not_counted)} in TEMP folder.")
        
        if files_found_in_ref:                
            if self.persist_reference():
                if self.file.publish_data_file(files_found_in_ref):
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
        save_at_least_one = False
        for catalog_file in self.config.catalog_files:
            try:
                for table in self.ref_df.keys():
                    # if the table is empty, remove it from the reference DataFrame
                    self.ref_df[table].to_excel(catalog_file, sheet_name=table, index=False)

                self.log.info(f"Reference data file updated: {catalog_file}")
                save_at_least_one = True
            except Exception as e:
                self.log.error(f"Error saving reference data: {e}")
        
        if not save_at_least_one:
            self.log.error("No reference data file was saved. No changes were made.")
        
        return save_at_least_one
        

# --------------------------------------------------------------