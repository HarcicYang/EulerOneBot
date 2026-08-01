import asyncio
import json
import traceback
from contextlib import suppress
from typing import TYPE_CHECKING, Any, NoReturn

from pydantic import TypeAdapter

from ..hyperogger import Logger
from .api import *
from .connector import Connector
from .events import *

__all__ = ["Adapter", "Connector"]

if TYPE_CHECKING:
    from ..config import AdapterConfig, ForwardWebsocketConfig

    ADAPTER_CONFIG = AdapterConfig
    FORWARD_WEBSOCKET_CONFIG = ForwardWebsocketConfig
else:
    ADAPTER_CONFIG = Any
    FORWARD_WEBSOCKET_CONFIG = Any

logger = Logger.fetch("euler").name_custom("euler.onebot")


class Adapter:
    def __init__(self, impls: list[ADAPTER_CONFIG]):
        self.connector = Connector(impls)
        self.api_calls: asyncio.Queue[BaseAPICall] = asyncio.Queue()
        self.api_validation = TypeAdapter(
            SendPrivateMessage
            | SendGroupMessage
            | SendMessage
            | DeleteMessage
            | GetMessage
            | GetForwardMessage
            | SendLike
            | SendPoke
            | SetGroupKick
            | SetGroupBan
            | SetGroupWholeBan
            | SetGroupAdmin
            | SetGroupCard
            | SetGroupName
            | SetGroupLeave
            | SetGroupSpecialTitle
            | SetFriendAddRequest
            | SetGroupAddRequest
            | GetLoginInfo
            | GetStrangerInfo
            | GetFriendList
            | GetGroupInfo
            | GetGroupList
            | GetGroupMemberInfo
            | GetGroupMemberList
            | GetStatus
            | GetVersionInfo
            | GetCookie
            | GetCSRFToken
            | GroupReaction
        )
        self._connector_task: asyncio.Task | None = None

    async def setup(self) -> None:
        self.connector = await self.connector.setup()

    async def cycle(self) -> NoReturn:
        self._connector_task = asyncio.create_task(self.connector.run())
        while True:
            data = await self.connector.received.get()
            try:
                api_call = self.api_validation.validate_json(data)
                await self.api_calls.put(api_call)
            except (ValueError, TypeError):
                logger.error(data)
                logger.error(traceback.format_exc())
                echo = ""
                with suppress(ValueError, TypeError):
                    echo = json.loads(data).get("echo", "")
                await self.report(ActionFailedResponse(status="failed", retcode=1400, data=EmptyRsp(), echo=echo))
                continue
        # noinspection PyUnreachableCode
        raise RuntimeError()

    async def trigger(self, event: BaseEvent) -> None:
        await self.connector.trigger(event.model_dump_json())

    async def report(self, rsp: BaseAPIResponse) -> None:
        logger.info(f"API Result: {rsp}")
        await self.connector.report(rsp.model_dump_json())
