import pytest
from pydantic import ValidationError

from euleronebot.onebot import Adapter
from euleronebot.onebot.api import (
    GetGroupFileUrl,
    GetPrivateFileUrl,
    GetStatus,
    GetStatusResponse,
    GetVersionInfo,
    SendGroupMessage,
    SendMessageResponse,
    SendPrivateMessage,
    SetGroupBan,
    UploadGroupFile,
    UploadPrivateFile,
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


def test_upload_group_file_action():
    call = UploadGroupFile.model_validate(
        {"action": "upload_group_file", "params": {"group_id": 1, "file": "a.txt", "name": "b.txt", "folder": "/x"}}
    )
    assert call.action == "upload_group_file"
    assert call.params.folder == "/x"


def test_upload_private_file_action_defaults():
    call = UploadPrivateFile.model_validate(
        {"action": "upload_private_file", "params": {"user_id": 1, "file": "a.txt"}}
    )
    assert call.action == "upload_private_file"
    assert call.params.name is None


def test_get_file_url_actions():
    group = GetGroupFileUrl.model_validate(
        {"action": "get_group_file_url", "params": {"group_id": 1, "file_id": "fid"}}
    )
    assert group.action == "get_group_file_url"
    private = GetPrivateFileUrl.model_validate(
        {"action": "get_private_file_url", "params": {"user_id": 1, "file_id": "fid", "file_hash": "hash"}}
    )
    assert private.action == "get_private_file_url"


def test_adapter_discriminates_new_file_actions():
    adapter = Adapter(impls=[])
    call = adapter.api_validation.validate_json(
        '{"action": "upload_group_file", "params": {"group_id": 1, "file": "a.txt"}}'
    )
    assert isinstance(call, UploadGroupFile)


def test_get_version_info_default_action():
    call = GetVersionInfo.model_validate({"action": "get_version_info", "params": {}})
    assert call.action == "get_version_info"


def test_get_status_action_and_response():
    call = GetStatus.model_validate({"action": "get_status", "params": {}})
    assert call.action == "get_status"
    rsp = GetStatusResponse(
        status="ok",
        retcode=0,
        data={
            "app_initialized": True,
            "app_enabled": True,
            "plugins_good": None,
            "app_good": True,
            "online": False,
            "good": True,
            "memory": 123,
        },
    )
    assert rsp.data is not None
    assert rsp.data.plugins_good is None
    assert rsp.data.memory == 123
