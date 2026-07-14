from hyperogger import Logger

logger = Logger.create("euler", "INFO")

from protocol import LagrangeProtocol
from onebot import Adapter
from config import load_config

import asyncio

cfg = load_config("appconfig.json")

logger.set_handler()
logger.info("Euler OneBot")
logger = logger.name_custom("euler.main")

adapter = Adapter(impls=cfg.connections)
protocol = LagrangeProtocol(adapter)

asyncio.run(protocol.run())
