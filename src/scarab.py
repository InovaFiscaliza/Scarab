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
from types import FrameType

import time

"""File config.json is expected in the same folder as the script."""

# Global variables
keep_watching: bool = True
"""Flag to keep the main loop running."""
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
    
    # keep thread running until a ctrl+C or kill command is received, even if an error occurs
    while keep_watching:
        
        try:
            metadata_to_process, data_files_to_process = fh.get_files_to_process()
            
            if metadata_to_process:
                dh.process_metadata_files(metadata_to_process)

            # remove files to ignore from the set of files to process.
            data_files_to_process = data_files_to_process - dh.data_files_to_ignore
                    
            if data_files_to_process:
                dh.process_data_files(data_files_to_process)
            
            fh.clean_folders()
            
            time.sleep(config.check_period)
        
        except (FileNotFoundError, OSError) as e:
            log.critical(f"Error accessing folders or files: {e}")
            keep_watching = False
        
        except Exception as e:
            log.exception(f"Error in main loop: {e}")

    log.info(f"Scarab is moving away from ({config.name})...")
    
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scarab.py <config_path>.json")
        sys.exit(1)

    config_path = sys.argv[1]
    main(config_path)
