import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from lagrange import Lagrange
from lagrange.info.app import app_list

from euleronebot.utils.sign_provider import _MODULE_NAME, load_sign_provider

PROVIDER_SOURCE = "\n".join(
    [
        "def make_sign_provider(sign_url, uin, guid, qua):",
        "    async def get_sign(cmd, seq, buf):",
        '        return {"sign": "ab" * 32, "token": "", "extra": "cd" * 8}',
        "",
        "    return get_sign",
    ]
)

VECTORS = [
    (bytes.fromhex("00"), "93a1f04712ec636afacdc8b5de7bfd0e135349ba0db46c0298dee6de4454874c"),
    (bytes.fromhex("01"), "eb79babe6c4efa49d7e14f645b32f7b616b5b73f558f5670419155253a94cfb5"),
    (b"hello", "31408282c1640790bb51efd07dedfa6270ce9ffff9534e3f6a96589b0174d98c"),
]
ROOT_PROVIDER = Path(__file__).resolve().parent.parent / "sign_provider.py"


def write_provider(tmp_path: Path) -> str:
    path = tmp_path / "provider.py"
    path.write_text(PROVIDER_SOURCE, encoding="utf-8")
    return str(path)


class TestLoadSignProvider:
    def test_loads_entry_and_returns_factory(self, tmp_path):
        factory = load_sign_provider(write_provider(tmp_path), "make_sign_provider")
        assert callable(factory)

        get_sign = factory(None, 123, "00" * 16, "V1_LNX_NQ_3.2.26_46494_GW_B")
        result = asyncio.run(get_sign("MessageSvc.PbSendMsg", 1, b"\x00"))
        assert result == {"sign": "ab" * 32, "token": "", "extra": "cd" * 8}

    def test_registers_module_under_fixed_name(self, tmp_path):
        path = write_provider(tmp_path)
        load_sign_provider(path, "make_sign_provider")
        assert sys.modules[_MODULE_NAME].__file__ == path

    def test_reload_replaces_module(self, tmp_path):
        path = write_provider(tmp_path)
        load_sign_provider(path, "make_sign_provider")
        first = sys.modules[_MODULE_NAME]

        Path(path).write_text(PROVIDER_SOURCE.replace("def make_sign_provider", "def other"), encoding="utf-8")
        with pytest.raises(AttributeError):
            load_sign_provider(path, "make_sign_provider")
        assert sys.modules[_MODULE_NAME] is not first

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_sign_provider(str(tmp_path / "nope.py"), "make_sign_provider")

    def test_missing_entry_raises(self, tmp_path):
        with pytest.raises(AttributeError):
            load_sign_provider(write_provider(tmp_path), "does_not_exist")

    def test_broken_source_propagates(self, tmp_path):
        path = tmp_path / "broken.py"
        path.write_text("this is not python(", encoding="utf-8")
        with pytest.raises(SyntaxError):
            load_sign_provider(str(path), "make_sign_provider")


@pytest.mark.skipif(not ROOT_PROVIDER.exists(), reason="root sign_provider.py is untracked and local-only")
class TestRootProviderFile:
    """The local sign_provider.py must stay a working drop-in for hiro-qq."""

    def _load(self):
        spec = importlib.util.spec_from_file_location("euleronebot.test_root_provider", str(ROOT_PROVIDER))
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_factory_via_loader(self):
        get_sign = load_sign_provider(str(ROOT_PROVIDER), "sign_provider")(
            None, 1, "00" * 16, "V1_LNX_NQ_3.2.26_46494_GW_B"
        )
        result = asyncio.run(get_sign("MessageSvc.PbSendMsg", 1, VECTORS[0][0]))
        assert result["token"] == ""
        assert bytes.fromhex(result["extra"]) == b"\x12\x1b" + b"V1_LNX_NQ_3.2.26_46494_GW_B"
        assert len(bytes.fromhex(result["sign"])) == 32

    def test_documented_vectors(self):
        module = self._load()
        for body, expected in VECTORS:
            assert module.compute_sign(body, nonce_time=1700000000).hex() == expected

    def test_nonce_covers_all_branches(self):
        module = self._load()
        for nonce_time in (1700000000, 1700000007, 22, 11, 1700000030, 0):
            assert 0 <= module.nonce_index(nonce_time) < 32
        seen = {module.nonce_index(t) for t in (1700000000, 1700000004, 22, 9, 36, 1700000007)}
        assert len(seen) > 1

    def test_login_command_uses_its_own_high_word(self):
        module = self._load()
        for body in (b"\x00", b"hello"):
            a = module.compute_sign(body, "wtlogin.login", nonce_time=1700000000)
            b = module.compute_sign(body, "MessageSvc.PbSendMsg", nonce_time=1700000000)
            assert a != b


