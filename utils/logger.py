import logging
import sys

def setup_logger(name: str = "AutoPoster") -> logging.Logger:
    """
    Initialize and configure a customized logger for the multi-agent system.
    
    Args:
        name (str): The name of the logger instance.
        
    Returns:
        logging.Logger: Configured logger object.
    """
    # Create a custom logger
    logger = logging.getLogger(name)
    
    # Set the threshold level for logging (INFO level catches normal operations)
    logger.setLevel(logging.INFO)
    
    # Prevent log messages from being propagated to the root logger (avoids duplicates)
    logger.propagate = False
    
    # Check if handlers already exist to avoid adding multiple handlers during re-imports
    if not logger.handlers:
        # Create a console handler that outputs to standard output (terminal)
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Define the string format for the log messages
        # E.g., [2026-05-24 10:00:00] [INFO] [AutoPoster] - Agent execution started.
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Attach the formatter to the handler, and the handler to the logger
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

# Instantiate a global logger for the project
system_logger = setup_logger()