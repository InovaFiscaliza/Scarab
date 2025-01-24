#!/usr/bin/python
"""
Module class that handle file operations for the script.

Args (stdin): ctrl+c will soft stop the process similar to kill command or systemd stop <service>. kill -9 will hard stop.

Returns (stdout): As self.log.messages, if target_screen in self.log.is set to True.

Raises:
    Exception: If any error occurs, the exception is raised with a message describing the error.
"""

# --------------------------------------------------------------
import config_handler as cm

import logging
import os
import shutil
import glob
import pandas as pd
from dataclasses import dataclass
# --------------------------------------------------------------
@dataclass
class FileHandler:
    
    config: cm.Config
    log: logging.Logger
        
    # --------------------------------------------------------------
    def move_to_temp(self, file: str) -> str:
        """Move a file to the temp folder, return the new path, resetting the file timestamp for the current time and self.log.the event.

        Args:
            file (str): File to move.

        Returns:
            str: New path of the file in the temp folder.
        """
        
        filename = os.path.basename(file)
        
        try:
            shutil.move(file, self.config.temp)
            os.utime(os.path.join(self.config.temp, filename))
            self.log.info(f"Moved to {self.config.temp} the file {filename}")
            return os.path.join(self.config.temp, filename)
        except Exception as e:
            self.log.error(f"Error moving {file} to temp folder: {e}")
            return file

    # --------------------------------------------------------------
    def trash_it(self, file: str) -> None:
        """Move file in argument to the trash folder.
        If overwrite is True and file with the same name already exist in the trash folder, it will be overwritten.
        If overwrite is False, any existing file in the trash folder with the same name will be renamed with a timestamp.
        
        Args:
            file (str): File to move to the trash folder.
            
        Returns: None
        
        Raises: None
        """
                
        filename = os.path.basename(file)
        trashed_file = os.path.join(self.config.trash, filename)
        
        if self.config.data_overwrite:
            try:
                os.remove(trashed_file)
            except FileNotFoundError:
                pass                
            except Exception as e:
                self.log.error(f"Error removing {filename} from trash folder: {e}")
        else:
            if os.path.exists(trashed_file):
                trashed_filename, ext = os.path.splitext(filename)
                timestamp = pd.to_datetime("now").strftime('%Y%m%d_%H%M%S')
                trashed_filename = f"{trashed_filename}_{timestamp}{ext}"
                new_trashed_file = os.path.join(self.config.trash, trashed_filename)
                try:
                    os.rename(trashed_file, new_trashed_file)
                    self.log.info(f"Renamed {filename} to {trashed_filename} in trash.")
                except Exception as e:
                    self.log.error(f"Error renaming {filename} in trash folder: {e}")

        try:
            shutil.move(file, self.config.trash)
            os.utime(trashed_file) # force the file timestamp to the current time to avoid being cleaned by the clean process before the clean period is over
            self.log.info(f"Moved to {self.config.trash} the file {filename}")
        except Exception as e:
            self.log.error(f"Error moving {file} to trash folder: {e}")
            
    # --------------------------------------------------------------
    def move_to_store(self, file: str) -> None:
        """Move a file to the store folder, resetting the file timestamp for the current time and self.log.the event.

        Args:
            file (str): File to move to the store folder.
        """
                
        filename = os.path.basename(file)
        
        try:
            shutil.move(file, self.config.store)
            os.utime(os.path.join(self.config.store, filename)) # force the file timestamp to the current time to avoid being cleaned by the clean process before the clean period is over
            self.log.info(f"Moved to {self.config.store} the file {filename}")
        except Exception as e:
            self.log.error(f"Error moving {file} to store folder: {e}")

    # --------------------------------------------------------------
    def publish_raw(self, file: str) -> bool:
        """Publish a file to the raw folder.

        Args:
            file (str): File to publish to the raw folder.
        """
                
        filename = os.path.basename(file)
        
        try:
            shutil.move(file, self.config.raw)
            self.log.info(f"Published to {self.config.raw} the file {filename}")
            return True
        except Exception as e:
            self.log.error(f"Error publishing {file} to raw folder: {e}")
            return False

    # --------------------------------------------------------------
    def sort_files_into_lists(  self, 
                                folder_content: list[str],
                                move: bool = True,
                                catalog_to_process: list[str] = None,
                                raw_to_process: list[str] = None,
                                subfolder: list[str] = None) -> tuple[list[str], list[str], list[str]]:
        """Sort files in the provided list into list of xlsx and pdf files to process and subfolder to remove.

        Args:
            files (list[str]): List of files to sort.
            move (bool): True if required to move files to the temp folder.
            catalog_to_process (list[str]): Existing list of xlsx files to process.
            raw_to_process (list[str]): Existing list of pdf files to process.
            subfolder (list[str]): Existing list of subfolder to remove.

        Returns:
            tuple[list[str], list[str], list[str]]: List of xlsx files to process, list of pdf files to process, list of subfolder to remove.
        """
        
        # Initialize lists if they are None
        if catalog_to_process is None:
            catalog_to_process = []
        if raw_to_process is None:
            raw_to_process = []
        if subfolder is None:
            subfolder = []
            
        for item in folder_content:
            
            # Check if the item is a file
            if os.path.isfile(item):
                
                # Classify the file by extension
                _, ext = os.path.splitext(item)
                match ext:
                    
                    case self.config.catalog_extension:
                        if move:                        
                            item = self.move_to_temp(item)

                        catalog_to_process.append(item)
                        
                    case self.config.raw_extension:
                        if move:
                            item = self.move_to_temp(item)
                            # TODO : CHECK
                        
                        raw_to_process.append(item)
                    
                    case _: 
                        self.trash_it(item)
            else:
                subfolder.append(item)
                
        return catalog_to_process, raw_to_process, subfolder

    # --------------------------------------------------------------
    def remove_unused_subfolder(self, subfolder: list[str]) -> None:
        """Remove empty subfolder from the post folder.

        Args:
            subfolder (list[str]): List of subfolder to remove.
        """
                
        if subfolder:
            for folder in subfolder:
                if not os.listdir(folder):
                    try:
                        os.rmdir(folder)
                        self.log.info(f"Removed folder {folder}")
                    except Exception as e:
                        self.log.warning(f"Error removing folder {folder}: {e}")

    # --------------------------------------------------------------
    def get_files_to_process(self) -> tuple[list[str], list[str]]:
        """Move new files from the post folder to the temp folder and return the list of files to process.

        Returns:
            list[str]: List of xlsx files to process.
            list[str]: List of pdf files to process.
        """
        
        # Get files from temp folder
        folder_content = glob.glob("**", root_dir=self.config.temp, recursive=True)
        
        if not folder_content:
            self.log.info("TEMP Folder is empty.")
        else:
            # add path to filenames
            folder_content = list(map(lambda x: os.path.join(self.config.temp, x), folder_content))
            self.log.info(f"TEMP Folder has {len(folder_content)} files/folders to process.")

        catalog_to_process, raw_to_process, subfolder = self.sort_files_into_lists(folder_content, move=False)
        
        # Get files from post folder
        folder_content = glob.glob("**", root_dir=self.config.post, recursive=True)
        
        if not folder_content:
            self.log.info("POST Folder is empty.")
        else:
            # add path to filenames
            folder_content = list(map(lambda x: os.path.join(self.config.post, x), folder_content))
            self.log.info(f"POST Folder has {len(folder_content)} files/folders to process.")
            
        catalog_to_process, raw_to_process, subfolder = self.sort_files_into_lists(folder_content, catalog_to_process=catalog_to_process, raw_to_process=raw_to_process, subfolder=subfolder)
                
        # Remove empty subfolder after moving files. New files that may have appeared in the subfolder will be processed in the next run
        self.remove_unused_subfolder(subfolder)
        
        return catalog_to_process, raw_to_process

    # --------------------------------------------------------------
    def clean_old_in_folder(self, folder: str) -> None:
        """Move all files older than the clean period in hours from the post folder to the trash folder."""
        
        # Get content from folder
        folder_content = glob.glob("**", root_dir=folder, recursive=True)
        
        if not folder_content:
            self.log.info(f"Nothing to clean in {folder}.")
            return
        
        folder_to_remove = []
        
        for item in folder_content:
                
                item_name = os.path.join(folder, item)
                # Check if the item is a file
                if os.path.isfile(item_name):
                    
                    # Check if the file is older than the clean period
                    if pd.to_datetime(os.path.getctime(item_name), unit='s') < pd.to_datetime("now") - pd.Timedelta(hours=self.config.clean_period):
                        self.trash_it(item_name, overwrite_trash=self.config.data_overwrite)
                else:
                    folder_to_remove.append(item)

        # Remove empty subfolder after moving files. 
        if folder_to_remove:
            # TODO: #1  Check if the subfolder corresponds to the raw data folder as defined in the config file and do not remove it
            for item in folder_to_remove:
                # New files that may have appeared in the subfolder will be processed in the next run, so test if it is empty before removing
                if not os.listdir(item):
                    try:
                        os.rmdir(item)
                        self.log.info(f"Removed folder {item}")
                    except Exception as e:
                        self.log.warning(f"Error removing folder {item}: {e}")

    # --------------------------------------------------------------
    def clean_folders(self) -> None:
        """Check if it's time to clean the post folder and update the last clean time in the config file."""

        if pd.to_datetime("now") - self.config.last_clean > pd.Timedelta(hours=self.config.clean_period):
            self.clean_old_in_folder(self.config.post)
            self.clean_old_in_folder(self.config.temp)
            self.config.set_last_clean()

