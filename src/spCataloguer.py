#!/usr/bin/python
"""
Check files in a folder and update a catalog file with new data.
Keep folders clean by moving old files to a trash folder.
Move files from post folder to get folder
This module will not stop execution on errors except at startup, if log can't be started and key folders and files can't be accessed
Log file is emptied on startup. Any existing log file is moved to the trash folder.

Args (stdin): ctrl+c will soft stop the process similar to kill command or systemd stop <service>. kill -9 will hard stop.

Returns (stdout): As log messages, if target_screen in log is set to True.

Raises:
    Exception: If any error occurs, the exception is raised with a message describing the error.
"""

import logging
import sys
import coloredlogs

import signal
import inspect

import os
import shutil
import glob

import json
import pandas as pd
import time

# Global Constants
CONFIG_FILE = "C:/ProgramData/Anatel/FileCataloger/config.json"

# Global variables
config = None
keep_watching = True
log = None

# --------------------------------------------------------------
class Config:
    """Class to load and store the configuration values from a JSON file."""

    def __init__(self) -> None:
        """Load the configuration values from a JSON file encoded with UTF-8 and with the following tags:
            {
                "check period in seconds":5,
                "clean period in hours":24,
                "last clean":"2021-09-30 15:00:00",
                "overwrite data in trash": true,
                "folders":{
                    "root":"D:/OneDrive",
                    "post":"post/Regulatron",
                    "temp":"temp/Regulatron",
                    "trash":"trash/Regulatron",
                    "store":"store/Regulatron",
                    "screenshots":"get/Regulatron/Screenshots"},
                "catalog":"get/Regulatron/Anuncios.xlsx",
                "log":{
                    "level":"INFO",
                    "screen output":true,
                    "file output":true,
                    "file path":"get/Regulatron/log.txt",
                    "separator": " | ",
                    "overwrite log in trash": false},
                "columns":{
                    "in":["nome", "preço", "avaliações", "nota", "imagem", "url", "data", "palavra_busca", "página_de_busca", "certificado", "características", "descrição", "ean_gtin", "estado", "estoque", "imagens", "fabricante", "modelo", "product_id", "vendas", "vendedor", "screenshot", "indice", "subcategoria", "nome_sch", "fabricante_sch", "modelo_sch", "tipo_sch", "nome_score", "modelo_score", "passível?", "probabilidade", "marketplace"],
                    "out":["nome", "preço", "avaliações", "nota", "imagem", "url", "data", "palavra_busca", "página_de_busca", "certificado", "características", "descrição", "ean_gtin", "estado", "estoque", "imagens", "fabricante", "modelo", "product_id", "vendas", "vendedor", "screenshot", "indice", "subcategoria", "nome_sch", "fabricante_sch", "modelo_sch", "tipo_sch", "nome_score", "modelo_score", "passível?", "probabilidade", "marketplace", "status_screenshot"],
                    "key":"screenshot"},
                    
            }
        """
        self.__load_config__()
        
        self.post = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["post"])
        self.temp = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["temp"])
        self.trash = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["trash"])
        self.screenshots = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["screenshots"])
        self.store = os.path.join(self.raw["folders"]["root"], self.raw["folders"]["store"])
        
        self.catalog = os.path.join(self.raw["folders"]["root"], self.raw["catalog"])
        
        self.log_level = self.raw["log"]["level"]
        self.log_screen = self.raw["log"]["screen output"]
        self.log_file = self.raw["log"]["file output"]
        self.log_filename = os.path.join(self.raw["folders"]["root"], self.raw["log"]["file path"])
        self.log_separator = self.raw["log"]["separator"]
        self.log_file_format = self.__log_format_plain__()
        self.log_screen_format = self.__log_format_colour__()
        self.log_title = self.__log_titles__()
        self.log_overwrite = self.raw["log"]["overwrite log in trash"]
        
        self.columns_in = sorted(self.raw["columns"]["in"])
        self.columns_out = self.raw["columns"]["out"]
        self.columns_key = self.raw["columns"]["key"]
        
        self.check_period = self.raw["check period in seconds"]
        self.clean_period = self.raw["clean period in hours"]
        
        self.last_clean = pd.to_datetime(self.raw["last clean"], format="%Y-%m-%d %H:%M:%S")
        
        self.data_overwrite = self.raw["overwrite data in trash"]
        
        if not self.is_config_ok():
            exit(1)

    # --------------------------------------------------------------
    def __load_config__(self) -> None:
        """Load the configuration values from a JSON file encoded with UTF-8.
        """
        
        global CONFIG_FILE
        
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as json_file:
                self.raw = json.load(json_file)
        except FileNotFoundError:
            print(f"Config file not found in path: {CONFIG_FILE}")
            exit(1)
    
    # --------------------------------------------------------------
    def __log_format_colour__(self) -> str:
        """Return the log format string.

        Returns:
            str: Log format string.
        """
        
        output_format = ""
        colour_format = self.raw["log"]["colour sequence"]
        colour_count = 0
        colour_set = '\x1b['
        separator = f"{colour_set}0m{self.log_separator}"
        for item in self.raw["log"]["format"]:
            output_format = f"{output_format}{colour_set}{colour_format[colour_count]}{item}{separator}"
            colour_count += 1
            if colour_count == len(colour_format):
                colour_count = 0
        
        return output_format[:-len(self.raw['log']['separator'])]

    # --------------------------------------------------------------
    def __log_format_plain__(self) -> str:
        """Return the log format string.

        Returns:
            str: Log format string.
        """
        
        output_format = ""
        for item in self.raw["log"]["format"]:
            output_format = f"{output_format}{item}{self.log_separator}"
        
        return output_format[:-len(self.log_separator)]

    # --------------------------------------------------------------
    def __log_titles__(self) -> str:
        """Return the log column titles as a string.
        
            "%(asctime)s" result title = "asctime"
            "%(module)s: %(funcName)s:%(lineno)d" result title = "module: funcName:lineno"
            "%(name)s[%(process)d]" result title = "name [process]"
            "%(levelname)s" result title = "levelname"
            "%(message)s" result title = "message"

        Returns:
            str: Log titles string.
        """
        
        non_title = ["%(", ")s", ")d"]
        output_format = ""
        for item in self.raw["log"]["format"]:

            for non in non_title:
                item = item.replace(non, "")
            
            output_format = f"{output_format}{item}{self.raw['log']['separator']}"
        
        return output_format[:-len(self.raw['log']['separator'])]
    # --------------------------------------------------------------
    def set_last_clean(self) -> None:
        """Write current datetime to JSON file."""
        
        self.raw["last clean"] = pd.to_datetime("now").strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as json_file:
                json.dump(self.raw, json_file, indent=4)
        except Exception as e:
            print(f"Error writing to config file: {e}")
    
    # --------------------------------------------------------------
    def is_config_ok(self) -> bool:
        """Test if the configuration folders and files exist. Test if log folder is writable. Test if config file is writable.

        Returns:
            bool: True if all folders and files exist and are writable.
        """
        
        if not os.path.exists(self.post):
            print(f"Post folder not found: {self.post}")
            return False
        
        if not os.path.exists(self.store):
            print(f"Store folder not found: {self.store}")
            return False
        
        if not os.path.exists(self.temp):
            print(f"Temp folder not found: {self.temp}")
            return False
        
        if not os.path.exists(self.trash):
            print(f"Trash folder not found: {self.trash}")
            return False
        
        if not os.path.exists(self.screenshots):
            print(f"Screenshots folder not found: {self.screenshots}")
            return False
        
        if not os.path.exists(self.catalog):
            print(f"Catalog file not found: {self.catalog}")
            return False
        
        if self.log_file:
            if not os.path.exists(os.path.dirname(self.log_filename)):
                print(f"Log folder not found: {os.path.dirname(self.log_filename)}")
                return False
            try:
                with open(self.log_filename, 'a') as log_file:
                    pass
            except Exception as e:
                print(f"Error writing to log file: {e}")
                return False
        
        try:
            with open(CONFIG_FILE, 'a') as json_file:  
                pass
        except Exception as e:
            print(f"Error writing to config file: {e}")
            return False
        
        return True

