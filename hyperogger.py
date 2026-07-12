import datetime
import traceback
import sys

from utils import color_txt, rgb, NerdICONs
from typing import Any


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
    running_loggers = {}

    def __init__(self, use_nf: bool = True):
        self.levels = Levels(NerdICONs(use_nf))
        self.log_level = self.levels.INFO

    @classmethod
    def create(cls, key: str, level: str, use_nf: bool = True):
        c = cls(use_nf)
        c.set_level(level)
        cls.running_loggers[key] = c
        return c

    @classmethod
    def fetch(cls, key: str):
        print(cls.running_loggers)
        return cls.running_loggers.get(key)

    def set_level(self, level: str):
        if level in self.levels.level_names:
            self.log_level = self.levels.level_names[level]
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

    def log(self, message: str, level: str) -> None:
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
