import asyncio

import pytest

from euleronebot.utils import with_retry


def run(coro):
    return asyncio.run(coro)


def test_with_retry_returns_first_success_without_extra_calls():
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        return 42

    assert run(with_retry(factory)) == 42
    assert calls == 1


def test_with_retry_retries_and_respects_maximum():
    calls = 0

    async def succeeds_later():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("temporary")
        return "ok"

    assert run(with_retry(succeeds_later)) == "ok"
    assert calls == 3

    async def always_fails():
        nonlocal calls
        calls += 1
        raise ValueError("boom")

    with pytest.raises(RuntimeError, match=r"Max retries \(2\)"):
        run(with_retry(always_fails, maximum=2))
    assert calls == 5
