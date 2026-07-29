from euleronebot.config import load_config
from euleronebot.hyperogger import Logger

cfg = load_config("appconfig.json")
logger = Logger.create("euler", cfg.log_level)

import asyncio

from euleronebot.onebot import Adapter
from euleronebot.protocol import LagrangeProtocol

logger.set_handler()
logger.info("Euler OneBot")
logger = logger.name_custom("euler.main")

adapter = Adapter(impls=cfg.connections)
protocol = LagrangeProtocol(adapter)

asyncio.run(protocol.run())
