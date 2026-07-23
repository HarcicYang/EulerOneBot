import datetime
import traceback
import sys
import logging
from typing import Any, Self

from .utils import color_txt, rgb, NerdICONs



__all__ = ["Logger", "Levels"]


class Levels:
    def __init__(self, nf_icons: NerdICONs):
        self.nf_icons = nf_icons
        self.TRACE = color_txt(f"|{nf_icons.nf_cod_debug_breakpoint_log} Trace    |", rgb(184, 255, 254))
        self.INFO = color_txt(f"|{nf_icons.nf_fa_circle_info} Info     |", rgb(90, 221, 225))
        self.WARNING = color_txt(f"|{nf_icons.nf_fa_warn} Warning  |", rgb(82, 171, 237))
        self.ERROR = color_txt(f"|{nf_icons.nf_cod_error} Error    |", rgb(255, 48, 70))
        self.CRITICAL = color_txt(f"|{nf_icons.nf_cod_bracket_error} Critical |", rgb(178, 33, 48))
        self.DEBUG = color_txt(f"|{nf_icons.nf_cod_debug_alt} Debug    |", rgb(93, 227, 144))

        self.level_nums = {
            self.TRACE: -1,
            self.INFO: 0,
            self.WARNING: 1,
            self.ERROR: 2,
            self.CRITICAL: 3,
            self.DEBUG: 10,
        }

        self.level_names = {
            "TRACE": self.TRACE,
            "INFO": self.INFO,
            "WARNING": self.WARNING,
            "ERROR": self.ERROR,
            "CRITICAL": self.CRITICAL,
            "DEBUG": self.DEBUG,
        }


class Logger:
    running_loggers: dict[str, "Logger"] = {}

    def __init__(self, use_nf: bool = True):
        self.levels = Levels(NerdICONs(use_nf))
        self._use_nf = use_nf
        self.log_level = self.levels.INFO
        self.log_level_text = ""

    @classmethod
    def create(cls, key: str, level: str, use_nf: bool = True):
        c = cls(use_nf)
        c.set_level(level)
        cls.running_loggers[key] = c
        return c

    @classmethod
    def fetch(cls, key: str) -> Self:
        return cls.running_loggers.get(key)

    def set_level(self, level: str):
        if level in self.levels.level_names:
            self.log_level = self.levels.level_names[level]
            self.log_level_text = level
        else:
            self.log("未知的日志等级", self.levels.ERROR)

        return self

    @staticmethod
    def format_exec():
        exc_type, exc_value, exc_traceback = sys.exc_info()
        formatted = color_txt("\nTraceback: \n\n", rgb(255, 47, 47))
        tb_frames = traceback.extract_tb(exc_traceback)
        FILE = color_txt("File", rgb(85, 173, 238))
        LINE = color_txt("line", rgb(85, 173, 238))
        for frame in tb_frames:
            filename, lineno, func_name, code = frame
            formatted += (
                f"  {FILE} {color_txt(filename, rgb(104, 255, 244))},"
                f" {LINE} {color_txt(str(lineno), rgb(215, 255, 255))},"
                f" in {color_txt(func_name, rgb(70, 172, 107))}\n"
                f"      {color_txt(code, rgb(255, 255, 255))}\n\n"
            )
        formatted += f"{color_txt(exc_type.__name__, rgb(255, 47, 47))}: "
        formatted += color_txt(exc_value, rgb(255, 255, 255)) + "\n"

        return formatted

    def register_hook(self) -> None:
        def hook(exc_t: Any, exc_v: Any, exc_tb: Any) -> None:
            self.error(self.format_exec())

        sys.excepthook = hook

    def name_custom(self, name: str) -> "Logger":
        new_logger = type(self)(self._use_nf)
        new_logger.set_level(self.log_level_text)
        new_logger._set_name_bind(name)
        return new_logger

    def _set_name_bind(self, name: str) -> None:
        def nlog(message: str, level: str):
            patch = color_txt(f"[{name}]", rgb(97, 192, 224))
            self._log(f"{patch} {color_txt(message, rgb(215, 255, 255))}", level)
        self.log = nlog

    def _log(self, message: str, level: str) -> None:
        if self.levels.level_nums[level] < self.levels.level_nums[self.log_level]:
            return
        time = color_txt(self.levels.nf_icons.nf_weather_time_4 + " " + str(datetime.datetime.now())[:-4], rgb(65, 128, 176))
        if "\n" in message:
            listed = message.split("\n")
            for i in listed:
                if listed.index(i) == 0:
                    listed[0] = "\n"
                    content = f" {time} {level} {color_txt(i, rgb(215, 255, 255))}"
                else:
                    content = " " * int((len(f"{time}{level}") - 2) / 2) + color_txt(i, rgb(215, 255, 255))
                print(content)
        else:
            content = f" {time} {level} {color_txt(message, rgb(215, 255, 255))}"
            print(content)

    def log(self, message: str, level: str) -> None:
        self._log(message, level)

    def info(self, message: Any) -> None:
        self.log(str(message), self.levels.INFO)

    def warning(self, message: Any) -> None:
        self.log(str(message), self.levels.WARNING)

    def error(self, message: Any) -> None:
        self.log(str(message), self.levels.ERROR)

    def critical(self, message: Any) -> None:
        self.log(str(message), self.levels.CRITICAL)

    def debug(self, message: Any) -> None:
        self.log(str(message), self.levels.DEBUG)

    def trace(self, message: Any) -> None:
        self.log(str(message), self.levels.TRACE)

    def set_handler(self) -> None:
        custom_logger = self
        class StdHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                msg = self.format(record)
                patch = color_txt(f"[{record.name}]", rgb(97, 192, 224))
                msg = f"{patch} {color_txt(msg, rgb(215, 255, 255))}"
                match record.levelno:
                    case logging.CRITICAL:
                        custom_logger.critical(msg)
                    case logging.ERROR:
                        custom_logger.error(msg)
                    case logging.WARNING:
                        custom_logger.warning(msg)
                    case logging.INFO:
                        custom_logger.info(msg)
                    case logging.DEBUG:
                        custom_logger.trace(msg)
                    case _:
                        custom_logger.debug(msg)

        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(StdHandler())
