from pydantic import BaseModel
from pydantic_settings import BaseSettings

class SignerConfig(BaseModel):
    url: str
    token: str

class BaseAdapterConfig(BaseModel):
    ...

class ForwardWebsocketConfig(BaseAdapterConfig):
    url: str
    host: str
    port: int