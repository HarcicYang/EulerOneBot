import asyncio
import traceback
from typing import NoReturn, Union, TYPE_CHECKING, Any
from pydantic import TypeAdapter, ValidationError

from .connector import Connector
from .api import *
from .events import *
from ..hyperogger import Logger


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
            Union[
                SendPrivateMessage,
                SendGroupMessage,
                SendMessage,
                DeleteMessage,
                GetMessage,
                GetForwardMessage,
                SendLike,
                SendPoke,
                SetGroupKick,
                SetGroupBan,
                SetGroupWholeBan,
                SetGroupAdmin,
                SetGroupCard,
                SetGroupName,
                SetGroupLeave,
                SetGroupSpecialTitle,
                SetFriendAddRequest,
                SetGroupAddRequest,
                GetLoginInfo,
                GetStrangerInfo,
                GetFriendList,
                GetGroupInfo,
                GetGroupList,
                GetGroupMemberInfo,
                GetGroupMemberList,
                GetStatus,
                GetVersionInfo,
            ]
        )

    async def setup(self) -> None:
        self.connector =  await self.connector.setup()

    async def cycle(self) -> NoReturn:
        asyncio.create_task(self.connector.run())
        while True:
            data = await self.connector.received.get()
            try:
                api_call = self.api_validation.validate_json(data)
                await self.api_calls.put(api_call)
            except (ValueError, TypeError, ValidationError):
                logger.error(data)
                logger.error(traceback.format_exc())
                continue

    async def trigger(self, event: BaseEvent) -> None:
        await self.connector.trigger(event.model_dump_json())

    async def report(self, rsp: BaseAPIResponse) -> None:
        logger.info(f"API Result: {rsp}")
        await self.connector.report(rsp.model_dump_json())