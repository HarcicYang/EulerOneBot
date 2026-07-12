from pydantic import BaseModel


class BotStatus(BaseModel):
    online: bool
    good: bool
