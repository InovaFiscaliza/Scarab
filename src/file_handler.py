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
import hashlib

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
    def calculate_md5(self, file_path: str) -> str:
        """Calculate the MD5 hash of the file content.
        
        Args:
            file_path (str): File to calculate the MD5 hash.
            
        Returns:
            str: MD5 hash of the file content.
            
        Raises: None
        """
        
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    # --------------------------------------------------------------
    def remove_file(self, file: str) -> None:
        """Remove a file from the system.

        Args:
            file (str): File to remove.
        """
        
        try:
            os.remove(file)
            self.log.info(f"Removed the file {file}")
        except FileNotFoundError:
            pass                
        except Exception as e:
            self.log.error(f"Error removing {file}: {e}")
            
    # --------------------------------------------------------------
    def trash_it(self, file: str, overwrite: bool) -> None:
        """Move file in argument to the trash folder.
        If overwrite is True and file with the same name already exist in the trash folder, it will be overwritten.
        If overwrite is False, any existing file in the trash folder with the same name will be renamed with a timestamp if it has a different content.
        
        Args:
            file (str): File to move to the trash folder.
            overwrite (bool): True to overwrite existing file in the trash folder with the same name. False to rename the existing file with a timestamp
            
        Returns: None
        
        Raises: None
        """
                
        filename = os.path.basename(file)
        trashed_file = os.path.join(self.config.trash, filename)
        
        try:
            shutil.move(file, self.config.trash)
        except FileExistsError:
            if overwrite:
                self.remove_file(trashed_file)
                self.log.info(f"Removed the file {trashed_file} in the trash folder.")
            elif self.calculate_md5(trashed_file) == self.calculate_md5(file):
                self.remove_file(trashed_file)
                self.log.info(f"The file {file} is already in the trash folder with the same content.")
            else:   
                trashed_filename, ext = os.path.splitext(filename)
                timestamp = pd.to_datetime("now").strftime('%Y%m%d_%H%M%S')
                trashed_filename = f"{trashed_filename}_{timestamp}{ext}"
                new_trashed_file = os.path.join(self.config.trash, trashed_filename)
                try:
                    os.rename(trashed_file, new_trashed_file)
                    self.log.info(f"Renamed {filename} to {trashed_filename} in trash.")
                except Exception as e:
                    self.log.error(f"Error renaming {filename} in trash folder: {e}")
                    raise e
                    # TODO: #5 Assign new name to the incoming file in order to avoid overwriting the existing file when trashing
        except Exception as e:
            self.log.error(f"Error moving {file} to trash folder: {e}")
            return
        finally:
            os.utime(trashed_file)
            self.log.info(f"Moved to {self.config.trash} the file {filename}")            
            
    # --------------------------------------------------------------
    def move_to_store(self, file: str) -> None:
        """Move a file to the store folder, resetting the file timestamp for the current time and self.log.the event.

        Args:
            file (str): File to move to the store folder.
        """
                
        filename = os.path.basename(file)
        
        try:
            shutil.move(file, self.config.store)
        except FileExistsError:
            self.trash_it(file=file, overwrite=self.config.data_overwrite)
            shutil.move(file, self.config.store)
        except Exception as e:
            self.log.error(f"Error moving {file} to store folder: {e}")
            return
        finally:
            os.utime(os.path.join(self.config.store, filename)) # force the file timestamp to the current time to avoid being cleaned by the clean process before the clean period is over
            self.log.info(f"Moved to {self.config.store} the file {filename}")

    # --------------------------------------------------------------
    def publish_data_file(self, file: str) -> bool:
        """Publish a file to the raw folder.

        Args:
            file (str): File to publish to the raw folder.
        """
                
        filename = os.path.basename(file)
        
        publish_succeded = True

        for publish_folder in self.config.get[:-1]:
            try:
                shutil.copy(file, publish_folder)
                self.log.info(f"Copied {filename} to {publish_folder}")
            except Exception as e:
                self.log.error(f"Error publishing {file} to {publish_folder}: {e}")
                publish_succeded = False
            
        try:
            shutil.move(file, publish_folder[-1])
            self.log.info(f"Moved {filename} to {publish_folder}")
        except Exception as e:
            self.log.error(f"Error moving {file} to {publish_folder}: {e}")
            publish_succeded = False
        
        return publish_succeded

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
    def sort_and_clean(  self, 
                                folder_content: list[str],
                                move: bool = True,
                                catalog_to_process: list[str] = None,
                                raw_to_process: list[str] = None) -> tuple[list[str], list[str], list[str]]:
        """ Move files listed according to extension to the temp folder and return the list of files to process
            Remove subfolder and files with unrecognized extensions.
            

        Args:
            files (list[str]): List of files to sort.
            move (bool): True if required to move files to the temp folder.
            catalog_to_process (list[str]): Existing list of xlsx files to process. Default is None.
            raw_to_process (list[str]): Existing list of pdf files to process. Default is None.

        Returns:
            tuple[list[str], list[str], list[str]]: List of xlsx files to process, list of pdf files to process, list of subfolder to remove.
        """
        
        # Initialize lists if they are None
        if catalog_to_process is None:
            catalog_to_process = []
        if raw_to_process is None:
            raw_to_process = []
        
        subfolder = []
            
        for item in folder_content:
            
            # Check if the item is a file
            if os.path.isfile(item):
                
                # Move file by extension
                _, ext = os.path.splitext(item)
                match ext:
                    
                    case self.config.metadata_extension:
                        if move:                        
                            item = self.move_to_temp(item)

                        catalog_to_process.append(item)
                        
                    case self.config.data_extension:
                        if move:
                            item = self.move_to_temp(item)
                        
                        raw_to_process.append(item)
                    
                    case _: 
                        self.trash_it(file=item, overwrite=self.config.data_overwrite)
            else:
                subfolder.append(item)
                
        self.remove_unused_subfolder(subfolder)
        
        return catalog_to_process, raw_to_process

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

        catalog_to_process, raw_to_process = self.sort_and_clean(folder_content, move=False)
        
        # Get files from post folder
        for post_folder in self.config.post:
        
            folder_content = glob.glob("**", root_dir=post_folder, recursive=True)
            
            if not folder_content:
                self.log.info("POST Folder {post_folder} is empty.")
            else:
                # add path to filenames
                folder_content = list(map(lambda x: os.path.join(post_folder, x), folder_content))
                self.log.info(f"POST Folder {post_folder} has {len(folder_content)} files/folders to process.")
                
            catalog_to_process, raw_to_process = self.sort_and_clean(folder_content, catalog_to_process=catalog_to_process, raw_to_process=raw_to_process)
                        
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
                        self.trash_it(file=item_name, overwrite=self.config.data_overwrite)
                else:
                    folder_to_remove.append(item)

        # Remove empty subfolder after moving files. 
        if folder_to_remove:
            # TODO: #1  Check if the subfolder is expected as defined in the config file and do not remove it
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
            for post_folder in self.config.post:
                self.clean_old_in_folder(post_folder)
                
        self.clean_old_in_folder(self.config.temp)
        
        # TODO: #3 Sync multiple catalog files by checking if they have same content and merge them
        self.config.set_last_clean()

