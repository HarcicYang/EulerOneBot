import pytest
from pydantic import ValidationError

from euleronebot.onebot import Adapter
from euleronebot.onebot.api import (
    GetVersionInfo,
    SendGroupMessage,
    SendMessageResponse,
    SendPrivateMessage,
    SetGroupBan,
)
from euleronebot.onebot.api_data import SendPrivateMsgData, SetGroupBanData
from euleronebot.onebot.segments import Text


def test_send_private_message_default_action():
    call = SendPrivateMessage(params=SendPrivateMsgData(user_id=1, message=[Text(data={"text": "hi"})]))
    assert call.action == "send_private_msg"
    assert call.model_dump()["action"] == "send_private_msg"


def test_adapter_discriminates_by_action():
    adapter = Adapter(impls=[])
    raw = (
        '{"action": "send_private_msg", "params": {"user_id": 1, '
        '"message": [{"type": "text", "data": {"text": "hi"}}]}}'
    )
    call = adapter.api_validation.validate_json(raw)
    assert isinstance(call, SendPrivateMessage)


def test_send_group_message_action():
    call = SendGroupMessage.model_validate({"action": "send_group_msg", "params": {"group_id": 2, "message": []}})
    assert call.action == "send_group_msg"


def test_set_group_ban_default_duration():
    call = SetGroupBan.model_validate({"action": "set_group_ban", "params": {"user_id": 1, "group_id": 2}})
    assert call.params.duration == 30 * 60


def test_set_group_ban_data_default():
    data = SetGroupBanData(user_id=1, group_id=2)
    assert data.duration == 1800


def test_unknown_action_rejected():
    adapter = Adapter(impls=[])
    with pytest.raises(ValidationError):
        adapter.api_validation.validate_json('{"action": "no_such_action", "params": {}}')


def test_response_roundtrip():
    rsp = SendMessageResponse(status="ok", retcode=0, data={"message_id": 1})
    restored = SendMessageResponse.model_validate(rsp.model_dump())
    assert restored == rsp


def test_get_version_info_default_action():
    call = GetVersionInfo.model_validate({"action": "get_version_info", "params": {}})
    assert call.action == "get_version_info"
