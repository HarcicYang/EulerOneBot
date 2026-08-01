import json
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


def build_schema() -> dict:
    """生成 appconfig.json 的 JSON Schema(由 BotConfig 模型推导)。"""
    schema = BotConfig.model_json_schema()
    schema.setdefault("title", "EulerOneBot 配置文件")
    schema.setdefault("description", "Euler OneBot 的 appconfig.json 配置结构,由 BotConfig 模型自动生成")
    schema.setdefault("$id", "./appconfig.schema.json")
    # 显式声明 $schema 字段,兼容不剥离该键的编辑器(配置解析时会忽略它)
    schema.setdefault("properties", {})["$schema"] = {"type": "string", "description": "JSON Schema 引用,解析时忽略"}
    return schema


def load_config(file: str) -> BotConfig:
    global loaded_config
    if loaded_config is not None:
        return loaded_config
    if os.path.exists(file):
        with open(file, encoding="utf-8") as f:
            data = json.load(f)
            data.pop("$schema", None)  # 编辑器引用字段,模型解析时忽略
            loaded_config = BotConfig.model_validate(data)
            return loaded_config  # type: ignore
    else:
        try:
            with open(file, "w", encoding="utf-8") as f:
                template = BotConfig().model_dump(mode="json")
                template = {"$schema": "./appconfig.schema.json", **template}
                f.write(json.dumps(template, indent=2, ensure_ascii=False))
        except Exception as e:  # noinspection PyBroadException
            raise RuntimeError(f"无法创建配置文件: {e} ，请检查路径是否有误") from e
        raise FileNotFoundError(f"配置文件 {file} 不存在， 已创建，请填写后重启")
