import pytest
from pydantic import ValidationError

from euleronebot.onebot.events import (
    FriendFileUploadEvent,
    FriendPokeEvent,
    FriendRecallEvent,
    GroupFileUploadEvent,
    GroupMessageEvent,
    GroupPokeEvent,
    HeartbeatEvent,
    LifecycleEvent,
    PrivateMessageEvent,
    ReactionEvent,
)


def group_sender() -> dict:
    return {
        "user_id": 4,
        "nickname": "n",
        "sex": "unknown",
        "age": 0,
        "card": "",
        "area": "",
        "level": "",
        "role": "member",
        "title": "",
    }


def group_message(sub_type: str) -> dict:
    return {
        "time": 1,
        "self_id": 2,
        "post_type": "message",
        "message_type": "group",
        "sub_type": sub_type,
        "message_id": 3,
        "user_id": 4,
        "group_id": 5,
        "message": [{"type": "text", "data": {"text": "hi"}}],
        "raw_message": "hi",
        "sender": group_sender(),
    }


def test_group_message_event_accepts_protocol_subtypes_and_rejects_legacy_value():
    for sub_type in ("normal", "anonymous", "notice"):
        event = GroupMessageEvent.model_validate(group_message(sub_type))
        assert event.group_id == 5
        assert event.sub_type == sub_type

    with pytest.raises(ValidationError):
        GroupMessageEvent.model_validate(group_message("group"))


def test_private_message_event_uses_private_discriminator():
    event = PrivateMessageEvent.model_validate(
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
    assert event.message_type == "private"
    assert event.sub_type == "friend"


def test_notice_events_validate_representative_payloads_and_reaction_alias():
    file_info = {"id": "a", "name": "b", "size": 1, "busid": 0, "hash": "h", "url": "https://example.com/b"}
    group_upload = GroupFileUploadEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "notice_type": "group_upload",
            "group_id": 3,
            "user_id": 4,
            "file": file_info,
        }
    )
    friend_upload = FriendFileUploadEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "notice_type": "friend_upload",
            "user_id": 3,
            "file": file_info,
        }
    )
    recall = FriendRecallEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "notice_type": "friend_recall",
            "user_id": 3,
            "message_id": 4,
        }
    )
    group_poke = GroupPokeEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "notice_type": "notify",
            "sub_type": "poke",
            "group_id": 3,
            "target_id": 4,
            "user_id": 5,
        }
    )
    friend_poke = FriendPokeEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "notice_type": "notify",
            "sub_type": "poke",
            "target_id": 3,
            "user_id": 4,
        }
    )
    reaction = ReactionEvent(
        time=1,
        self_id=2,
        notice_type="group_msg_emoji_like",
        message_id=3,
        operator_id=4,
        sub_type="add",
        code=1,
        count=2,
    )

    assert group_upload.file.url == "https://example.com/b"
    assert friend_upload.file.hash == "h"
    assert recall.message_id == 4
    assert (group_poke.group_id, group_poke.target_id) == (3, 4)
    assert (friend_poke.target_id, friend_poke.user_id) == (3, 4)
    assert reaction.notice_type == "group_msg_emoji_like"


def test_meta_events_validate_lifecycle_and_require_heartbeat_status():
    lifecycle = LifecycleEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "meta_event",
            "meta_event_type": "lifecycle",
            "sub_type": "connect",
        }
    )
    heartbeat = HeartbeatEvent.model_validate(
        {
            "time": 1,
            "self_id": 2,
            "post_type": "meta_event",
            "meta_event_type": "heartbeat",
            "status": {"online": True, "good": True},
            "interval": 15000,
        }
    )

    assert lifecycle.sub_type == "connect"
    assert heartbeat.status.good is True
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
