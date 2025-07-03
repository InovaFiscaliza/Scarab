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
import itertools
import re

from dataclasses import dataclass
from typing import List

# --------------------------------------------------------------
@dataclass
class FileHandler:
    
    config: cm.Config
    log: logging.Logger
    
    # --------------------------------------------------------------
    def move_to_temp(self, source_file: str) -> str:
        """Move a file to the temp folder, return the new path, resetting the file timestamp for the current time and self.log.the event.

        Args:
            file (str): File to move.

        Returns:
            str: New path of the file in the temp folder, or the original path if the file cannot be moved or is already in the temp folder.
        """
        
        filename = os.path.basename(source_file)
        target_file = os.path.join(self.config.temp, filename)
        
        if source_file == target_file:
            return source_file
        
        if os.path.exists(target_file):
            # test if content match
            if self._calculate_md5(target_file) == self._calculate_md5(source_file):
                self.remove_file(source_file)
                self.log.warning(f"File {filename} posted in more than one folder or duplicated in TEMP.")
                return None
            else:
                filename = self._add_timestamp_to_name(filename=filename)
                target_file = os.path.join(self.config.temp, filename)
        
        try:
            shutil.move(source_file, target_file)
            os.utime(target_file)
            self.log.info(f"Moved {source_file} to {target_file}")
            return target_file
        except Exception as e:
            self.log.error(f"Error moving {source_file} to {target_file}: {e}")
            return None

    # --------------------------------------------------------------
    def _calculate_md5(self, file_path: str) -> str:
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
    def remove_file_list(self, files: set[str]) -> None:
        """Remove a set of files from the system.

        Args:
            files (set[str]): Set of files to remove.
        """
        
        for file in files:
            self.remove_file(file)

    # --------------------------------------------------------------
    def _add_timestamp_to_name(self, filename: str, variant: int = 0) -> str:
        """Add a timestamp to the filename and return the new filename.
        
        Args:
            filename (str): File to rename.
            variant (int): Number to add to the filename if it already exists in the trash folder. Default is 0.
            
        Returns:
            str: New filename with a timestamp and variant.
        """

        name, ext = os.path.splitext(filename)
        timestamp = pd.to_datetime("now").strftime('%Y%m%d_%H%M%S')
        if variant:
            return f"{name}_{timestamp}-{variant}{ext}"
        else:
            return f"{name}_{timestamp}{ext}"
            
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
        except Exception as e:
            # FileExistsError not functioning as expected for windows in current version of shutil. Need to handle it with additional test
            if os.path.exists(trashed_file):
                if overwrite:
                    self.remove_file(trashed_file)
                    self.log.info(f"Removed the file {trashed_file} in the trash folder.")
                    
                # marked to not overwrite but the content is the same
                elif self._calculate_md5(trashed_file) == self._calculate_md5(file): 
                    self.remove_file(trashed_file)
                    self.log.info(f"The file {file} is already in the trash folder with the same content.")
                    
                # marked to not overwrite and the content is different
                else:
                    # add timestamp to the filename and rename it
                    rename_failed = True
                    variant = 0
                    while rename_failed:
                        try:
                            trashed_filename = self._add_timestamp_to_name(filename, variant)
                            new_trashed_file = os.path.join(self.config.trash, trashed_filename)
                            os.rename(trashed_file, new_trashed_file)
                            rename_failed = False
                                                        
                        except Exception as e:
                            self.log.warning(f"Duplicate name for {new_trashed_file}. Trying variant")
                            variant = variant + 1
                            if variant > self.config.maximum_file_variations:
                                self.log.error(f"Too many variants of {filename} in trash folder.")
                                raise Exception(f"Too many variants of the same file in trash folder. Check folder properties. Error: {e}")

                        # TODO: #5 Assign new name to the incoming file in order to avoid overwriting the existing file when trashing

                    self.log.info(f"Renamed {filename} to {trashed_filename} in trash.")
                    
                # once handled the trash file situation, move the incoming file to trash
                shutil.move(file, self.config.trash)
                
            # error is not due to existing file in trash folder
            else:
                self.log.error(f"Error moving {file} to trash folder: {e}")
                return

        os.utime(trashed_file)
        self.log.info(f"Moved to {self.config.trash} the file {filename}")            
            
    # --------------------------------------------------------------
    def move_to_store(self, files: List[str]) -> None:
        """Move a list of files to the store folder, resetting the file timestamp for the current time and self.log.the event.

        Args:
            files (List[str]): File(s) to move to the store folder.
        """
        
        for file in files:
            filename = os.path.basename(file)
            stored_file = os.path.join(self.config.store, filename)
            
            try:
                os.rename(file, stored_file)
            except FileExistsError:
                self.trash_it(file=stored_file, overwrite=self.config.store_data_overwrite)
                os.rename(file, stored_file)                
            except PermissionError as e:
                self.log.error(f"Permission error moving {file} to store folder: {e}")
                return
            except Exception as e: 
                self.log.error(f"Error moving {file} to store folder: {e}")
                return
            finally:
                os.utime(stored_file) # force the file timestamp to the current time to avoid being cleaned by the clean process before the clean period is over
                self.log.info(f"Moved to {self.config.store} the file {filename}")

    # --------------------------------------------------------------
    def publish_data_file(self, files_to_publish: set[str], target_key:str) -> bool:
        """Publish a file to the get folder.

        Args:
            files_to_publish (set[str]): Set of files to publish.
            
        Returns:
            bool: True if all files were published successfully, False otherwise.
        """
                        
        publish_succeeded = True

        for file in files_to_publish:
            
            filename = os.path.basename(file)

            # copy file to all publish folders
            for publish_folder in self.config.get[target_key]:
                try:
                    target_file = os.path.join(publish_folder, filename)
                    if os.path.exists(target_file):
                        if self.config.get_data_overwrite:
                            self.remove_file(target_file)
                        else:
                            self.trash_it(file=target_file, overwrite=self.config.trash_data_overwrite)
                        
                    shutil.copy(file, publish_folder)
                    self.log.info(f"Copied {filename} to {publish_folder}")
                except Exception as e:
                    self.log.error(f"Error publishing {file} to {publish_folder}: {e}")
                    publish_succeeded = False
        
        return publish_succeeded

    # --------------------------------------------------------------
    def _remove_unused_subfolder(self, folders: set[str]) -> None:
        """Remove empty subfolder from the post folder.

        Args:
            folders (set[str]): Set of folders to remove.
        """

        for folder in folders:
            if not os.listdir(folder):
                try:
                    os.rmdir(folder)
                    self.log.info(f"Removed folder {folder}")
                except Exception as e:
                    self.log.warning(f"Error removing folder {folder}: {e}")

    # --------------------------------------------------------------
    def _file_matching(self,
                        filename: str,
                        regex_rules: dict[str, re.Pattern],
                        files_to_process: dict[str, set[str]]) -> tuple[dict[str, set[str]], bool]:
        """Check if the file matches any of the regex patterns in the rules.
        
        Args:
            filename (str): Name of the file to check.
            regex_rules (dict[str, re.Pattern]): Dictionary of regex patterns to check against.
            
        Returns:
            tuple[dict[str, set[str]], bool]: Dictionary of matched files by category and a boolean indicating if a match was found.
        """
        
        name = os.path.basename(filename)
        for table, pattern in regex_rules.items():
            if pattern.match(name):
                file_in_temp = self.move_to_temp(filename)
                if file_in_temp:
                    files_to_process[table].add(file_in_temp)
                return files_to_process, True
        
        return files_to_process, False
    
    # --------------------------------------------------------------
    def sort_and_clean(self, 
                    folder_content: set[str],
                    metadata_to_process: dict[str, set[str]],
                    data_files_to_process: dict[str, set[str]]) -> tuple[dict[str,set[str]], dict[str,set[str]], bool, bool]:
        """ Move files listed according to regex patterns to the temp folder and return the list of files to process
            If files are already in the temp folder, they are not moved.
            Remove files with unrecognized patterns if discard_invalid_data_files is set to True
            Remove any empty subfolder after moving files.
            
        Args:
            folder_content (set[str]): Set of files to sort.
            metadata_to_process (dict[str, set[str]]): Existing dictionary of metadata files by category. Default is None, which will create a new dict.
            data_files_to_process (dict[str, set[str]]): Existing dictionary of data files by category. Default is None, which will create a new dict.

        Returns:
            - dict[str, set[str]]: Dictionary with table names as keys and set of metadata files to process as values
            - dict[str, set[str]]: Dictionary with data file types as keys and set of data files to process as values
            - bool: True if metadata files were found, False otherwise.
            - bool: True if data files were found, False otherwise.
            
        Raises: None
        """
            
        folders = set()
        
        metadata_found = False
        data_found = False
        for item in folder_content:
            
            # Check if the item is a file
            if os.path.isfile(item):
                file_matched = False

                # test if file contains metadata to be processed
                metadata_to_process, file_matched = self._file_matching( filename=item,
                                                                        regex_rules=self.config.metadata_file_regex,
                                                                        files_to_process=metadata_to_process)
                
                # if already found, continue to the next file
                if file_matched:
                    metadata_found = True
                    continue
                
                # test if file contains data to be arranged
                data_files_to_process, file_matched = self._file_matching(filename=item,
                                                                         regex_rules=self.config.data_file_regex,
                                                                         files_to_process=data_files_to_process)
                
                if file_matched:
                    data_found = True
                    continue
                
                # If file doesn't match any pattern, optionally trash it
                if self.config.discard_invalid_data_files:
                    self.trash_it(file=item, overwrite=self.config.trash_data_overwrite)

            # if item is a folder, simply add it to the subfolder list to be removed later
            else:
                folders.add(item)
                
        self._remove_unused_subfolder(folders)
        
        return metadata_to_process, data_files_to_process, metadata_found, data_found

    # --------------------------------------------------------------
    def get_files_to_process(self) -> tuple[dict[str,set[str]], dict[str,set[str]], bool, bool]:
        """Move new files from the post folder to the temp folder and return the list of files to process.

        Args: None
        
        Returns:
            - dict[str, set[str]]: Dictionary with table names as keys and set of metadata files to process as values
            - dict[str, set[str]]: Dictionary with data file types as keys and set of data files to process as values
            - bool: True if metadata files were found, False otherwise.
            - bool: True if data files were found, False otherwise.

        Raises: None
        """
        metadata_to_process = {table: set() for table in self.config.metadata_file_regex.keys()}
        data_to_process = {table: set() for table in self.config.data_file_regex.keys()}
        metadata_found_any_folder = False
        metadata_found_now = False
        data_found_any_folder = False
        data_found_now = False
        
        # Loop through all post folders and temp folder
        for input_folder in self.config.input_path_list:
        
            folder_content = glob.glob("**", root_dir=input_folder, recursive=True)
            
            if not folder_content:
                self.log.debug(f"Folder {input_folder} is empty.")
            else:
                # remove files and folders to ignore from the list
                folder_content = set(folder_content) - self.config.input_to_ignore
                
                # add path to filenames
                folder_content = set(map(lambda x: os.path.join(input_folder, x), folder_content))
                self.log.debug(f"Folder {input_folder} has {len(folder_content)} files/folders to process.")
                
                metadata_to_process, data_to_process, metadata_found_now, data_found_now = self.sort_and_clean(
                                                                            folder_content,
                                                                            metadata_to_process=metadata_to_process,
                                                                            data_files_to_process=data_to_process)
                
                metadata_found_any_folder |= metadata_found_now
                data_found_any_folder |= data_found_now
                
        return metadata_to_process, data_to_process, metadata_found_any_folder, data_found_any_folder

    # --------------------------------------------------------------
    def _clean_old_in_folder(self, folder: str) -> None:
        """Move all files older than the clean period in hours from the post folder to the trash folder.
        
        Args: folder (str): Folder to clean.
        
        Returns: None
        
        Raises: None
        """
        
        # Get content from folder
        folder_content = glob.glob("**", root_dir=folder, recursive=True)
        
        # Remove files and folder to ignore from the list of cleaning
        folder_content = set(folder_content) - self.config.input_to_ignore
        
        if not folder_content:
            self.log.info(f"Nothing to clean in {folder}.")
            return
        
        self.log.info(f"Checking {len(folder_content)} files/folders in {folder} for cleaning")
        
        folder_to_remove = []
        
        for item in folder_content:
                
                item_name = os.path.join(folder, item)
                # Check if the item is a file
                if os.path.isfile(item_name):
                    
                    # Check if the file is older than the clean period
                    file_creation_time = pd.to_datetime(os.path.getctime(item_name), unit='s')
                    if file_creation_time < pd.to_datetime("now") - self.config.clean_period:
                        self.trash_it(file=item_name, overwrite=self.config.trash_data_overwrite)
                else:
                    folder_to_remove.append(item_name)

        # Remove empty subfolder after moving files. 
        if folder_to_remove:
            # TODO: #1  Check if the subfolder is expected as defined in the config file and do not remove it
            for folder in folder_to_remove:
                # New files that may have appeared in the subfolder will be processed in the next run, so test if it is empty before removing
                if not os.listdir(folder):
                    try:
                        os.rmdir(folder)
                        self.log.info(f"Removed folder {folder}")
                    except Exception as e:
                        self.log.warning(f"Error removing folder {folder}: {e}")

    # --------------------------------------------------------------
    def clean_folders(self) -> None:
        """Check if it's time to clean the post folder and update the last clean time in the config file.
        
        Args: None
        
        Returns: None
        
        Raises: None"""

        if pd.to_datetime("now") - self.config.last_clean > self.config.clean_period:
            for input_folder in self.config.input_path_list:
                self._clean_old_in_folder(input_folder)
                
            self._clean_old_in_folder(self.config.temp)
        
            # TODO: #3 Sync multiple catalog files by checking if they have same content and merge them
            try:
                self.config.set_last_clean()
            except Exception as e:
                self.log.error(f"Error setting last clean time: {e}")
        
        
    # --------------------------------------------------------------
    def mirror_raw_data(self) -> None:
        """Mirror the raw data between multiple config.get folders.
        Folder comparison is based on file names only. Differences in content will be ignored.

        Args: None

        Returns: None

        Raises: None
        """
        
        # Test if self.config.get has multiple folders
        if len(self.config.get) > 1:
            self.log.info(f"Mirroring raw data between {len(self.config.get)} folders.")

            # get the content from all folders into a dictionary of lists
            folders = {}
            for folder in self.config.get:
                folders[folder] = glob.glob("**", root_dir=folder, recursive=True)

            # Use itertools.combinations to generate pairs of folders for comparison
            for folder1, folder2 in itertools.combinations(folders.keys(), 2):
                
                # Compare pair of folders
                missing_in_folder2 = [file for file in folders[folder1] if file not in folders[folder2]]
                missing_in_folder1 = [file for file in folders[folder2] if file not in folders[folder1]]

                # Copy missing files from folder1 to folder2
                for file in missing_in_folder2:
                    try:
                        shutil.copy(os.path.join(folder1, file), folder2)
                        self.log.info(f"Copied {file} from {folder1} to {folder2}")
                    except Exception as e:
                        self.log.error(f"Error copying {file} from {folder1} to {folder2}: {e}")

                # Copy missing files from folder2 to folder1
                for file in missing_in_folder1:
                    try:
                        shutil.copy(os.path.join(folder2, file), folder1)
                        self.log.info(f"Copied {file} from {folder2} to {folder1}")
                    except Exception as e:
                        self.log.error(f"Error copying {file} from {folder2} to {folder1}: {e}")
                        
