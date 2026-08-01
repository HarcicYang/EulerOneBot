import asyncio
import time
import traceback
from collections.abc import Callable, Coroutine
from typing import Any, NoReturn

from lagrange import Client, Lagrange
from lagrange.client.events import BaseEvent

from ..config import BotConfig
from ..hyperogger import Logger
from ..onebot import Adapter as OneBotAdapter
from ..onebot import events as onebot_events
from ..utils.infomgr import info_mgr
from .handle import LagrangeEventHandler
from .impl import LagrangeImpl

logger = Logger.fetch("euler").name_custom("euler.protocol")
LagrangeEvent = type[BaseEvent]
LagrangeHandler = Callable[["LagrangeProtocol", Client, LagrangeEvent], Coroutine[Any, Any, None]]


class LagrangeProtocol:
    def __init__(self, cfg: BotConfig, onebot_adapter: OneBotAdapter):
        self.cfg = cfg
        self.adapter = onebot_adapter
        self._tasks: list[asyncio.Task[None]] = []
        self.lag = Lagrange(
            cfg.login.uin,
            "linux",
            (cfg.login.signer_url + "/api/sign/sec-sign")
            .replace("https://", f"https://{cfg.login.signer_token}@")
            .replace("http://", f"http://{cfg.login.signer_token}@"),
        )

        self.lag.log.set_level("DEBUG")

        self.impl = LagrangeImpl(self.adapter, self.lag, self)
        self.handler = LagrangeEventHandler(self.adapter, self.lag, self)

    def _subscribe(self) -> None:
        self.impl.subscribe()
        self.handler.subscribe()

    async def _cancel_tasks(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def run(self) -> None:
        self._subscribe()

        try:
            await info_mgr.init()
            await self.adapter.setup()
            self._tasks = [
                asyncio.create_task(self.adapter.cycle()),
                asyncio.create_task(self.impl.api_service()),
            ]
            if self.cfg.heartbeat.enabled:
                self._tasks.append(asyncio.create_task(self.heartbeat()))
            await self.lag.run()
        except KeyboardInterrupt:
            # noinspection PyProtectedMember
            self.lag.client._task_clear()
            logger.info("Program exited by user")
        else:
            logger.info("Program exited normally")
        finally:
            await self._cancel_tasks()
            await self.adapter.close()
            await info_mgr.close()

    async def heartbeat(self) -> NoReturn:
        while True:
            await asyncio.sleep(self.cfg.heartbeat.interval / 1000)
            try:
                await self.adapter.trigger(
                    onebot_events.HeartbeatEvent(
                        interval=self.cfg.heartbeat.interval,
                        self_id=self.lag.client.uin,
                        status=onebot_events.BotStatus(good=True, online=True),
                        time=round(time.time()),
                    )
                )
            except Exception as e:  # noinspection PyBroadException
                logger.error(repr(e))
                logger.error(traceback.format_exc())
