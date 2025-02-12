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

        self.unique_id : str = base58.b58encode(uuid.uuid4().bytes).decode('utf-8')
        """Unique identifier for the in class column naming."""
        
        df, col = self.read_reference_df()
        
        self.ref_df : pd.DataFrame = df
        """Reference DataFrame with the data from the most recently updated catalog file."""
        self.ref_cols : list = col
        """List of columns in the reference DataFrame."""

    # --------------------------------------------------------------
    def drop_na(self, df: pd.DataFrame, file: str) -> pd.DataFrame:
        """Drop rows from the DataFrame where the self.unique_id column has a null value in any variant form, including NA, NaN, strings such as '<NA>', 'NA', 'N/A', 'None', 'null' and empty strings.

        Args:
            df (pd.DataFrame): DataFrame to process.
            file (str): File name to be used in the log message.

        Returns:
            pd.DataFrame: DataFrame with the rows where the self.unique_id column is not null.
        """
        
        # store the number of rows in the dataframe
        rows_before = df.shape[0]
        
        na_strings = ['<NA>', 'NA', 'N/A', 'None', 'null', '']
        
        df = df[~df[self.unique_id].isin(na_strings)]
        
        df = df.dropna(subset=[self.unique_id])
        
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
    def read_excel(self, file: str, index_column: list) -> tuple[pd.DataFrame, list]:
        """Read an Excel file and return a DataFrame indexed according to the defined keys

        Args:
            file (str): Excel file to read.
            index_column (list): Columns to be used as index in the DataFrame.

        Returns:
            pd.DataFrame: DataFrame with the data from the Excel file.
            list: List of columns in the DataFrame.
        """
        
        try:
            new_data_df = pd.read_excel(file, dtype="string")
        except Exception as e:
            self.log.error(f"Error reading Excel file {file}: {e}")
            return pd.DataFrame(), []
        
        # get the columns from new_data_df
        columns = new_data_df.columns.tolist()
        
        try:
            # create a column to be used as index, merging the columns in index_column list
            new_data_df[self.unique_id] = new_data_df[index_column].astype(str).agg('-'.join, axis=1)
            
            # drop rows in which the self.unique_id column has value null
            new_data_df = self.drop_na(df=new_data_df, file=file)
        
            # Identify rows with duplicate self.unique_id values
            duplicate_ids = new_data_df[self.unique_id].duplicated(keep=False)
            duplicate_rows = new_data_df[duplicate_ids]
            
            if not duplicate_rows.empty:
                self.log.warning(f"Duplicated keys in {len(duplicate_rows)} rows in {file}. Rows will be merged")
                # Apply the custom aggregation function to the duplicate rows
                aggregated_rows = duplicate_rows.groupby(self.unique_id).agg(self._custom_agg)
                
                # get the rows that are not duplicated
                unique_rows = new_data_df[~duplicate_ids]
                unique_rows = unique_rows.set_index(self.unique_id)
                
                # Combine the unique rows with the aggregated rows
                new_data_df = pd.concat([unique_rows, aggregated_rows])
            else:
                new_data_df = new_data_df.set_index(self.unique_id)
                
        except Exception as e:
            self.log.error(f"Error creating index: {e}")
            return pd.DataFrame(), []
        
        return new_data_df, columns

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
            self.log.error(f"File '{file}' is empty or has nor data in columns defined as keys.")
            return False
        
        df_columns = df.columns.tolist()
    
        if not self.config.columns_in.issubset(set(df_columns)):
            # find which elements from self.config.columns_in are missing in df_columns
            missing_columns = self.config.columns_in - set(df_columns)
            self.log.error(f"File '{file}' does not contain the required metadata columns: {missing_columns}")
            return False
            
        if not set(self.config.columns_key).issubset(set(df_columns)):
            missing_columns = set(self.config.columns_key) - set(df_columns)
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
        
        try:
            latest_file = max(self.config.catalog_files, key=os.path.getmtime)
        except FileNotFoundError as e:
            for file in self.config.catalog_files:
                # test if file exist
                if os.path.isfile(file):
                    latest_file = file
                    break
                else:
                    self.log.error(f"Reference data file not found: {e}")            
        
        self.log.info(f"Reading reference data from the most recently updated file: {latest_file}")
        
        return self.read_excel(file=latest_file, index_column=self.config.columns_key)

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
            self.log.info(f"Items present in the existing list that are not in the new list: {items_not_in_new}")
            
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
    def process_metadata_files(self,  metadata_files: list[str]) -> None:
        """Process the list of xlsx files and update the reference data file.

        Args:
             metadata_files (list[str]): List of xlsx files to process.
            config (Config): Configuration object.
            log (logging.Logger): Logger object.
            
        Returns: None            
        """
        
        
        for file in metadata_files:
            new_data_df, column_in = self.read_excel(   file=file,
                                                index_column=self.config.columns_key)
            
            # test the content of the file
            if not self.valid_data(df=new_data_df, file=file):
                if self.config.discard_invalid_data_files:
                    self.file.trash_it(file=file, overwrite=self.config.trash_data_overwrite)
                continue
            
            # Compute the new column order for the reference DataFrame
            self.ref_cols = self.merge_lists(new_list=column_in, legacy_list=self.ref_cols)
            
            # Compute the new dataframe            
            # update the reference data with the new data where index matches
            self.ref_df.update(new_data_df)
            
            # add new_data_df rows where index does not match
            self.ref_df = self.ref_df.combine_first(new_data_df)
            
            self.log.info(f"Reference data updated with file: {file}")

        self.persist_reference()
        
        self.file.move_to_store(metadata_files)

    # --------------------------------------------------------------
    def process_data_files(self, files_to_process: list[str]) -> None:
        """Process the list of pdf files and update the reference data file.

        Args:
            files_to_process (list[str]): List of pdf files to process.
            reference_df (pd.DataFrame): Reference data DataFrame.
            log (logging.Logger): Logger object.
            
        Returns: None
        """
            
        for item in files_to_process:
            filename = os.path.basename(item)

            
            # change column [self.config.columns_data_filenames] to string type
            self.ref_df[self.config.columns_data_published] = self.ref_df[self.config.columns_data_published].astype(str)
            
            for data_filename in self.config.columns_data_filenames:
                self.ref_df.loc[self.ref_df[data_filename].str.contains(filename, na=False), self.config.columns_data_published] = "True"

            # Set column [self.config.columns_data_published] to "False" for any remaining NA values
            self.ref_df.loc[:, self.config.columns_data_published] = self.ref_df[self.config.columns_data_published].fillna("False")
            
            if self.file.publish_data_file(item):
                self.persist_reference()
            else:
                # if file is not present in the reference_df, just do nothing and wait for it to appear later.
                self.log.info(f"{filename} not found in the metadata catalog.")
                    
    # --------------------------------------------------------------
    def persist_reference(self) -> None:
        """Persist the reference DataFrame to the catalog file.

        Args: None
        
        Returns: None
        """

        # reorder columns to match order defined the config file as columns_out_order
        self.ref_df = self.ref_df[self.ref_cols]
        
        for catalog_file in self.config.catalog_files:
            try:
                self.ref_df.to_excel(catalog_file, index=False)
                self.log.info(f"Reference data file updated: {catalog_file}")
            except Exception as e:
                self.log.error(f"Error saving reference data: {e}")