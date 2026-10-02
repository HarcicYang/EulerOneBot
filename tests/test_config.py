import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from euleronebot import config as config_module
from euleronebot.config import BotConfig, load_config


@pytest.fixture(autouse=True)
def reset_loaded_config(monkeypatch):
    monkeypatch.setattr(config_module, "loaded_config", None)


def test_missing_config_creates_usable_template_and_caches_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "appconfig.json"

    with pytest.raises(FileNotFoundError, match="已创建模板"):
        load_config("appconfig.json")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    assert next(iter(raw)) == "$schema"
    assert raw["login"]["sign_provider_path"] == "./sign_provider.py"
    assert raw["connections"][0]["type"] == "ForwardWebSocket"

    first = load_config("appconfig.json")
    second = load_config("appconfig.json")
    assert first is second


def test_existing_config_round_trips_login_and_discriminated_connections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = {
        "$schema": "./appconfig.schema.json",
        "log_level": "DEBUG",
        "login": {
            "uin": 123,
            "use_custom_sign_provider": True,
            "sign_provider_path": "./custom/sign.py",
            "sign_provider_entry": "build_signer",
        },
        "connections": [
            {"type": "HTTPPost", "url": "http://127.0.0.1:5005", "timeout": 5, "secret": "tok"},
            {"type": "ReverseWebSocket", "url": "ws://127.0.0.1:5006", "use_universal_client": True},
        ],
    }
    (tmp_path / "appconfig.json").write_text(json.dumps(raw), encoding="utf-8")

    cfg = load_config("appconfig.json")

    assert cfg.log_level == "DEBUG"
    assert cfg.login.uin == 123
    assert cfg.login.use_custom_sign_provider is True
    assert [connection.type for connection in cfg.connections] == ["HTTPPost", "ReverseWebSocket"]
    assert cfg.connections[0].model_dump()["timeout"] == 5
    assert cfg.connections[1].model_dump()["use_universal_client"] is True


def test_config_rejects_corrupt_non_object_and_invalid_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "appconfig.json"

    path.write_text("not-json{{{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config("appconfig.json")

    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON 对象"):
        load_config("appconfig.json")

    invalid_configs = [
        {"log_level": "NOT_A_LEVEL"},
        {"heartbeat": {"enabled": True, "interval": 0}},
        {"event_compatibility": {"reaction_event_type": "unknown"}},
        {"no_such_field": 1},
    ]
    for raw in invalid_configs:
        with pytest.raises(ValidationError):
            BotConfig.model_validate(raw)


def test_committed_schema_matches_builder_and_contains_connection_discriminator():
    schema = config_module.build_schema()
    committed = json.loads(
        Path(__file__).resolve().parent.parent.joinpath("appconfig.schema.json").read_text(encoding="utf-8")
    )
    connection_schema = schema["properties"]["connections"]["items"]

    assert committed == schema
    assert connection_schema["discriminator"]["propertyName"] == "type"
    assert len(connection_schema["oneOf"]) == 4
    assert schema["properties"]["log_level"]["enum"] == [
        "INFO",
        "DEBUG",
        "TRACE",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]
    assert schema["properties"]["$schema"]["type"] == "string"
