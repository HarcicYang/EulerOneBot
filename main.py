#!/usr/bin/env python3
import asyncio

from euleronebot import Adapter, LagrangeProtocol, apply_patches, setup

def main() -> int:
    try:
        logger, cfg = setup()
    except FileNotFoundError as exc:
        print(exc)
        return 0

    logger.info("Euler OneBot")
    apply_patches()
    adapter = Adapter(impls=cfg.connections, access_token=cfg.access_token)
    protocol = LagrangeProtocol(cfg, adapter)
    asyncio.run(protocol.run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