# --------------------------------------------------------------
def sigterm_handler(signal=None, frame=None) -> None:
    """Signal handler for SIGTERM (Kill) to stop the process."""

    global keep_watching
    global log

    current_function = inspect.currentframe().f_back.f_code.co_name
    log.critical(f"Kill signal received at: {current_function}()")
    keep_watching = False

# --------------------------------------------------------------
def sigint_handler(signal=None, frame=None) -> None:
    """Signal handler for SIGINT (Ctrl+C) to stop the process."""

    global keep_watching
    global log

    current_function = inspect.currentframe().f_back.f_code.co_name
    log.critical(f"Ctrl+C received at: {current_function}()")
    keep_watching = False

# --------------------------------------------------------------
def start_logging() -> bool:
    """Start the logging system with the configuration values from the config file and updating global variables.

    Returns:
        bool: True if the logging system started successfully.
    """
    global log
    global config
    
    log = logging.getLogger('Regulatron Catalog')
    
    # Drop all existing handlers
    log.handlers.clear()
    log.propagate = False
            
    match config.log_level:
        case 'DEBUG':
            log.setLevel(logging.DEBUG)
        case 'INFO':
            log.setLevel(logging.INFO)
        case 'WARNING':
            log.setLevel(logging.WARNING)
        case 'ERROR':
            log.setLevel(logging.ERROR)
        case 'CRITICAL':
            log.setLevel(logging.CRITICAL)
        case _:
            log.setLevel(logging.INFO)            
    
    if config.log_screen:
        
        terminal_width = shutil.get_terminal_size().columns
        print(f"\n{'~' * terminal_width}")
        print(config.log_title)
        
        coloredlogs.install()
        screen_formatter = coloredlogs.ColoredFormatter(fmt=config.log_screen_format)
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setFormatter(screen_formatter)
        log.addHandler(ch)
    
    if config.log_file:
        
        trash_it(config.log_filename, overwrite_trash=config.log_overwrite)
        with open(config.log_filename, 'w') as log_file:
            log_file.write(config.log_title + "\n")
        
        fh = logging.FileHandler(config.log_filename)
        file_formatter = logging.Formatter(fmt=config.log_file_format)
        fh.setFormatter(file_formatter)
        log.addHandler(fh)
    
    log.info("Starting file catalog script...")

    return True

