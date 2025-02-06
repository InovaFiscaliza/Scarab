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
    def read_excel(self, file: str, index_column: str) -> tuple[pd.DataFrame, list]:
        """Read an Excel file and return a DataFrame indexed according to the defined keys

        Args:
            file (str): Excel file to read.
            index_column (str): Column to use as index in the DataFrame.

        Returns:
            pd.DataFrame: DataFrame with the data from the Excel file.
            list: List of columns in the DataFrame.
        """
        
        try:
            df_from_file = pd.read_excel(file, dtype="string")
        except Exception as e:
            self.log.error(f"Error reading Excel file {file}: {e}")
            return pd.DataFrame()
        
        # get the columns from df_from_file
        columns = df_from_file.columns.tolist()
        
        try:
            df_from_file.set_index(index_column, inplace=True)
        except Exception as e:
            self.log.error(f"Error setting index in reference data: {e}")
            pass

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
        
        # add the index column to the list of columns, such that it can be compared to the config file definition of required columns
        df_columns.append(df.index.name)

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
    def process_metadata_files(self,  metadata_files: list[str]) -> pd.DataFrame:
        """Process the list of xlsx files and update the reference data file.

        Args:
             metadata_files (list[str]): List of xlsx files to process.
            config (Config): Configuration object.
            log (logging.Logger): Logger object.
            
        Returns:
            pd.DataFrame: Updated reference DataFrame.
        """
        
        reference_df,columns_out = self.read_reference_df()
        
        for file in metadata_files:
            new_data_df, _ = self.read_excel(   file=file,
                                                index_column=self.config.columns_key)

            if not self.valid_data(new_data_df):
                self.file.trash_it(file=file, overwrite=self.config.trash_data_overwrite)
                continue
            
            # update the reference data with the new data where index matches
            reference_df.update(new_data_df)
            
            # add new_data_df rows where index does not match
            reference_df = reference_df.combine_first(new_data_df)
            
            self.persist_reference(reference_df, columns_out)
            
            self.file.move_to_store(file)


    # --------------------------------------------------------------
    def process_data_files(self, files_to_process: list[str]) -> None:
        """Process the list of pdf files and update the reference data file.

        Args:
            files_to_process (list[str]): List of pdf files to process.
            reference_df (pd.DataFrame): Reference data DataFrame.
            log (logging.Logger): Logger object.
        """
            
        reference_df, columns_out = self.read_reference_df()
        
        for item in files_to_process:
            filename = os.path.basename(item)

            # Change the dataframe column data type to numeric, since excel_read was used forcing type to string to avoid corrupting data from columns that do appear to have a different data type.
            reference_df[self.config.columns_data_published] = pd.to_numeric(reference_df[self.config.columns_data_published], errors='coerce')
            
            # Set to value 1 the column data_published for the row where the filename is found
            reference_df.loc[reference_df[self.config.columns_data_filenames].str.contains(filename, na=False), self.config.columns_data_published] = 1
            
            if self.file.publish_data_file(item):
                self.persist_reference(reference_df=reference_df, columns_out=columns_out)
            else:
                # if file is not present in the reference_df, just do nothing and wait for it to appear later.
                self.log.info(f"{filename} not found in the metadata catalog.")
                    
    # --------------------------------------------------------------
    def persist_reference(self, reference_df: pd.DataFrame, columns_out: list) -> None:
        """Persist the reference DataFrame to the catalog file.

        Args:
            reference_df (pd.DataFrame): The reference DataFrame to be saved.
        """

        # Make a copy of the DataFrame to avoid modifying the original
        reference_df = reference_df.copy()
        
        # change index column to a regular column so it is exported to the Excel file
        reference_df.reset_index(inplace=True)
        
        # reorder columns to match order defined the config file as columns_out_order
        reference_df = reference_df[columns_out]
        
        for catalog_file in self.config.catalog_files:
            try:
                reference_df.to_excel(catalog_file, index=False)
                self.log.info(f"Reference data file updated: {catalog_file}")
            except Exception as e:
                self.log.error(f"Error saving reference data: {e}")