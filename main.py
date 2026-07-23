from euleronebot.hyperogger import Logger
from euleronebot.config import load_config

cfg = load_config("appconfig.json")
logger = Logger.create("euler", cfg.log_level)

from euleronebot.protocol import LagrangeProtocol
from euleronebot.onebot import Adapter

import asyncio

logger.set_handler()
logger.info("Euler OneBot")
logger = logger.name_custom("euler.main")

adapter = Adapter(impls=cfg.connections)
protocol = LagrangeProtocol(adapter)

asyncio.run(protocol.run())
