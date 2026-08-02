import asyncio
import json
import traceback
from contextlib import suppress
from functools import reduce
from operator import or_
from typing import TYPE_CHECKING, Any, NoReturn

from pydantic import TypeAdapter, ValidationError

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


def _summarize_validation_error(e: ValidationError, raw: dict, known_actions: set[str]) -> str:
    """把 pydantic union 验证错误压成一行摘要。

    未知 action 时 69 个 variant 会各自报 action 字面量错误,只取与 action 匹配
    的 variant 的 params 错误,避免完整 traceback 刷屏。
    """
    action = raw.get("action")
    if action is None:
        return "缺少 action 字段"
    if action not in known_actions:
        return f"未知 action: {action!r}"
    errors = e.errors()
    # action 字面量校验失败的 variant(与调用方无关),其 params 错误一并忽略
    action_fail = {err["loc"][0] for err in errors if err["type"] == "literal_error" and err["loc"][-1] == "action"}
    useful: list[str] = []
    seen: set[tuple[Any, str]] = set()
    for err in errors:
        loc: tuple = err["loc"]
        if len(loc) < 2 or loc[0] in action_fail:
            continue
        key = (loc, err["type"])
        if key in seen:
            continue
        seen.add(key)
        useful.append(f"{'.'.join(map(str, loc))}: {err['msg']}")
    head = "; ".join(useful[:5])
    if len(useful) > 5:
        head += f" ... 共 {len(useful)} 处"
    return head or "参数无效"


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
            except (ValueError, TypeError) as e:
                raw: dict = {}
                with suppress(ValueError, TypeError):
                    raw = json.loads(data)
                if isinstance(e, ValidationError):
                    # pydantic union 验证错误极其冗长(每个 variant 一份),只打一行摘要
                    logger.warning(f"API 请求验证失败: {_summarize_validation_error(e, raw, self.api_actions)}")
                    logger.trace(traceback.format_exc())
                else:
                    logger.error(data)
                    logger.error(traceback.format_exc())
                retcode = 1404 if raw.get("action") not in self.api_actions else 1400
                await self.report(
                    ActionFailedResponse(status="failed", retcode=retcode, data=EmptyRsp(), echo=raw.get("echo", ""))
                )
                continue
            await self.api_calls.put(api_call)
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
