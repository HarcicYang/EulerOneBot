#!/usr/bin/env python3
import asyncio

from euleronebot.config import load_config
from euleronebot.hyperogger import Logger
from euleronebot.onebot import Adapter
from euleronebot.protocol import LagrangeProtocol

cfg = load_config("appconfig.json")
logger = Logger.create("euler", cfg.log_level, use_nf=cfg.log_nf)

logger.set_handler()
logger.info("Euler OneBot")
logger = logger.name_custom("euler.main")

adapter = Adapter(impls=cfg.connections)
protocol = LagrangeProtocol(cfg, adapter)

asyncio.run(protocol.run())
