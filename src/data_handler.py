#!/usr/bin/python
"""
Module class that handle file operations for the script.

Args (stdin): ctrl+c will soft stop the process similar to kill command or systemd stop <service>. kill -9 will hard stop.

Returns (stdout): As self.log.messages, if target_screen in self.log.is set to True.

Raises:
    Exception: If any error occurs, the exception is raised with a message describing the error.
"""

import cataloguer_config.py as conf_module
import log_with_logging.py as log_module
import file_handler.py as file_module

import os

import pandas as pd

# --------------------------------------------------------------
class DataHandler:

    def __init__(self, config: conf_module.Config, log: log_module.Logger) -> None:
        """Initialize the FileHandler object with the configuration and self.log.er objects.

        Args:
            config (conf_module.Config): Configuration object.
            self.log.(log_module.Logger): self.log.er object.
        """
        self.config = config
        self.log = log
        

    # --------------------------------------------------------------
    def read_excel(self, file: str) -> pd.DataFrame:
        """Read an Excel file and return a DataFrame.

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
    def process_xlsx_files(self, xlsx_to_process: list[str]) -> pd.DataFrame:
        """Process the list of xlsx files and update the reference data file.

        Args:
            xlsx_to_process (list[str]): List of xlsx files to process.
            config (Config): Configuration object.
            log (logging.Logger): Logger object.
        """
        
        
        reference_df = read_excel(self.config.catalog)
        
        for file in xlsx_to_process:
            new_data_df = read_excel(file)

            if not valid_data(new_data_df):
                trash_it(file, overwrite_trash=self.config.data_overwrite)
                continue
            
            # update the reference data with the new data where index matches
            reference_df.update(new_data_df)
            
            # add new_data_df rows where index does not match
            reference_df = reference_df.combine_first(new_data_df)
            
            persist_reference(reference_df)
            
            move_to_store(file)

    # --------------------------------------------------------------
    def process_pdf_files(self, pdf_to_process: list[str]) -> None:
        """Process the list of pdf files and update the reference data file.

        Args:
            pdf_to_process (list[str]): List of pdf files to process.
            reference_df (pd.DataFrame): Reference data DataFrame.
            log (logging.Logger): Logger object.
        """
            
        reference_df = read_excel(self.config.catalog)
        
        for item in pdf_to_process:
            filename = os.path.basename(item)
            if filename in reference_df.index:
                reference_df.at[filename, "status_screenshot"] = 1
                if publish_raw(item):
                    persist_reference(reference_df)
                
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
            reference_df.to_excel(self.config.catalog, index=False)
            self.log.info(f"Reference data file updated: {self.config.catalog}")
        except Exception as e:
            self.log.error(f"Error saving reference data: {e}")