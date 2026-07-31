import os
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class SignerConfig(BaseModel):
    url: str = ""
    token: str = ""


class BaseAdapterConfig(BaseModel):
    type: Literal["ForwardWebSocket", "ReverseWebSocket", "HTTP", "HTTPPost"] = "ForwardWebSocket"
    url: str = ""


class ForwardWebsocketConfig(BaseAdapterConfig):
    type: Literal["ForwardWebSocket"] = "ForwardWebSocket"  # type: ignore
    ...


class ReverseWebsocketConfig(BaseAdapterConfig):
    type: Literal["ReverseWebSocket"] = "ReverseWebSocket"  # type: ignore
    api_url: str = ""
    event_url: str = ""
    use_universal_client: bool = False
    reconnect_interval: int = 3000


class HTTPConfig(BaseAdapterConfig):
    type: Literal["HTTP"] = "HTTP"  # type: ignore


class HTTPPostConfig(BaseAdapterConfig):
    type: Literal["HTTPPost"] = "HTTPPost"  # type: ignore
    timeout: int = 0
    secret: str = ""


AdapterConfig = Annotated[
    HTTPConfig | HTTPPostConfig | ForwardWebsocketConfig | ReverseWebsocketConfig,
    Field(discriminator="type"),
]


class HeartbeatConfig(BaseModel):
    enabled: bool = True
    interval: int = 15000


class LoginConfig(BaseModel):
    uin: int = 0
    signer_url: str = "https://"
    signer_token: str = ""


class BotConfig(BaseSettings):
    log_level: Literal["INFO", "DEBUG", "TRACE", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_nf: bool = True
    connections: list[AdapterConfig] = [ForwardWebsocketConfig()]
    login: LoginConfig = LoginConfig()
    heartbeat: HeartbeatConfig = HeartbeatConfig()


loaded_config: BotConfig | None = None


def load_config(file: str) -> BotConfig:
    if loaded_config is not None:
        return loaded_config
    if os.path.exists(file):
        with open(file, encoding="utf-8") as f:
            return BotConfig.model_validate_json(f.read())
    else:
        try:
            with open(file, "w", encoding="utf-8") as f:
                f.write(BotConfig().model_dump_json(indent=2, ensure_ascii=False))
        except Exception as e:
            raise RuntimeError(f"无法创建配置文件: {e} ，请检查路径是否有误") from e
        raise FileNotFoundError(f"配置文件 {file} 不存在， 已创建，请填写后重启")
