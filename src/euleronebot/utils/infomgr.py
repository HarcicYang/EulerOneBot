import os.path
import random
import hashlib
from Tools.scripts import ifdef
from typing import Dict, Literal, Union, Self
from pydantic import BaseModel
from lagrange.client.message import elems


class MsgInfo(BaseModel):
    scene_type: Literal["group", "user"]
    scene_id: int
    uin: int = 0
    uid: str = ""
    timestamp: int = 0
    raw_msg: list[elems.BaseElem] = []
    seq: int
    rand: int = 0
    text: str = ""

    def __eq__(self, other: Self) -> bool:  # type: ignore
        return (
                other.scene_type == self.scene_type and
                other.scene_id == self.scene_id and
                other.seq == self.seq
        )


class MsgIDPool(BaseModel):
    pool: Dict[str, MsgInfo] = {}

    def _gen_id(self, info: MsgInfo) -> int:
        key = f"{info.scene_type}_{info.scene_id}_{info.seq}_{len(list(self.pool.keys()))}".encode()
        x = hashlib.sha1(key).digest()
        return int.from_bytes(x[-4:], "big", signed=False)

    def add(self, info: MsgInfo) -> int:
        if info.scene_type == "group" and info.rand == 0:
            raise AssertionError()
        nid = self._gen_id(info)
        self.pool[str(nid)] = info
        return nid

    def fetch(self, nid: int) -> MsgInfo:
        if str(nid) in list(self.pool.keys()):
            return self.pool[str(nid)]
        else:
            raise KeyError(f"Unknown message_id = {nid} ")

    def search(self, info: MsgInfo) -> int:
        if info in list(self.pool.values()):
            index = list(self.pool.values()).index(info)
        else:
            return 0
        return int(list(self.pool.keys())[index])


class UIDPool(BaseModel):
    pool: Dict[str, int] = {}

    def add(self, uid: str, uin: int) -> int:
        self.pool[uid] = uin
        return uin

    def add_fake(self, uid: str) -> int:
        x = 0
        while not x or str(x) + "0145" in list(self.pool.keys()):
            x = random.randint(1 << 15, (1 << 16) - 1)
        self.add(uid, int(str(x) + "0145"))
        return int(str(x) + "0145")

    def from_uid(self, uid: str) -> int:
        if uid in list(self.pool.keys()):
            return self.pool[uid]
        else:
            raise ValueError(f"Unknown uid = {uid}")

    def from_uin(self, uin: int) -> str:
        if uin in list(self.pool.values()):
            index = list(self.pool.values()).index(uin)
            return list(self.pool.keys())[index].replace("b'", "").replace("'", "")
        else:
            raise ValueError(f"Unknown uin = {uin}")

    def is_exist(self, uid_or_uin: Union[int, str]) -> bool:
        if isinstance(uid_or_uin, str) and uid_or_uin in list(self.pool.keys()):
            if str(self.from_uid(uid_or_uin)).endswith("0145"):
                return False
        return uid_or_uin in list(self.pool.keys()) or uid_or_uin in list(self.pool.values())


class RequestInfo(BaseModel):
    type: Literal["friend", "group"] = "group"
    id: int
    seq: int
    ev_type: int


class RequestPool(BaseModel):
    pool: Dict[str, RequestInfo] = {}

    def _get_flag(self) -> str:
        x = 0
        while not x or str(x) in list(self.pool.keys()):
            x = random.randint(1 << 15, (1 << 18) - 1)
        return str(x)

    def set_group(self, grp_id: int, seq: int, ev_type: int) -> str:
        flag = self._get_flag()
        self.pool[flag] = RequestInfo(
            type="group",
            id=grp_id,
            seq=seq,
            ev_type=ev_type
        )
        return flag

    def has(self, info: RequestInfo) -> bool:
        return info in list(self.pool.values())

    def fetch(self, flag: str) -> RequestInfo:
        if flag in list(self.pool.keys()):
            return self.pool[flag]
        else:
            raise ValueError(f"Unknown flag: {flag}")


class InfoManager(BaseModel):
    msgid_mgr: MsgIDPool = MsgIDPool()
    uid_mgr: UIDPool = UIDPool()
    req_mgr: RequestPool = RequestPool()

    async def save(self) -> None:
        with open("cache.json", "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))


if os.path.exists("cache.json"):
    with open("cache.json", "r", encoding="utf-8") as f:
        info_mgr = InfoManager.model_validate_json(f.read())
else:
    info_mgr = InfoManager()  # type: ignore
    with open("cache.json", "w", encoding="utf-8") as f:
        f.write(info_mgr.model_dump_json(indent=2))
