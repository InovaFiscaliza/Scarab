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


# Constants
NA_VALUES = ['<NA>', 'NA', 'N/A', 'na', 'Na', 'n/a', 'None', 'null', '', 'pd.NA', 'pd.NaT', 'pd.NA', 'pd.NaT', 'nan', 'NaN', 'NAN', 'missing value', 'Missing Value', 'MISSING VALUE']
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
        """Data file control column name. Used to contatenate the filenames of the data files when multiple columns are defined."""
        self.post_order_column : str = SCARAB_POST_ORDER_COLUMN
        """Post order column name. Used to keep ordering of the rows in the DataFrame."""
        if not self.config.rows_sort_by:
            self.config.rows_sort_by = [self.post_order_column]
        
        self.ordering_index : int = 0
        """Index user for sequentially ordering rows in the DataFrame if no ordering column is defined."""
        
        df, col = self.read_reference_df()
        
        self.ref_df : pd.DataFrame = df
        """Reference DataFrame with the data from the most recently updated catalog file."""
        self.ref_cols : list = col
        """List of columns in the reference DataFrame."""

    # --------------------------------------------------------------
    def drop_na(self, df: pd.DataFrame, file: str) -> pd.DataFrame:
        """Drop rows from the DataFrame where the ID column has a null value in any variant form, including NA, NaN, strings such as '<NA>', 'NA', 'N/A', 'None', 'null' and empty strings.

        Args:
            df (pd.DataFrame): DataFrame to process.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the rows where the ID column is not null.
        """
        
        rows_before = df.shape[0]
        
        df = df[~df[self.index_column].isin(NA_VALUES)]
        
        df = df.dropna(subset=[self.index_column])
        
        removed_rows = rows_before - df.shape[0]
        if removed_rows:
            self.log.info(f"Removed {removed_rows} rows with null values in key column(s) in file '{file}'")
        
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
    def create_index(self, df: pd.DataFrame, file: str) -> pd.DataFrame:
        """Create an index for the DataFrame based on the columns defined in the config file. The index is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the index column created.
        """
        
        try:
            # create a column to be used as index, merging the columns in index_column list
            df[self.index_column] = df[self.config.columns_key].astype(str).agg('-'.join, axis=1)
            
            # drop rows in which the unique_name column has value null
            df = self.drop_na(df=df, file=file)
        
            # Identify rows with duplicate unique_name values
            duplicate_ids = df[self.index_column].duplicated(keep=False)
            duplicate_rows = df[duplicate_ids]
            
            if not duplicate_rows.empty:
                self.log.warning(f"Duplicated keys in {len(duplicate_rows)} rows in {file}. Rows will be merged")
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
                self.log.error(f"Key error in dataframe from file {file}: {e}")
            return pd.DataFrame()
        except Exception as e:
            self.log.error(f"Error creating index in dataframe from file {file}: {e}")
            return pd.DataFrame()
        
        return df

    # --------------------------------------------------------------
    def sort_dataframe(self, df: pd.DataFrame, file: str) -> pd.DataFrame:
        """Sort the DataFrame by the columns defined in the config file. The index is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the index column created.
        """
        
        df[self.post_order_column] = range(self.ordering_index, self.ordering_index + len(df))
        self.ordering_index += len(df)
        
        try:
            # sort the DataFrame by the columns defined in the config file
            df = df.sort_values(by=self.config.rows_sort_by, ascending=True)
        except AttributeError as e:
            if df.empty:
                self.log.info(f"No data in file {file}")
            else:
                self.log.error(f"Attribute error in sorting metadata from file {file}: {e}")
            return pd.DataFrame()
        except KeyError as e:
            if not df.empty:
                self.log.error(f"Key error in sorting metadata from file {file}: {e}")
            return pd.DataFrame()
        except Exception as e:
            self.log.error(f"Error sorting metadata from file {file}: {e}")
            return pd.DataFrame()
        
        return df
    # --------------------------------------------------------------
    def create_data_file_control_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create a column with the filenames of the data files that were used to create the DataFrame. 
        The column is created by concatenating the values of the columns defined in the config file.

        Args:
            df (pd.DataFrame): DataFrame to process.

        Returns:
            pd.DataFrame: DataFrame with the filenames column created.
        """
        
        try:
            # create a column to be used as index, merging the columns in index_column list
            df[self.data_file_column] = df[self.config.columns_data_filenames].astype(str).agg('-'.join, axis=1)
        except ValueError as e:
            self.log.warning(f"No data file column found in {self.config.columns_data_filenames}. Error: {e}")
            return df
        except Exception as e:	
            self.log.error(f"Error creating data filenames column: {e}")
            return pd.DataFrame()
        
        # if column self.config.columns_data_published is not present in the reference_df, create it with false string values
        if self.config.columns_data_published not in df.columns:
            df[self.config.columns_data_published] = pd.Series(dtype='string')
            
        # Replace the Null values in the self.config.columns_data_published column with the string "False"
        df[self.config.columns_data_published] = df[self.config.columns_data_published].fillna("False")
                    
        df[self.config.columns_data_published] = (
            df[self.config.columns_data_published]
            .replace(NA_VALUES, "False")
        )
        
        return df
    
    # --------------------------------------------------------------
    def read_metadata(self, file: str, filetype: str) -> tuple[pd.DataFrame, list]:
        """Read an metadata file and return a DataFrame indexed according to the defined keys

        Args:
            file (str): Excel file to read.
            filetype (str): Type of the file to read. Supported types are '.xlsx', '.csv' and '.json'.

        Returns:
            pd.DataFrame: DataFrame with the data from the Excel file.
            list: List of columns in the DataFrame.
        """
        
        try:
            match filetype:
                case '.xlsx':
                    new_df = pd.read_excel(file, dtype="string")
                case '.csv':
                    new_df = pd.read_csv(file, dtype="string")
                case '.json':
                    with open(file, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                    if isinstance(data, list):
                        new_df = pd.DataFrame(data, dtype="string")
                    else:
                        new_df = pd.DataFrame([data], dtype="string")
                case _:
                    self.log.error(f"Unsupported metadata file type: {filetype}")
        except Exception as e:
            self.log.error(f"Error reading metadata file {file}: {e}")
            return pd.DataFrame(), []
        
        # Remove escaped characters from column names
        new_df.columns = self.config.limit_character_scope(new_df.columns.tolist())
        
        new_df = self.create_index(df=new_df, file=file)
        
        new_df = self.sort_dataframe(df=new_df, file=file)

        # get the columns from new_data_df
        columns = new_df.columns.tolist()
                        
        new_df = self.create_data_file_control_column(df=new_df)

        return new_df, columns

    # --------------------------------------------------------------
    def valid_data(self, df: pd.DataFrame, file: str) -> bool:
        """Check if the input dataframme is valid with the following tests:
            - If columns are a superset of the minimum required columns.
            - If columns contain the key columns.
            - If key columns contain any non null values.

        Args:
            df (pd.DataFrame): DataFrame to validate.
            file (str): File name to be used in the log message.

        Returns:
            bool: True if the data is valid.
        """
        
        # since self.excel_read will remove rows with null values in the key columns, the resulting DataFrame may be empty
        if df.empty:
            self.log.warning(f"File '{file}' is empty or has nor data in columns defined as keys.")
            return False
        
        df_columns = set(df.columns.tolist())
    
        if not self.config.columns_in.issubset(df_columns):
            # find which elements from self.config.columns_in are missing in df_columns
            missing_columns = self.config.columns_in - df_columns
            self.log.error(f"File '{file}' does not contain the required metadata columns: {missing_columns}")
            return False
            
        if not set(self.config.columns_key).issubset(df_columns):
            missing_columns = set(self.config.columns_key) - df_columns
            self.log.error(f"File '{file}' does not contain the required key columns: {missing_columns}")
            return False        
            
        return True


    # --------------------------------------------------------------
    def read_reference_df(self) -> tuple[pd.DataFrame, list]:
        """Read the most recently updated reference DataFrame from the list of catalog files.

        Args: None

        Returns:
            pd.DataFrame: DataFrame with the data from the most recently updated catalog file.
            list: List of columns in the DataFrame.
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
            self.log.warning("No reference data found")
            ref_df, ref_cols = pd.DataFrame(), []

        return ref_df, ref_cols

    # --------------------------------------------------------------
    def merge_lists(self, new_list: list, legacy_list: list) -> list:
        """Merge two lists into a single list, preserving the order of the elements in new_list with minimum distance to the element order in the legacy_list.
        
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
            self.ref_cols = self.merge_lists(new_list=column_in, legacy_list=self.ref_cols)
            
            # add column with combined data filenames string column
            if len(self.config.columns_data_filenames) > 1:
                self.ref_cols.append(self.config.columns_data_filenames)
            
            # update the reference data with the new data where index matches
            self.ref_df.update(new_data_df)
            
            # add new_data_df rows where index does not match
            self.ref_df = self.ref_df.combine_first(new_data_df)
            
            self.log.info(f"Reference data updated with file: {file}")

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
            
            # Find the row in the reference DataFrame in which the data_file_column contains filename
            match = self.ref_df[self.ref_df[self.data_file_column].str.contains(os.path.basename(file))]
            
            # Set column [self.config.columns_data_published] to "Gotcha!" for any matching rows
            if not match.empty:
                self.ref_df.loc[match.index, self.config.columns_data_published] = "True"
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

        # sort the reference DataFrame by the columns defined in the config file
        self.ref_df = self.ref_df.sort_values(by=self.config.rows_sort_by, ascending=True)
        
        # get selected columns in the defined order
        df = self.ref_df[self.ref_cols]
        
        # loop through the target catalog files and save the reference data, 
        # ensuring that at least one file is saved successfully before returning True
        save_at_least_one = False
        for catalog_file in self.config.catalog_files:
            try:
                df.to_excel(catalog_file, index=False)
                self.log.info(f"Reference data file updated: {catalog_file}")
                save_at_least_one = True
            except Exception as e:
                self.log.error(f"Error saving reference data: {e}")
        
        return save_at_least_one
        

# --------------------------------------------------------------