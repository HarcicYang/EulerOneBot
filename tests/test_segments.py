import pytest
from pydantic import TypeAdapter, ValidationError

from euleronebot.onebot.segments import (
    At,
    Dice,
    Face,
    File,
    Forward,
    GreyTips,
    Image,
    Json,
    MarketFace,
    Node,
    Poke,
    Record,
    Reply,
    Rps,
    SegmentUnion,
    Text,
    Video,
)

segment_adapter = TypeAdapter(SegmentUnion)

CASES = [
    (Text, {"text": "hello"}),
    (At, {"qq": "12345"}),
    (Reply, {"id": "42"}),
    (Face, {"id": "1"}),
    (Rps, {}),
    (Dice, {}),
    (Poke, {"id": "1", "type": "1"}),
    (MarketFace, {"face_id": "a", "tab_id": "1", "name": "x"}),
    (
        Node,
        {
            "user_id": "1",
            "nickname": "n",
            "content": [{"type": "text", "data": {"text": "hi"}}],
        },
    ),
    (Forward, {"id": "resid1", "content": []}),
    (Image, {"file": "abc.png", "summary": "img", "is_emoji": False}),
    (Record, {"file": "a.wav"}),
    (Video, {"file": "a.mp4"}),
    (File, {"file_name": "a.txt", "file_hash": "hash", "file_id": "fid", "url": "https://example.com/a.txt"}),
    (Json, {"data": '{"k": 1}'}),
    (GreyTips, {"text": "tip"}),
]


def test_segment_union_roundtrips_every_supported_shape():
    for seg_cls, data in CASES:
        seg = seg_cls(data=data)
        dumped = seg.model_dump()
        assert dumped["type"] == seg.type
        for key, value in data.items():
            assert dumped["data"][key] == value
        assert segment_adapter.validate_python(dumped) == seg


def test_segment_union_rejects_unknown_types():
    with pytest.raises(ValidationError):
        segment_adapter.validate_python({"type": "unknown", "data": {}})
