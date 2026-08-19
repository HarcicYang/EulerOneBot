#!/usr/bin/env python3
import asyncio

from euleronebot.config import load_config
from euleronebot.hyperogger import Logger
from euleronebot.onebot import Adapter
from euleronebot.protocol import LagrangeProtocol
from euleronebot.utils.patch import apply_patches

cfg = load_config("appconfig.json")
logger = Logger.create("euler", cfg.log_level, use_nf=cfg.log_nf)
logger.set_handler()
logger = logger.name_custom("euler.main")

if __name__ == "__main__":
    logger.info("Euler OneBot")
    apply_patches()
    adapter = Adapter(impls=cfg.connections, access_token=cfg.access_token)
    protocol = LagrangeProtocol(cfg, adapter)
    asyncio.run(protocol.run())