# --------------------------------------------------------------
def move_to_temp(file: str) -> str:
    """Move a file to the temp folder, return the new path, resetting the file timestamp for the current time and log the event.

    Args:
        file (str): File to move.

    Returns:
        str: New path of the file in the temp folder.
    """
    
    global log
    global config
    
    filename = os.path.basename(file)
    try:
        shutil.move(file, config.temp)
        os.utime(os.path.join(config.temp, filename))
        log.info(f"Moved to {config.temp} the file {filename}")
        return os.path.join(config.temp, filename)
    except Exception as e:
        log.error(f"Error moving {file} to temp folder: {e}")
        return file

# --------------------------------------------------------------
def trash_it(file: str, overwrite_trash:bool) -> None:
    """Move a file to the trash folder, resetting the file timestamp for the current time and log the event.

    Args:
        file (str): File to move to the trash folder.
        overwrite_trash (bool): True if the file should be overwritten in the trash folder.
    """
    
    global log
    global config
    
    filename = os.path.basename(file)
    trashed_file = os.path.join(config.trash, filename)
    
    if overwrite_trash:
        try:
            os.remove(trashed_file)
        except FileNotFoundError:
            pass                
        except Exception as e:
            log.error(f"Error removing {filename} from trash folder: {e}")
    else:
        if os.path.exists(trashed_file):
            trashed_filename, ext = os.path.splitext(filename)
            timestamp = pd.to_datetime("now").strftime('%Y%m%d_%H%M%S')
            trashed_filename = f"{trashed_filename}_{timestamp}{ext}"
            new_trashed_file = os.path.join(config.trash, trashed_filename)
            try:
                os.rename(trashed_file, new_trashed_file)
                log.info(f"Renamed {filename} to {trashed_filename} in trash.")
            except Exception as e:
                log.error(f"Error renaming {filename} in trash folder: {e}")

    try:
        shutil.move(file, config.trash)
        os.utime(trashed_file) # force the file timestamp to the current time to avoid being cleaned by the clean process before the clean period is over
        log.info(f"Moved to {config.trash} the file {filename}")
    except Exception as e:
        log.error(f"Error moving {file} to trash folder: {e}")
        
