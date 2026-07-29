from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("euler-onebot")
except PackageNotFoundError:
    __version__ = "unknown"

NAME = "EulerOneBot"
VERSION = __version__
