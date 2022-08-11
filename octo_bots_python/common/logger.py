import datetime
import platform
import sys

import colorama

colorama.init(wrap=False)

TRACE_COLOR = 12
DEBUG_COLOR = 2
INFO_COLOR = 4
DEPRECATED_COLOR = 7
WARN_COLOR = 3
ERROR_COLOR = 9
FATAL_COLOR = 1

if platform.system() == 'Windows':
    TRACE_COLOR = colorama.Fore.WHITE
    DEBUG_COLOR = colorama.Fore.GREEN
    INFO_COLOR = colorama.Fore.CYAN
    DEPRECATED_COLOR = colorama.Fore.LIGHTBLUE_EX
    WARN_COLOR = colorama.Fore.YELLOW
    ERROR_COLOR = colorama.Fore.LIGHTRED_EX
    FATAL_COLOR = colorama.Fore.RED

TRACE = 0
DEBUG = 2
INFO = 3
DEPRECATED = 4
WARN = 5
ERROR = 6
FATAL = 7

logger_levels = {
    TRACE: 'TRACE',
    DEBUG: 'DEBUG',
    INFO: 'INFO',
    DEPRECATED: 'DEPRECATED',
    WARN: 'WARN',
    ERROR: 'ERROR',
    FATAL: 'FATAL'
}

class Logger:
    def __init__(self, channel, level=INFO):
        self._channel = channel
        self._level = level
        self._node = platform.node()

    def __log(self, color, level, msg):
        if level >= self._level:
            ts = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            if platform.system() == "Windows":
                sys.stdout.write("{}[{}][{}][{}][{}]: {}{}\n".format(color, ts, self._node, logger_levels[level], self._channel, msg, colorama.Fore.RESET))
            else:
                sys.stdout.write(u"\u001b[1;38;5;{}m[{}][{}][{}][{}]: {}\u001b[0m\n".format(color, ts, self._node, logger_levels[level], self._channel, msg))
            sys.stdout.flush()

    def trace(self, msg):
        self.__log(TRACE_COLOR, TRACE, msg)

    def debug(self, msg):
        self.__log(DEBUG_COLOR, DEBUG, msg)

    def info(self, msg):
        self.__log(INFO_COLOR, INFO, msg)

    def deprecated(self, msg):
        self.__log(DEPRECATED_COLOR, DEPRECATED, msg)

    def warn(self, msg):
        self.__log(WARN_COLOR, WARN, msg)

    def error(self, msg):
        self.__log(ERROR_COLOR, ERROR, msg)

    def fatal(self, msg):
        self.__log(FATAL_COLOR, FATAL, msg)

    def log_level(self):
        return self._level

    def channel(self):
        return self._channel

if __name__ == "__main__":
    logger = Logger("BLA", DEBUG)
    logger.trace("A")
    logger.debug("A")
    logger.info("A")
    logger.deprecated("A")
    logger.warn("A")
    logger.error("A")
    logger.fatal("A")
