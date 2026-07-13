from pydantic import BaseModel
from typing import Literal


class BotStatus(BaseModel):
    online: bool
    good: bool

class TargetInfo(BaseModel):
    target: Literal["group", "user"]
    id: int
