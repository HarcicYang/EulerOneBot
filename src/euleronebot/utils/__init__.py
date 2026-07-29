import traceback
from typing import Any, Coroutine, TypeVar


def rgb(r: int, g: int, b: int) -> tuple[int, int, int]:
    return r, g, b


def color_txt(text: str, color: tuple[int, int, int]) -> str:
    r = color[0]
    g = color[1]
    b = color[2]
    return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"


class NerdICONs:
    def __init__(self, enable: bool):
        self.enable = enable

    def __getattribute__(self, item) -> str:
        if super().__getattribute__("enable"):
            return str(super().__getattribute__(item))
        else:
            return " "

    nf_fa_circle_info = " \uf05a"
    nf_cod_bracket_error = " \uebe6"
    nf_cod_error = " \uea87"
    nf_fa_warn = " \uf071"
    nf_cod_debug_alt = " \ueb91"
    nf_cod_debug_breakpoint_log = " \ueaab"
    nf_weather_time_4 = " \ue385"


T = TypeVar("T")


async def with_retry(cor: Coroutine[Any, Any, T], maximum: int = 5) -> T:
    retried = 0
    exceptions = []
    while retried < maximum:
        try:
            res = await cor
        except Exception:
            exceptions.append(traceback.format_exc())
            retried += 1
            continue

        return res

    next_line = "\n"
    raise AssertionError(
        f"Max retries ({maximum}) exceed when operating '{getattr(cor, '__name__', '')}' :\n{next_line.join(exceptions)}\n")
