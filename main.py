from hyperogger import Logger

logger = Logger.create("euler", "INFO")

from protocol import LagrangeProtocol
from onebot import Adapter
from config import load_config

import asyncio


cfg = load_config("appconfig.json")

logger.info("Euler OneBot")

adapter = Adapter(impls=cfg.connections)
protocol = LagrangeProtocol(adapter)

asyncio.run(protocol.run())
