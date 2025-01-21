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

import os
import logging

import pandas as pd

# --------------------------------------------------------------
class DataHandler:

    def __init__(self, config: cm.Config, log: logging.Logger) -> None:
        """Initialize the FileHandler object with the configuration and self.log.er objects.

        Args:
            config (cm.Config): Configuration object.
            self.log.(lm.Logger): self.log.er object.
        """
        self.config = config
        self.log = log
        
        self.file = fm.FileHandler(config, log)
        

    # --------------------------------------------------------------
    def read_excel(self, file: str) -> pd.DataFrame:
        """Read an Excel file and return a DataFrame indexed according to the defined keys

        Args:
            file (str): Excel file to read.

        Returns:
            pd.DataFrame: DataFrame with the Excel data.
        """
        
        try:
            df_from_file = pd.read_excel(file)
        except Exception as e:
            self.log.error(f"Error reading Excel file {file}: {e}")
            return pd.DataFrame()
        
        try:
            df_from_file.set_index(self.config.columns_key, inplace=True)
        except Exception as e:
            self.log.error(f"Error setting index in reference data: {e}")
            pass

        return df_from_file

    # --------------------------------------------------------------
    def valid_data(self, df: pd.DataFrame) -> bool:
        """Validate the data in the DataFrame.

        Args:
            df (pd.DataFrame): DataFrame to validate.

        Returns:
            bool: True if the data is valid.
        """
        
        df_columns = df.columns.tolist()
        df_columns.append(df.index.name)

        if sorted(df_columns) != self.config.columns_in:
            return False
        
        return True

    # --------------------------------------------------------------
    def process_metadata_files(self, metadata_to_process: list[str]) -> pd.DataFrame:
        """Process the list of xlsx files and update the reference data file.

        Args:
            metadata_to_process (list[str]): List of xlsx files to process.
            config (Config): Configuration object.
            log (logging.Logger): Logger object.
        """
        
        
        reference_df = self.read_excel(self.config.catalog_file)
        
        for file in metadata_to_process:
            new_data_df = self.read_excel(file)

            if not self.valid_data(new_data_df):
                self.file.trash_it(file, overwrite_trash=self.config.data_overwrite)
                continue
            
            # update the reference data with the new data where index matches
            reference_df.update(new_data_df)
            
            # add new_data_df rows where index does not match
            reference_df = reference_df.combine_first(new_data_df)
            
            self.persist_reference(reference_df)
            
            self.file.move_to_store(file)

    # --------------------------------------------------------------
    def process_raw_files(self, raw_to_process: list[str]) -> None:
        """Process the list of pdf files and update the reference data file.

        Args:
            raw_to_process (list[str]): List of pdf files to process.
            reference_df (pd.DataFrame): Reference data DataFrame.
            log (logging.Logger): Logger object.
        """
            
        reference_df = self.read_excel(self.config.catalog_file)
        
        for item in raw_to_process:
            filename = os.path.basename(item)
            if filename in reference_df.index:
                reference_df.at[filename, "status_screenshot"] = 1
                if self.file.publish_raw(item):
                    self.persist_reference(reference_df)
                
            else:
                # if file is not present in the reference_df, just do nothing and wait for it to appear later.
                self.log.info(f"{filename} not found in the reference data.")

        
    # --------------------------------------------------------------
    def persist_reference(self, reference_df: pd.DataFrame) -> None:
        """Persist the reference DataFrame to the catalog file.

        Args:
            reference_df (pd.DataFrame): The reference DataFrame to be saved.
        """

        # Make a copy of the DataFrame to avoid modifying the original
        reference_df = reference_df.copy()
        
        # change index column to a regular column so it is exported to the Excel file
        reference_df.reset_index(inplace=True)
        
        # reorder columns to match order defined the config file as columns_out
        reference_df = reference_df[self.config.columns_out]
        
        try:
            reference_df.to_excel(self.config.catalog_file, index=False)
            self.log.info(f"Reference data file updated: {self.config.catalog_file}")
        except Exception as e:
            self.log.error(f"Error saving reference data: {e}")