# --------------------------------------------------------------
def move_to_store(file: str) -> None:
    """Move a file to the store folder, resetting the file timestamp for the current time and log the event.

    Args:
        file (str): File to move to the store folder.
    """
    
    global log
    global config
    
    filename = os.path.basename(file)
    try:
        shutil.move(file, config.store)
        os.utime(os.path.join(config.store, filename)) # force the file timestamp to the current time to avoid being cleaned by the clean process before the clean period is over
        log.info(f"Moved to {config.store} the file {filename}")
    except Exception as e:
        log.error(f"Error moving {file} to store folder: {e}")

# --------------------------------------------------------------
def publish(file: str) -> bool:
    """Publish a file to the screenshots folder.

    Args:
        file (str): File to publish to the screenshots folder.
    """
    
    global log
    global config
    
    filename = os.path.basename(file)
    try:
        shutil.move(file, config.screenshots)
        log.info(f"Published to {config.screenshots} the file {filename}")
        return True
    except Exception as e:
        log.error(f"Error publishing {file} to screenshots folder: {e}")
        return False

# --------------------------------------------------------------
def sort_files_into_lists(  folder_content: list[str],
                            move: bool = True,
                            xlsx_to_process: list[str] = None,
                            pdf_to_process: list[str] = None,
                            subfolders: list[str] = None) -> tuple[list[str], list[str], list[str]]:
    """Sort files in the provided listo into list of xlsx and pdf files to process and subfolders to remove.

    Args:
        files (list[str]): List of files to sort.
        move (bool): True if required to move files to the temp folder.
        xlsx_to_process (list[str]): Existing list of xlsx files to process.
        pdf_to_process (list[str]): Existing list of pdf files to process.
        subfolders (list[str]): Existing list of subfolders to remove.

    Returns:
        tuple[list[str], list[str], list[str]]: List of xlsx files to process, list of pdf files to process, list of subfolders to remove.
    """
    
    global log
    global config

    # Initialize lists if they are None
    if xlsx_to_process is None:
        xlsx_to_process = []
    if pdf_to_process is None:
        pdf_to_process = []
    if subfolders is None:
        subfolders = []
        
    for item in folder_content:
        
        # Check if the item is a file
        if os.path.isfile(item):
            
            # Classify the file by extension
            _, ext = os.path.splitext(item)
            match ext:
                
                case '.xlsx':
                    if move:                        
                        item = move_to_temp(item)

                    xlsx_to_process.append(item)
                    
                case '.pdf':
                    if move:
                        item = move_to_temp(item)
                    
                    pdf_to_process.append(item)
                
                case _: 
                    trash_it(item, overwrite_trash=config.data_overwrite)
        else:
            subfolders.append(item)
            
    return xlsx_to_process, pdf_to_process, subfolders

# --------------------------------------------------------------
def remove_unused_subfolders(subfolders: list[str]) -> None:
    """Remove empty subfolders from the post folder.

    Args:
        subfolders (list[str]): List of subfolders to remove.
    """
    
    global log
    global config
    
    if subfolders:
        for folder in subfolders:
            if not os.listdir(os.path.join(config.post, folder)):
                try:
                    os.rmdir(os.path.join(config.post, folder))
                    log.info(f"Removed folder {folder}")
                except Exception as e:
                    log.warning(f"Error removing folder {folder}: {e}")

