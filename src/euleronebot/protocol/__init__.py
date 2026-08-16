import asyncio
import time
import traceback
from collections.abc import Callable, Coroutine
from typing import Any, Literal, NoReturn

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
        self.status = onebot_events.BotStatus(online=False, good=True)
        self._disable_sent = False
        self._tasks: list[asyncio.Task[None]] = []
        self.lag = Lagrange(
            cfg.login.uin,
            "custom" if cfg.login.use_custom else "linux",
            (cfg.login.signer_url + "/api/sign/sec-sign")
            .replace("https://", f"https://{cfg.login.signer_token}@")
            .replace("http://", f"http://{cfg.login.signer_token}@"),
            custom_protocol_path=cfg.login.appinfo_path,
        )

        self.lag.log.set_level("DEBUG")

        self.impl = LagrangeImpl(self.adapter, self.lag, self)
        self.handler = LagrangeEventHandler(self.adapter, self.lag, self)

    def _subscribe(self) -> None:
        self.impl.subscribe()
        self.handler.subscribe()

    def set_online(self, online: bool) -> None:
        self.status = onebot_events.BotStatus(online=online, good=self.status.good)

    def _self_id(self) -> int:
        client = getattr(self.lag, "client", None)
        if client is not None:
            uin = getattr(client, "uin", 0)
            if uin:
                return uin
        return getattr(self.lag, "uin", 0)

    async def emit_lifecycle(self, sub_type: Literal["enable", "disable", "connect"]) -> None:
        if sub_type == "disable":
            if self._disable_sent:
                return
            self._disable_sent = True
        elif sub_type == "connect":
            self.set_online(True)
        try:
            await self.adapter.trigger(
                onebot_events.LifecycleEvent(time=round(time.time()), self_id=self._self_id(), sub_type=sub_type)
            )
        except Exception as e:  # noinspection PyBroadException
            logger.error(f"发送 lifecycle[{sub_type}] 失败: {e!r}")

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
            await self.emit_lifecycle("enable")
            await self.lag.run()
        except KeyboardInterrupt:
            # noinspection PyProtectedMember
            self.lag.client._task_clear()
            logger.info("Program exited by user")
        else:
            logger.info("Program exited normally")
        finally:
            await self.emit_lifecycle("disable")
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
                        self_id=self._self_id(),
                        status=self.status.model_copy(deep=True),
                        time=round(time.time()),
                    )
                )
            except Exception as e:  # noinspection PyBroadException
                logger.error(repr(e))
                logger.error(traceback.format_exc())
