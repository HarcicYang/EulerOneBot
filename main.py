#!/usr/bin/env python3
import asyncio

from euleronebot import Adapter, LagrangeProtocol, setup

logger, cfg = setup()

if __name__ == "__main__":
    logger.info("Euler OneBot")
    # apply_patches()
    adapter = Adapter(impls=cfg.connections, access_token=cfg.access_token)
    protocol = LagrangeProtocol(cfg, adapter)
    asyncio.run(protocol.run())
