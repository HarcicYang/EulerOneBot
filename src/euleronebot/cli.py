from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from euleronebot import Adapter, LagrangeProtocol, setup
from euleronebot.versions import VERSION


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="euler.onebot", description="EulerOneBot OneBot v11 service")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _build_parser().parse_args(argv)
    try:
        logger, cfg = setup()
    except FileNotFoundError as exc:
        print(exc)
        return 0

    logger.info("Euler OneBot")
    adapter = Adapter(impls=cfg.connections, access_token=cfg.access_token)
    protocol = LagrangeProtocol(cfg, adapter)
    asyncio.run(protocol.run())
    return 0
