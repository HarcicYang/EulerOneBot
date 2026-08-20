from .config import BotConfig, load_config
from .extensions.patch import apply_patches
from .hyperogger import Logger
from .onebot import Adapter
from .protocol import LagrangeProtocol
from .versions import NAME, VERSION

__all__ = ["NAME", "VERSION", "Adapter", "LagrangeProtocol", "apply_patches", "setup"]


def setup() -> tuple[Logger, BotConfig]:
    cfg = load_config("appconfig.json")
    logger = Logger.create("euler", cfg.log_level, use_nf=cfg.log_nf)
    logger.set_handler()
    return logger.name_custom("euler.main"), cfg
