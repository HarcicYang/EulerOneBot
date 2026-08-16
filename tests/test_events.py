import pytest
from pydantic import ValidationError

from euleronebot.onebot.events import (
    FriendFileUploadEvent,
    FriendRecallEvent,
    GroupDecreaseEvent,
    GroupFileUploadEvent,
    GroupMessageEvent,
    GroupMuteEvent,
    GroupPokeEvent,
    HeartbeatEvent,
    LifecycleEvent,
    PrivateMessageEvent,
    ReactionEvent,
)


def test_group_message_event():
    ev = GroupMessageEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "message",
            "message_type": "group",
            "sub_type": "group",
            "message_id": 3,
            "user_id": 4,
            "group_id": 5,
            "message": [{"type": "text", "data": {"text": "hi"}}],
            "raw_message": "hi",
            "sender": {
                "user_id": 4,
                "nickname": "n",
                "sex": "unknown",
                "age": 0,
                "card": "",
                "area": "",
                "level": "",
                "role": "member",
                "title": "",
            },
        }
    )
    assert ev.group_id == 5


def test_private_message_event_defaults():
    ev = PrivateMessageEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "message",
            "message_type": "private",
            "sub_type": "friend",
            "message_id": 3,
            "user_id": 4,
            "message": [],
            "raw_message": "",
            "sender": {"user_id": 4, "nickname": "n", "sex": "unknown", "age": 0},
        }
    )
    assert ev.sub_type == "friend"


def test_group_mute_lift_ban():
    ev = GroupMuteEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "notice",
            "notice_type": "group_ban",
            "sub_type": "lift_ban",
            "group_id": 3,
            "operator_id": 4,
            "user_id": 5,
            "duration": 0,
        }
    )
    assert ev.duration == 0


def test_group_decrease_kick_me():
    ev = GroupDecreaseEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "notice",
            "notice_type": "group_decrease",
            "sub_type": "kick_me",
            "group_id": 3,
            "operator_id": 0,
            "user_id": 2,
        }
    )
    assert ev.sub_type == "kick_me"


def test_friend_file_upload_notice_type():
    ev = FriendFileUploadEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "notice",
            "notice_type": "friend_upload",
            "user_id": 3,
            "file": {"id": "a", "name": "b", "size": 1, "busid": 0, "hash": "h", "url": "https://example.com/b"},
        }
    )
    assert ev.notice_type == "friend_upload"
    assert ev.file.url == "https://example.com/b"


def test_group_file_upload_notice_type():
    ev = GroupFileUploadEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "notice",
            "notice_type": "group_upload",
            "group_id": 3,
            "user_id": 4,
            "file": {"id": "a", "name": "b", "size": 1, "busid": 0, "url": "https://example.com/b"},
        }
    )
    assert ev.notice_type == "group_upload"
    assert ev.file.url == "https://example.com/b"


def test_friend_recall():
    ev = FriendRecallEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "notice",
            "notice_type": "friend_recall",
            "user_id": 3,
            "message_id": 4,
        }
    )
    assert ev.message_id == 4


def test_group_poke():
    ev = GroupPokeEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "notice",
            "notice_type": "notify",
            "sub_type": "poke",
            "group_id": 3,
            "target_id": 4,
            "user_id": 5,
        }
    )
    assert ev.target_id == 4


def test_reaction_event():
    ev = ReactionEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "notice",
            "notice_type": "reaction",
            "message_id": 3,
            "operator_id": 4,
            "sub_type": "add",
            "code": 1,
            "count": 2,
        }
    )
    assert ev.code == 1


def test_lifecycle_event():
    ev = LifecycleEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "meta_event",
            "meta_event_type": "lifecycle",
            "sub_type": "connect",
        }
    )
    assert ev.sub_type == "connect"


def test_heartbeat_event_requires_status():
    with pytest.raises(ValidationError):
        HeartbeatEvent.model_validate(
            {
                "time": 1,
                "self_id": 2,
                "post_type": "meta_event",
                "meta_event_type": "heartbeat",
                "interval": 15000,
            }
        )


def test_heartbeat_event():
    ev = HeartbeatEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "meta_event",
            "meta_event_type": "heartbeat",
            "status": {"online": True, "good": True},
            "interval": 15000,
        }
    )
    assert ev.status.good is True