class FakeClient:
    def __init__(self, *args: Any):
        self.sign = args[4]
        self.connected = False

    def connect(self):
        self.connected = True

    async def wait_closed(self):
        return None


class FakeInfoManager:
    def __init__(self, *args: Any):
        self.device = SimpleNamespace(guid="ab" * 16)
        self.sig_info = SimpleNamespace(d2="ticket")

    def __enter__(self):
        return self

    def __exit__(self, *args: Any):
        return False


class TestHiroqqWiring:
    """Drive the real Lagrange.run() to prove the factory is the one used."""

    def _drive(self, monkeypatch, factory, sign_url):
        captured: dict[str, Any] = {}
        seen: dict[str, Any] = {}

        def recording_factory(url, uin, guid, qua):
            seen["args"] = (url, uin, guid, qua)
            getter = factory(url, uin, guid, qua)

            async def traced(cmd, seq, buf):
                seen["sign_call"] = (cmd, seq, buf)
                return await getter(cmd, seq, buf)

            return traced

        monkeypatch.setattr("lagrange.Client", FakeClient)
        monkeypatch.setattr("lagrange.InfoManager", FakeInfoManager)

        lag = Lagrange(
            3672492480,
            "linux",
            sign_url,
            device_info_path="./unused.json",
            signinfo_path="./unused.bin",
            custom_sign_provider=recording_factory,
        )

        async def fake_login(client):
            captured["client"] = client
            return True

        lag.login = fake_login  # type: ignore[method-assign]
        asyncio.run(lag.run())
        return seen, captured

    def test_custom_provider_receives_live_guid_and_qua(self, monkeypatch, tmp_path):
        def factory(url, uin, guid, qua):
            async def get_sign(cmd, seq, buf):
                return {"sign": "00" * 32, "token": "", "extra": "11" * 8}

            return get_sign

        seen, captured = self._drive(monkeypatch, factory, "https://sign.example.com/api/sign/sec-sign")

        url, uin, guid, qua = seen["args"]
        assert url == "https://sign.example.com/api/sign/sec-sign"
        assert uin == 3672492480
        assert guid == "ab" * 16
        assert qua == app_list["linux"].qua

        signer = captured["client"].sign
        assert asyncio.run(signer("MessageSvc.PbSendMsg", 9, b"\x00")) == {
            "sign": "00" * 32,
            "token": "",
            "extra": "11" * 8,
        }
        assert seen["sign_call"] == ("MessageSvc.PbSendMsg", 9, b"\x00")

    @pytest.mark.skipif(not ROOT_PROVIDER.exists(), reason="root sign_provider.py is untracked and local-only")
    def test_root_file_signer_reaches_the_client(self, monkeypatch):
        factory = load_sign_provider(str(ROOT_PROVIDER), "sign_provider")
        seen, captured = self._drive(monkeypatch, factory, None)
        assert seen["args"][0] is None

        signer = captured["client"].sign
        out = asyncio.run(signer("MessageSvc.PbSendMsg", 1, bytes.fromhex("00")))
        assert out["token"] == ""
        assert bytes.fromhex(out["extra"]) == b"\x12\x1b" + seen["args"][3].encode()
        assert len(bytes.fromhex(out["sign"])) == 32

    def test_url_mode_still_signs_via_http(self, monkeypatch):
        """Without a custom provider hiro-qq must fall back to its own signer."""
        captured: dict[str, Any] = {}

        monkeypatch.setattr("lagrange.Client", FakeClient)
        monkeypatch.setattr("lagrange.InfoManager", FakeInfoManager)

        lag = Lagrange(
            3672492480,
            "linux",
            "https://sign.example.com/api/sign/sec-sign",
            device_info_path="./unused.json",
            signinfo_path="./unused.bin",
        )

        async def fake_login(client):
            captured["sign"] = client.sign
            return True

        lag.login = fake_login  # type: ignore[method-assign]
        asyncio.run(lag.run())
        assert captured["sign"] is not None
        assert captured["sign"].__name__ == "get_sign"