# --------------------------------------------------------------
def get_files_to_process() -> tuple[list[str], list[str]]:
    """Move new files from the post folder to the temp folder and return the list of files to process.

    Returns:
        list[str]: List of xlsx files to process.
        list[str]: List of pdf files to process.
    """
    
    global log
    global config

    # Get files from temp folder
    folder_content = glob.glob("**", root_dir=config.temp, recursive=True)
    
    if not folder_content:
        log.info("TEMP Folder is empty.")
    else:
        # add path to filenames
        folder_content = list(map(lambda x: os.path.join(config.temp, x), folder_content))
        log.info(f"TEMP Folder has {len(folder_content)} files/folders to process.")

    xlsx_to_process, pdf_to_process, subfolders = sort_files_into_lists(folder_content, move=False)
    
    # Get files from post folder
    folder_content = glob.glob("**", root_dir=config.post, recursive=True)
    
    if not folder_content:
        log.info("POST Folder is empty.")
    else:
        # add path to filenames
        folder_content = list(map(lambda x: os.path.join(config.post, x), folder_content))
        log.info(f"POST Folder has {len(folder_content)} files/folders to process.")
        
    xlsx_to_process, pdf_to_process, subfolders = sort_files_into_lists(folder_content, xlsx_to_process=xlsx_to_process, pdf_to_process=pdf_to_process, subfolders=subfolders)
            
    # Remove empty subfolders after moving files. New files that may have appeared in the subfolders will be processed in the next run
    remove_unused_subfolders(subfolders)
    
    return xlsx_to_process, pdf_to_process

# --------------------------------------------------------------
def clean_old_in_folder(folder: str) -> None:
    """Move all files older than the clean period in hours from the post folder to the trash folder."""
    
    global log
    global config

    # Get content from folder
    folder_content = glob.glob("**", root_dir=folder, recursive=True)
    
    if not folder_content:
        log.info(f"Nothing to clean in {folder}.")
        return
    
    folder_to_remove = []
    
    for item in folder_content:
            
            item_name = os.path.join(folder, item)
            # Check if the item is a file
            if os.path.isfile(item_name):
                
                # Check if the file is older than the clean period
                if pd.to_datetime(os.path.getctime(item_name), unit='s') < pd.to_datetime("now") - pd.Timedelta(hours=config.clean_period):
                    trash_it(item_name, overwrite_trash=config.data_overwrite)
            else:
                folder_to_remove.append(item)

    # Remove empty subfolders after moving files. 
    if folder_to_remove:
        for item in folder_to_remove:
            # New files that may have appeared in the subfolders will be processed in the next run, so test if it is empty before removing
            if not os.listdir(item):
                try:
                    os.rmdir(item)
                    log.info(f"Removed folder {item}")
                except Exception as e:
                    log.warning(f"Error removing folder {item}: {e}")

# --------------------------------------------------------------
def read_excel(file: str) -> pd.DataFrame:
    """Read an Excel file and return a DataFrame.

    Args:
        file (str): Excel file to read.

    Returns:
        pd.DataFrame: DataFrame with the Excel data.
    """
    global log
    global config
    
    try:
        df_from_file = pd.read_excel(file)
    except Exception as e:
        log.error(f"Error reading Excel file {file}: {e}")
        return pd.DataFrame()
    
    try:
        df_from_file.set_index(config.columns_key, inplace=True)
    except Exception as e:
        log.error(f"Error setting index in reference data: {e}")
        pass

    return df_from_file

