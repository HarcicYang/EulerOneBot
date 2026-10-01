import importlib.util
import sys
from collections.abc import Callable, Coroutine
from typing import Any

__all__ = ["SignFactory", "load_sign_provider"]

_MODULE_NAME = "euleronebot.custom_sign_provider"

SignResult = dict[str, Any]
SignGetter = Callable[[str, int, bytes], Coroutine[Any, Any, SignResult]]
# hiro-qq types the factory as (int, str, str, str) but calls it with
# (sign_url, uin, guid, qua), so keep the real contract here and cast at the
# Lagrange call site.
SignFactory = Callable[[str | None, int, str, str], SignGetter]


def load_sign_provider(path: str, entry: str) -> SignFactory:
    """Load the sign provider factory from an untracked user file.

    The file is executed under a fixed module name so it never collides with
    anything on sys.path, and hiro-qq re-invokes the factory on every run()
    with the live guid/qua, so loading it once is enough.
    """
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"sign provider file is not importable: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return getattr(module, entry)
