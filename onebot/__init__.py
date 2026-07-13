import traceback
from typing import Literal, NoReturn, Union
from pydantic import TypeAdapter, ValidationError

from .connector import Connector
from .api import *
from .events import *

from ..hyperogger import Logger

logger = Logger.create("euler", "INFO")


class Adapter:
    def __init__(
            self, host: str, port: int,
            impls: list[Literal["http", "http_post", "forward_websocket", "reverse_websocket"]]
    ):
        self.connector = Connector(host, port, impls)
        self.api_validation = TypeAdapter(
            Union[
                SendPrivateMessage,
                SendGroupMessage,
                SendMessage,
                DeleteMessage,
                GetMessage,
                GetForwardMessage,
                SendLike,
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
        while True:
            data = await self.connector.received.get()
            try:
                api_call = self.api_validation.validate_json(data)
            except (ValueError, TypeError, ValidationError):
                logger.error(data)
                logger.error(traceback.format_exc())
                continue
            raise NotImplementedError()

    async def trigger(self, event: BaseEvent) -> None:
        await self.connector.trigger(event.model_dump_json())