# --------------------------------------------------------------
def valid_data(df: pd.DataFrame) -> bool:
    """Validate the data in the DataFrame.

    Args:
        df (pd.DataFrame): DataFrame to validate.

    Returns:
        bool: True if the data is valid.
    """
    global log
    global config
    
    df_columns = df.columns.tolist()
    df_columns.append(df.index.name)

    if sorted(df_columns) != config.columns_in:
        return False
    
    return True

# --------------------------------------------------------------
def process_xlsx_files(xlsx_to_process: list[str]) -> pd.DataFrame:
    """Process the list of xlsx files and update the reference data file.

    Args:
        xlsx_to_process (list[str]): List of xlsx files to process.
        config (Config): Configuration object.
        log (logging.Logger): Logger object.
    """
    
    global log
    global config
    
    reference_df = read_excel(config.catalog)
    
    for file in xlsx_to_process:
        new_data_df = read_excel(file)

        if not valid_data(new_data_df):
            trash_it(file, overwrite_trash=config.data_overwrite)
            continue
        
        # update the reference data with the new data where index matches
        reference_df.update(new_data_df)
        
        # add new_data_df rows where index does not match
        reference_df = reference_df.combine_first(new_data_df)
        
        persist_reference(reference_df)
        
        move_to_store(file)

# --------------------------------------------------------------
def process_pdf_files(pdf_to_process: list[str]) -> None:
    """Process the list of pdf files and update the reference data file.

    Args:
        pdf_to_process (list[str]): List of pdf files to process.
        reference_df (pd.DataFrame): Reference data DataFrame.
        log (logging.Logger): Logger object.
    """
    global log
    global config
        
    reference_df = read_excel(config.catalog)
    
    for item in pdf_to_process:
        filename = os.path.basename(item)
        if filename in reference_df.index:
            reference_df.at[filename, "status_screenshot"] = 1
            if publish(item):
                persist_reference(reference_df)
            
        else:
            # if file is not present in the reference_df, just do nothing and wait for it to appear later.
            log.info(f"{filename} not found in the reference data.")

    
# --------------------------------------------------------------
def persist_reference(reference_df: pd.DataFrame) -> None:
    """Persist the reference DataFrame to the catalog file.

    Args:
        reference_df (pd.DataFrame): The reference DataFrame to be saved.
    """
    global log
    global config

    # Make a copy of the DataFrame to avoid modifying the original
    reference_df = reference_df.copy()
    
    # change index column to a regular column so it is exported to the Excel file
    reference_df.reset_index(inplace=True)
    
    # reorder columns to match order defined the config file as columns_out
    reference_df = reference_df[config.columns_out]
    
    try:
        reference_df.to_excel(config.catalog, index=False)
        log.info(f"Reference data file updated: {config.catalog}")
    except Exception as e:
        log.error(f"Error saving reference data: {e}")

# --------------------------------------------------------------
def clean_folders() -> None:
    """Check if it's time to clean the post folder and update the last clean time in the config file."""
    global config

    if pd.to_datetime("now") - config.last_clean > pd.Timedelta(hours=config.clean_period):
        clean_old_in_folder(config.post)
        clean_old_in_folder(config.temp)
        config.set_last_clean()

# --------------------------------------------------------------
# Main function
# --------------------------------------------------------------

# Register the signal handler function, to handle system kill commands
signal.signal(signal.SIGTERM, sigterm_handler)
signal.signal(signal.SIGINT, sigint_handler)

def main():
    """Main function"""
    
    global config
    global keep_watching
    
    config = Config()
    
    start_logging()
    
    # keep thread running until a crtl+C or kill command is received, even if an error occurs
    while keep_watching:
        
        try:
            xlsx_to_process, pdf_to_process = get_files_to_process()
            
            if xlsx_to_process:
                process_xlsx_files(xlsx_to_process)
                    
            if pdf_to_process:
                process_pdf_files(pdf_to_process)
            
            clean_folders()
            
            time.sleep(config.check_period)
        
        except Exception as e:
            log.exception(f"Error in main loop: {e}")
            continue

    log.info("File catalog script stopped.")
    
if __name__ == "__main__":
    main()
