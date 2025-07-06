#!/usr/bin/python
"""
Module that handle the logging specific uses for scarab.
"""

# --------------------------------------------------------------
import config_handler as cm
import file_handler as fm

import logging
import sys
import os
import coloredlogs

import shutil

# --------------------------------------------------------------
def start_logging(config: cm.Config) -> logging.Logger:
    """Start the logging system with the configuration values from the config file.
    
    Args:
        config (cm.Config): Configuration object

    Returns:
        logging.Logger: Logger object
    """
    
    log = logging.getLogger(config.name)
    
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
    
    if config.log_to_screen:
        
        terminal_width = shutil.get_terminal_size().columns
        print(f"\n{'~' * terminal_width}")
        print(config.log_title)
        
        coloredlogs.install()
        screen_formatter = coloredlogs.ColoredFormatter(fmt=config.log_screen_format)
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setFormatter(screen_formatter)
        log.addHandler(ch)
        
        log.info("Screen log started...")

    if config.log_to_file:
        
        # Clean existing log file
        file = fm.FileHandler(config,log)
        for log_file in config.log_file_path:
            if os.path.exists(log_file):
                file.trash_it(file=log_file, overwrite=config.log_overwrite)
        
            # Create new log file with header line
            with open(log_file, 'w') as log_file_handle:
                log_file_handle.write(config.log_title + "\n")
        
            fh = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(fmt=config.log_file_format)
            fh.setFormatter(file_formatter)
            log.addHandler(fh)
            
    log.info(f"Scarab v{config.scarab_version} starts rolling ({config.name})...")

    return log