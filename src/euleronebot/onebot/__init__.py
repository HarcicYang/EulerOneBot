import asyncio
import json
import traceback
from contextlib import suppress
from functools import reduce
from operator import or_
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

API_CALL_TYPES = (
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
    GetCookie,
    GetCSRFToken,
    GroupReaction,
)


class Adapter:
    def __init__(self, impls: list[ADAPTER_CONFIG], access_token: str = ""):
        self.connector = Connector(self, impls, access_token=access_token)
        self.api_calls: asyncio.Queue[BaseAPICall] = asyncio.Queue()
        self.api_validation = TypeAdapter(reduce(or_, API_CALL_TYPES))
        self.api_actions = {t.model_fields["action"].default for t in API_CALL_TYPES}
        self._connector_task: asyncio.Task | None = None
        self._pending_responses: dict[str, asyncio.Future[BaseAPIResponse]] = {}

    async def setup(self) -> None:
        self.connector = await self.connector.setup()

    def _connector_done(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        if exc := task.exception():
            logger.error(f"Connector 异常退出: {exc!r}")
            logger.error(traceback.format_exc())

    async def cycle(self) -> NoReturn:
        self._connector_task = asyncio.create_task(self.connector.run())
        self._connector_task.add_done_callback(self._connector_done)
        while True:
            data = await self.connector.received.get()
            try:
                api_call = self.api_validation.validate_json(data)
                await self.api_calls.put(api_call)
            except (ValueError, TypeError):
                logger.error(data)
                logger.error(traceback.format_exc())
                raw: dict = {}
                with suppress(ValueError, TypeError):
                    raw = json.loads(data)
                retcode = 1404 if raw.get("action") not in self.api_actions else 1400
                await self.report(
                    ActionFailedResponse(status="failed", retcode=retcode, data=EmptyRsp(), echo=raw.get("echo", ""))
                )
                continue
        # noinspection PyUnreachableCode
        raise RuntimeError()

    async def close(self) -> None:
        if self._connector_task is not None:
            self._connector_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._connector_task
        await self.connector.close()

    def register_awaiter(self, echo: str) -> asyncio.Future[BaseAPIResponse]:
        future: asyncio.Future[BaseAPIResponse] = asyncio.get_event_loop().create_future()
        self._pending_responses[echo] = future
        return future

    async def trigger(self, event: BaseEvent) -> None:
        await self.connector.trigger(event.model_dump_json())

    async def report(self, rsp: BaseAPIResponse) -> None:
        logger.info(f"API Result: {rsp}")
        if rsp.echo and rsp.echo in self._pending_responses:
            self._pending_responses.pop(rsp.echo).set_result(rsp)
        await self.connector.report(rsp.model_dump_json())
