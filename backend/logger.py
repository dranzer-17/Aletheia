import logging
import logging.handlers
import sys
import atexit
from queue import Queue

# This queue will hold all log records from all parts of the application
log_queue = Queue(-1)

# This listener is a background thread that pulls records from the queue
# and passes them to the actual handlers (console, file)
# This guarantees sequential, non-interleaved output.
queue_listener = None

def setup_logger():
    """
    Sets up the queue-based logging system. This should be called only once.
    """
    global queue_listener

    # The actual handlers that will do the writing
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Use mode='w' to overwrite the log file on each new run
    file_handler = logging.FileHandler('app.log', mode='w')
    file_handler.setFormatter(formatter)

    # If listener already exists, do nothing.
    if queue_listener:
        return

    # Create and start the listener
    queue_listener = logging.handlers.QueueListener(
        log_queue, console_handler, file_handler, respect_handler_level=True
    )
    queue_listener.start()
    
    # Ensure the listener is stopped when the program exits
    atexit.register(stop_logger)

def stop_logger():
    """
    Stops the queue listener thread gracefully.
    """
    global queue_listener
    if queue_listener:
        queue_listener.stop()
        queue_listener = None

def get_logger(name: str) -> logging.Logger:
    """
    Configures and returns a logger that sends records to the central queue.
    """
    logger = logging.getLogger(name)
    
    # Prevents adding handlers multiple times by clearing existing ones
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(logging.DEBUG)
    
    # The only handler for application loggers is the QueueHandler
    queue_handler = logging.handlers.QueueHandler(log_queue)
    logger.addHandler(queue_handler)
    
    return logger

# --- Initial setup when this module is imported ---
setup_logger()

