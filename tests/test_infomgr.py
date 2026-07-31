import pytest

from euleronebot.utils.infomgr import (
    InfoManager,
    MsgIDPool,
    MsgInfo,
    RequestPool,
    UIDPool,
    _load_cache,
)


def make_msg(scene_type="group", scene_id=1, seq=1) -> MsgInfo:
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
