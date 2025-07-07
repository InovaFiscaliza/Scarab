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
import config_handler as cm
import log_handler as lm
import file_handler as fm
import metadata_handler as dm

import signal
import inspect
import sys
import logging
import traceback
from types import FrameType

import time

"""File config.json is expected in the same folder as the script."""

# Global variables
keep_watching: bool = True
"""Flag to keep the main loop running."""
error_count = 0
"""Counter of errors to stop the process if too many errors occur."""
log: logging.Logger = None
"""Logger object."""

# --------------------------------------------------------------
def sigint_handler( signal_code: signal.Signals = None,
                    frame: FrameType = None) -> None:
    """Signal handler to stop the process."""

    global keep_watching
    global log
    
    frame_info = inspect.getframeinfo(frame)
    module_name = frame_info.filename
    line_number = frame_info.lineno
    
    log.critical(f"{signal.Signals(signal_code).name} received when rolling at [{line_number}] in {module_name}")
    keep_watching = False
    
def count_errors(threshold: int) -> None:
    """Count errors to stop the process if too many errors occur."""
    
    global error_count
    global keep_watching
    global log
    
    error_count += 1
    if error_count > threshold:
        log.critical("Too many errors. Exiting...")
        keep_watching = False

# --------------------------------------------------------------
# Main function
# --------------------------------------------------------------

# Register the signal handler function, to handle system kill commands
signal.signal(signal.SIGTERM, sigint_handler)
signal.signal(signal.SIGBREAK, sigint_handler)
signal.signal(signal.SIGINT, sigint_handler)

def main(config_path: str) -> None:
    """Main function"""
    
    global keep_watching
    global log
    
    config = cm.Config(config_path)
    log = lm.start_logging(config)
    fh = fm.FileHandler(config, log)
    dh = dm.DataHandler(config, log)
    
    # initialize raw data folders to be synchronized
    fh.mirror_raw_data()
    
    error_count = 0

    # keep thread running until a ctrl+C or kill command is received, even if an error occurs
    while keep_watching:
        
        try:
            metadata_to_process, data_files_to_process, metadata_found, data_found = fh.get_files_to_process()
            
            if metadata_found:
                dh.process_metadata_files(metadata_to_process)

            if data_found:
                # remove files to ignore from the sets of files to process.
                for file_type, data_file_set in data_files_to_process.items():
                    data_file_set.difference_update(dh.data_files_to_ignore.get(file_type, set()))
                        
                dh.process_data_files(data_files_to_process)
            
            fh.clean_folders()
            
            time.sleep(config.check_period)
            
            error_count = 0
        
        except (FileNotFoundError, OSError) as e:
            log.critical(f"Error {error_count} accessing folders or files: {e}")
            
            count_errors(threshold=config.maximum_errors_before_exit)
                    
        except Exception as e:
            tb = traceback.format_exc()
            msg = "Error location (last call in traceback):"
            tb_lines = tb.splitlines()
            for line in tb_lines[-4:]:  # Show last few lines of traceback
                msg += f"\n{line}"
            log.exception(f"Error in main loop: {e}\n{msg}")

            
            count_errors(threshold=config.maximum_errors_before_exit)

    log.info(f"Scarab is moving away from ({config.name})...")
    
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scarab.py <config_path>.json")
        sys.exit(1)

    config_path = sys.argv[1]
    main(config_path)
