import os.path

from pydantic import BaseModel
from typing import Dict, Literal, Union
import random

from lagrange.client.message import elems


class MsgInfo(BaseModel):
    scene_type: Literal["group", "user"]
    scene_id: int
    uin: int
    uid: str
    timestamp: int
    raw_msg: list[elems.BaseElem]
    seq: int


class MsgIDPool(BaseModel):
    pool: Dict[str, MsgInfo] = {}

    def _gen_id(self) -> int:
        x = 0
        while not x or str(x) in list(self.pool.keys()):
            x = random.randint(1 << 15, (1 << 18) - 1)
        return x

    def add(self, info: MsgInfo) -> int:
        nid = self._gen_id()
        self.pool[str(nid)] = info
        return nid

    def fetch(self, nid: int) -> MsgInfo:
        if str(nid) in list(self.pool.keys()):
            return self.pool[str(nid)]
        else:
            raise KeyError(f"message_id = {nid} 没有对应的消息")

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

    def from_uid(self, uid: str) -> int:
        if uid in list(self.pool.keys()):
            return self.pool[uid]
        else:
            raise ValueError(f"未缓存 uid = {uid}")

    def from_uin(self, uin: int) -> str:
        if uin in list(self.pool.values()):
            index = list(self.pool.values()).index(uin)
            return list(self.pool.keys())[index]
        else:
            raise ValueError(f"未缓存 uin = {uin}")

    def is_exist(self, uid_or_uin: Union[int, str]) -> bool:
        return uid_or_uin in list(self.pool.keys()) or uid_or_uin in list(self.pool.values())


class InfoManager(BaseModel):
    msgid_mgr: MsgIDPool = MsgIDPool()
    uid_mgr: UIDPool = UIDPool()

    async def save(self) -> None:
        with open("cache.json", "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))


if os.path.exists("cache.json"):
    with open("cache.json", "r", encoding="utf-8") as f:
        info_mgr = InfoManager.model_validate_json(f.read())
else:
    info_mgr = InfoManager()
    with open("cache.json", "w", encoding="utf-8") as f:
        f.write(info_mgr.model_dump_json(indent=2))
