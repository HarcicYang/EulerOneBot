from typing import Literal
from pydantic import BaseModel


class BotStatus(BaseModel):
    online: bool
    good: bool

class TargetInfo(BaseModel):
    target: Literal["group", "user"]
    id: int
