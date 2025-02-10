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

        self.unique_id : str = uuid.uuid4().int
        """Unique identifier for the in class column naming."""
        
        df, col = self.read_reference_df()
        
        self.ref_df : pd.DataFrame = df
        """Reference DataFrame with the data from the most recently updated catalog file."""
        self.ref_cols : list = col
        """List of columns in the reference DataFrame."""
        
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
            df_from_file = pd.read_excel(file, dtype="string")
        except Exception as e:
            self.log.error(f"Error reading Excel file {file}: {e}")
            return pd.DataFrame(), []
        
        # get the columns from df_from_file
        columns = df_from_file.columns.tolist()
        
        try:
            # create a column to be used as index, merging the columns in index_column list
            df_from_file[self.unique_id] = df_from_file[index_column].astype(str).agg('-'.join, axis=1)
        
            # set the new column as index
            df_from_file.set_index(self.unique_id, inplace=True)
            #df_from_file.set_index(df_from_file[index_column].astype(str).agg('-'.join, axis=1), inplace=True)
            #df_from_file.index = pd.MultiIndex.from_arrays([df_from_file[col].astype(str) for col in index_column], names=index_column)
        except Exception as e:
            self.log.error(f"Error setting index in reference data: {e}")
            return pd.DataFrame(), []

        return df_from_file, columns

    # --------------------------------------------------------------
    def valid_data(self, df: pd.DataFrame) -> bool:
        """Check if the input table columns are a superset of the minimum required columns.

        Args:
            df (pd.DataFrame): DataFrame to validate.

        Returns:
            bool: True if the data is valid.
        """
        
        df_columns = df.columns.tolist()
        
        return self.config.columns_in.issubset(set(df_columns))


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
        """Merge two lists into a single list, preserving the order of the elements in new_list with minimum distance to the element order in legacy_list.
        
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
            if items_not_in_new:
                self.log.info(f"Items present in the existing list that are not in the new list: {items_not_in_new}")
                
                legacy_order = {item: i for i, item in enumerate(legacy_list)}
                new_order = {item: i for i, item in enumerate(new_list)}
                
                for item in items_not_in_new:
                    
                    keep_neighbor_search = True
                    
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
                            # if neighbor is found in the new list, insert the item in the new list at the same relative position
                            if legacy_list[position] in new_set:
                                position = new_order[legacy_list[position]]+direction
                                merged_list.insert(position, item)
                                keep_neighbor_search = False
                            else:
                                # if moving forward, increase distance to the neighbor and try the other direction
                                if direction == -1:
                                    distance_to_neighbor += 1
                                    direction = 1
                                # if moving backwards, keep the distance and try the other direction
                                else:
                                    direction = -1
                                    
                                position = legacy_order[item] - (distance_to_neighbor*direction)
                        except IndexError:
                            if position < 0:
                                reached_beginning = True
                            else:
                                reached_end = True
                            
                            # if a neighbor is not found in the new list, insert the item at end
                            if reached_beginning and reached_end:
                                merged_list.append(item)
                                keep_neighbor_search = False
        
        return merged_list

    # --------------------------------------------------------------
    def process_metadata_files(self,  metadata_files: list[str]) -> pd.DataFrame:
        """Process the list of xlsx files and update the reference data file.

        Args:
             metadata_files (list[str]): List of xlsx files to process.
            config (Config): Configuration object.
            log (logging.Logger): Logger object.
            
        Returns:
            pd.DataFrame: Updated reference DataFrame.
        """
        
        
        for file in metadata_files:
            new_data_df, column_in = self.read_excel(   file=file,
                                                index_column=self.config.columns_key)
            
            if not self.valid_data(new_data_df):
                if self.config.discard_invalid_data_files:
                    self.file.trash_it(file=file, overwrite=self.config.trash_data_overwrite)
                continue

            self.ref_cols = self.merge_lists(new_list=column_in, legacy_list=self.ref_cols)
            
            # update the reference data with the new data where index matches
            self.ref_df.update(new_data_df)
            
            # add new_data_df rows where index does not match
            self.ref_df = self.ref_df.combine_first(new_data_df)
            
            self.persist_reference()
            
            self.file.move_to_store(file)


    # --------------------------------------------------------------
    def process_data_files(self, files_to_process: list[str]) -> None:
        """Process the list of pdf files and update the reference data file.

        Args:
            files_to_process (list[str]): List of pdf files to process.
            reference_df (pd.DataFrame): Reference data DataFrame.
            log (logging.Logger): Logger object.
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

        # Make a copy of the DataFrame to avoid modifying the original
        # self.ref_df = self.self.ref_df.copy()
        
        # change index column to a regular column so it is exported to the Excel file
        self.ref_df.reset_index(inplace=True)
        
        # reorder columns to match order defined the config file as columns_out_order
        self.ref_df = self.ref_df[self.ref_cols]
        
        for catalog_file in self.config.catalog_files:
            try:
                self.ref_df.to_excel(catalog_file, index=False)
                self.log.info(f"Reference data file updated: {catalog_file}")
            except Exception as e:
                self.log.error(f"Error saving reference data: {e}")