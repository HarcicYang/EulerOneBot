import asyncio
from typing import Literal

import pytest

from euleronebot.utils.infomgr import (
    InfoManager,
    MsgIDPool,
    MsgInfo,
    RequestPool,
    UIDPool,
    _load_cache,
)


def make_msg(scene_type: Literal["group", "user"] = "group", scene_id: int = 1, seq: int = 1) -> MsgInfo:
    return MsgInfo(scene_type=scene_type, scene_id=scene_id, seq=seq)


class TestMsgIDPool:
    def test_add_and_fetch(self):
        pool = MsgIDPool()
        info = make_msg(seq=10)
        nid = pool.add(info)
        assert isinstance(nid, int)
        assert pool.fetch(nid) == info

    def test_fetch_unknown_raises(self):
        pool = MsgIDPool()
        with pytest.raises(KeyError):
            pool.fetch(123456)

    def test_search_hit(self):
        pool = MsgIDPool()
        info = make_msg(seq=10)
        nid = pool.add(info)
        assert pool.search(info) == nid

    def test_search_miss_returns_zero(self):
        pool = MsgIDPool()
        assert pool.search(make_msg(seq=999)) == 0

    def test_search_returns_most_recent_duplicate(self):
        pool = MsgIDPool()
        first = pool.add(make_msg(seq=7))
        latest = pool.add(make_msg(seq=7))
        assert first != latest
        assert pool.search(make_msg(seq=7)) == latest

    def test_different_seq_different_id(self):
        pool = MsgIDPool()
        a = pool.add(make_msg(seq=7))
        b = pool.add(make_msg(seq=8))
        assert a != b


class TestUIDPool:
    def test_add_and_from_uid(self):
        pool = UIDPool()
        pool.add("u_abc", 10001)
        assert pool.from_uid("u_abc") == 10001

    def test_add_bytes_uid(self):
        pool = UIDPool()
        pool.add(b"u_byte", 10002)
        assert pool.from_uid("u_byte") == 10002

    def test_from_uid_unknown_raises(self):
        pool = UIDPool()
        with pytest.raises(ValueError):
            pool.from_uid("u_none")

    def test_from_uin(self):
        pool = UIDPool()
        pool.add("u_abc", 10001)
        assert pool.from_uin(10001) == "u_abc"

    def test_from_uin_unknown_raises(self):
        pool = UIDPool()
        with pytest.raises(ValueError):
            pool.from_uin(99999)

    def test_is_exist_uid_and_uin(self):
        pool = UIDPool()
        pool.add("u_abc", 10001)
        assert pool.is_exist("u_abc")
        assert pool.is_exist(10001)
        assert not pool.is_exist("u_none")

    def test_is_exist_fake_uid_returns_false(self):
        pool = UIDPool()
        fake_uin = pool.add_fake("u_fake")
        assert pool.is_exist("u_fake") is False
        assert pool.from_uid("u_fake") == fake_uin

    def test_add_fake_uin_ends_with_0145(self):
        pool = UIDPool()
        uin = pool.add_fake("u_fake")
        assert str(uin).endswith("0145")


class TestRequestPool:
    def test_set_and_fetch(self):
        pool = RequestPool()
        flag = pool.set_group(grp_id=100, seq=200, ev_type=1)
        info = pool.fetch(flag)
        assert info.type == "group"
        assert info.id == 100
        assert info.seq == 200

    def test_fetch_unknown_raises(self):
        pool = RequestPool()
        with pytest.raises(ValueError):
            pool.fetch("no-such-flag")


class TestLoadCache:
    def test_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert isinstance(_load_cache(), InfoManager)

    def test_empty_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "cache.json").write_text("", encoding="utf-8")
        assert isinstance(_load_cache(), InfoManager)

    def test_corrupt_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "cache.json").write_text("not-json{{{", encoding="utf-8")
        assert isinstance(_load_cache(), InfoManager)

    def test_valid_file_loaded(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mgr = InfoManager()
        mgr.uid_mgr.add("u_abc", 10001)
        (tmp_path / "cache.json").write_text(mgr.model_dump_json(), encoding="utf-8")
        loaded = _load_cache()
        assert loaded.uid_mgr.from_uid("u_abc") == 10001


class TestSave:
    def test_save_writes_valid_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mgr = InfoManager()
        mgr.msgid_mgr.add(make_msg(seq=5))
        asyncio.run(mgr.save())
        loaded = _load_cache()
        assert loaded.msgid_mgr.search(make_msg(seq=5)) != 0

    def test_save_falls_back_to_empty_raw_msg(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mgr = InfoManager()
        mgr.msgid_mgr.add(MsgInfo(scene_type="group", scene_id=1, seq=1, raw_msg=[object()]))
        asyncio.run(mgr.save())
        raw = (tmp_path / "cache.json").read_text(encoding="utf-8")
        assert len(raw) > 0
        assert '"raw_msg": []' in raw
        loaded = _load_cache()
        assert loaded.msgid_mgr.search(make_msg(seq=1)) != 0

    def test_save_only_clears_unserializable_message(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mgr = InfoManager()
        good = make_msg(seq=1)
        good.raw_msg = [{"text": "keep me"}]  # type: ignore[bad-assignment]
        mgr.msgid_mgr.add(good)
        bad = MsgInfo(scene_type="group", scene_id=1, seq=2, raw_msg=[object()])
        mgr.msgid_mgr.add(bad)
        asyncio.run(mgr.save())
        loaded = _load_cache()
        kept = loaded.msgid_mgr.fetch(loaded.msgid_mgr.search(good))
        assert kept.raw_msg == [{"text": "keep me"}]
        cleared = loaded.msgid_mgr.fetch(loaded.msgid_mgr.search(bad))
        assert cleared.raw_msg == []

    def test_atomic_save_keeps_old_file_if_replace_fails(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mgr = InfoManager()
        mgr.uid_mgr.add("u_keep", 10001)
        mgr.save_sync()
        before = (tmp_path / "cache.json").read_text(encoding="utf-8")
        assert before

        import euleronebot.utils.infomgr as im

        def broken_replace(src, dst):
            raise OSError("replace failed")

        monkeypatch.setattr(im.os, "replace", broken_replace)
        mgr.uid_mgr.add("u_new", 10002)
        with pytest.raises(OSError):
            mgr.save_sync()
        assert (tmp_path / "cache.json").read_text(encoding="utf-8") == before
