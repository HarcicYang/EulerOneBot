import asyncio
import time
import traceback
from typing import (
    Any,
    Callable,
    Coroutine,
    NoReturn,
    Protocol,
    Type,
    runtime_checkable
)

from lagrange import Client, Lagrange
from lagrange.client.events import BaseEvent

from ..config import load_config
from ..hyperogger import Logger
from ..onebot import Adapter as OneBotAdapter
from ..onebot import events as onebot_events
from .handle import LagrangeEventHandler
from .impl import LagrangeImpl

appconfig = load_config("./appconfig.json")
logger = Logger.fetch("euler").name_custom("euler.protocol")
LagrangeEvent = Type[BaseEvent]
LagrangeHandler = Callable[["LagrangeProtocol", Client, LagrangeEvent], Coroutine[Any, Any, None]]


@runtime_checkable
class RegisteredHandler(Protocol):
    ev_type: LagrangeEvent


def on(ev_type: LagrangeEvent) -> Callable[[LagrangeHandler], LagrangeHandler]:
    def dec(func: LagrangeHandler) -> LagrangeHandler:
        func.ev_type = ev_type
        return func

    return dec


class LagrangeProtocol:
    def __init__(self, onebot_adapter: OneBotAdapter):
        self.adapter = onebot_adapter
        self.lag = Lagrange(
            appconfig.login.uin,
            "linux",
            (appconfig.login.signer_url + "/api/sign/sec-sign") \
                .replace("https://", f"https://{appconfig.login.signer_token}@") \
                .replace("http://", f"http://{appconfig.login.signer_token}@"),
        )

        self.lag.log.set_level("DEBUG")
        self.info_updated = False

        self.impl = LagrangeImpl(self.adapter, self.lag, self)
        self.handler = LagrangeEventHandler(self.adapter, self.lag, self)

    def _subscribe(self) -> None:
        self.impl.subscribe()
        self.handler.subscribe()

    async def run(self) -> None:
        self._subscribe()

        try:
            await self.adapter.setup()
            asyncio.create_task(self.adapter.cycle())
            asyncio.create_task(self.impl.api_service())
            asyncio.create_task(self.heartbeat())
            await self.lag.run()
        except KeyboardInterrupt:
            # noinspection PyProtectedMember
            self.lag.client._task_clear()
            logger.info("Program exited by user")
        else:
            logger.info("Program exited normally")

    async def heartbeat(self) -> NoReturn:
        while True:
            await asyncio.sleep(appconfig.heartbeat.interval / 1000)
            try:
                await self.adapter.trigger(
                    onebot_events.HeartbeatEvent(
                        interval=appconfig.heartbeat.interval,
                        self_id=self.lag.client.uin,
                        status=onebot_events.BotStatus(good=True, online=True),
                        time=round(time.time())
                    )
                )
            except Exception as e:
                logger.error(repr(e))
                logger.error(traceback.format_exc())
