import asyncio
from collections.abc import Callable
from typing import Any

from lagrange.client.base import BaseClient

from euleronebot.hyperogger import Logger

_HEARTBEAT_TIMEOUT = 10
_heartbeat_timeout_patched = False


def patch_lagrange_heartbeat_timeout() -> None:
    """
    This patch is here due to an unsure bug that lagrange-python doesn't set timeout for some of the network actions
    """
    global _heartbeat_timeout_patched
    if _heartbeat_timeout_patched:
        return

    original_sso_heartbeat = BaseClient.sso_heartbeat

    async def sso_heartbeat_with_total_timeout(self: BaseClient, *args: Any, **kwargs: Any) -> float:
        try:
            return await asyncio.wait_for(
                original_sso_heartbeat(self, *args, **kwargs),
                timeout=_HEARTBEAT_TIMEOUT,
            )
        except TimeoutError:
            raise
        except (ConnectionError, OSError) as exc:
            raise TimeoutError("Lagrange heartbeat network failure") from exc
        except asyncio.CancelledError as exc:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise
            raise TimeoutError("Lagrange heartbeat response cancelled") from exc

    BaseClient.sso_heartbeat = sso_heartbeat_with_total_timeout
    _heartbeat_timeout_patched = True


def apply_patches() -> None:
    patches: list[Callable[[], None]] = [patch_lagrange_heartbeat_timeout]
    logger = Logger.fetch("euler").name_custom("euler.patches")
    for pt in patches:
        logger.trace(f"Applying patch for {pt.__name__}")
        pt()
