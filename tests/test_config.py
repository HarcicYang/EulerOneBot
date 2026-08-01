import json

import pytest
from pydantic import ValidationError

from euleronebot import config as config_module
from euleronebot.config import BotConfig, load_config


@pytest.fixture(autouse=True)
def reset_loaded_config(monkeypatch):
    monkeypatch.setattr(config_module, "loaded_config", None)


def test_default_config_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_config("appconfig.json")
    assert (tmp_path / "appconfig.json").exists()


def test_load_existing_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = BotConfig(
        log_level="DEBUG",
        login={"uin": 123},
        connections=[{"type": "ForwardWebSocket", "url": "ws://127.0.0.1:5004"}],
    )
    (tmp_path / "appconfig.json").write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    loaded = load_config("appconfig.json")
    assert loaded.log_level == "DEBUG"
    assert loaded.login.uin == 123
    assert loaded.connections[0].url == "ws://127.0.0.1:5004"


def test_load_corrupt_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "appconfig.json").write_text("not-json{{{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config("appconfig.json")


def test_config_cached(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "appconfig.json").write_text(BotConfig().model_dump_json(), encoding="utf-8")
    first = load_config("appconfig.json")
    second = load_config("appconfig.json")
    assert first is second


def test_log_level_validation():
    with pytest.raises(ValidationError):
        BotConfig(log_level="NOT_A_LEVEL")  # type: ignore[bad-argument-type]


def test_adapter_config_discriminates_by_type():
    raw = json.dumps(
        {
            "log_level": "INFO",
            "connections": [{"type": "HTTPPost", "url": "http://x", "timeout": 5}],
        }
    )
    cfg = BotConfig.model_validate_json(raw)
    assert cfg.connections[0].type == "HTTPPost"


class TestSchema:
    def test_template_contains_schema_first(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError):
            load_config("appconfig.json")
        raw = json.loads((tmp_path / "appconfig.json").read_text(encoding="utf-8"))
        assert next(iter(raw)) == "$schema"
        assert raw["$schema"] == "./appconfig.schema.json"

    def test_load_config_with_schema_field(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "appconfig.json").write_text(
            '{"$schema": "./appconfig.schema.json", "log_level": "DEBUG", "connections": []}', encoding="utf-8"
        )
        loaded = load_config("appconfig.json")
        assert loaded.log_level == "DEBUG"

    def test_unknown_field_still_rejected(self):
        with pytest.raises(ValidationError):
            BotConfig.model_validate_json('{"no_such_field": 1}')

    def test_schema_structure(self):
        schema = config_module.build_schema()
        assert "connections" in schema["properties"]
        items = schema["properties"]["connections"]["items"]
        assert len(items["oneOf"]) == 4
        assert items["discriminator"]["propertyName"] == "type"
        assert schema["properties"]["log_level"]["enum"] == [
            "INFO",
            "DEBUG",
            "TRACE",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ]
        assert "login" in schema["properties"]
        assert "heartbeat" in schema["properties"]
        assert schema["properties"]["$schema"]["type"] == "string"

    def test_committed_schema_in_sync(self):
        import os

        schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "appconfig.schema.json")
        with open(schema_path, encoding="utf-8") as f:
            committed = json.loads(f.read())
        assert committed == config_module.build_schema()
