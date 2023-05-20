from colorama import init, Fore, Back
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

init(autoreset=True)

LOG_DIR = "logs"
LOG_FILE = LOG_DIR + "/console.log"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


class ColorFormatter(logging.Formatter):
    # Change this dictionary to suit your coloring needs!
    COLORS = {
        "WARNING": Fore.RED,
        "ERROR": Fore.RED + Back.WHITE,
        "DEBUG": Fore.BLUE,
        "INFO": Fore.GREEN,
        "CRITICAL": Fore.RED + Back.WHITE
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        if color:
            record.name = color + record.name
            record.levelname = color + record.levelname
            record.msg = color + record.msg
        return logging.Formatter.format(self, record)


class DefaultFormatter(logging.Formatter):
    def format(self, record):
        return logging.Formatter.format(self, record)


class ColorLogger(logging.Logger):
    def __init__(self, name):
        logging.Logger.__init__(self, name, logging.DEBUG)
        self.default_formatter = DefaultFormatter("%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s")
        self.color_formatter = ColorFormatter("%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s")
        self.get_file_handler()
        self.get_console_handler()

    def get_console_handler(self):
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(self.color_formatter)
        self.addHandler(console)

    def get_file_handler(self):
        file_handler = TimedRotatingFileHandler(LOG_FILE, when='midnight')
        file_handler.setFormatter(self.default_formatter)
        self.addHandler(file_handler)



def get_logger(logger_name):
    logging.setLoggerClass(ColorLogger)
    logger = logging.getLogger(logger_name)
    return logger


def main():
    logger = get_logger('Test')
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.debug("This is a debug message")
    logger.error("This is an error message")


if __name__ == "__main__":
    main()
