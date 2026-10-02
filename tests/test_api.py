import json

import pytest
from pydantic import ValidationError

from euleronebot.onebot import Adapter
from euleronebot.onebot.api import (
    GetPrivateFileUrl,
    GetStatus,
    GetVersionInfo,
    SendGroupMessage,
    SendPrivateMessage,
    SetGroupBan,
    UploadGroupFile,
    UploadPrivateFile,
)


def test_adapter_accepts_supported_actions_and_applies_protocol_defaults():
    adapter = Adapter(impls=[])
    cases = [
        (
            SendPrivateMessage,
            "send_private_msg",
            {"action": "send_private_msg", "params": {"user_id": 1, "message": []}},
        ),
        (
            SendGroupMessage,
            "send_group_msg",
            {"action": "send_group_msg", "params": {"group_id": 2, "message": []}},
        ),
        (
            SetGroupBan,
            "set_group_ban",
            {"action": "set_group_ban", "params": {"user_id": 1, "group_id": 2}},
        ),
        (
            UploadGroupFile,
            "upload_group_file",
            {"action": "upload_group_file", "params": {"group_id": 1, "file": "a.txt"}},
        ),
        (
            UploadPrivateFile,
            "upload_private_file",
            {"action": "upload_private_file", "params": {"user_id": 1, "file": "a.txt"}},
        ),
        (
            GetPrivateFileUrl,
            "get_private_file_url",
            {"action": "get_private_file_url", "params": {"user_id": 1, "file_id": "fid", "file_hash": "hash"}},
        ),
        (GetStatus, "get_status", {"action": "get_status", "params": {}}),
        (GetVersionInfo, "get_version_info", {"action": "get_version_info", "params": {}}),
    ]

    for expected_type, action, raw in cases:
        call = adapter.api_validation.validate_json(json.dumps(raw))
        assert isinstance(call, expected_type)
        assert call.action == action

    ban = adapter.api_validation.validate_json(json.dumps(cases[2][2]))
    uploaded = adapter.api_validation.validate_json(json.dumps(cases[4][2]))
    assert isinstance(ban, SetGroupBan)
    assert isinstance(uploaded, UploadPrivateFile)
    assert ban.params.duration == 1800
    assert uploaded.params.name is None


def test_adapter_rejects_unknown_actions_and_invalid_params():
    adapter = Adapter(impls=[])
    with pytest.raises(ValidationError):
        adapter.api_validation.validate_json('{"action": "no_such_action", "params": {}}')
    with pytest.raises(ValidationError):
        adapter.api_validation.validate_json('{"action": "send_private_msg", "params": {}}')
