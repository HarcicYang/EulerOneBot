from pathlib import Path

from .config import BotConfig, load_config
from .extensions.patch import apply_patches
from .hyperogger import Logger
from .onebot import Adapter
from .protocol import LagrangeProtocol
from .versions import NAME, VERSION

__all__ = ["NAME", "VERSION", "Adapter", "LagrangeProtocol", "apply_patches", "setup"]


def setup() -> tuple[Logger, BotConfig]:
    compiled = globals().get("__compiled__")
    if compiled is None:
        config_file = Path("appconfig.json")
    else:
        # Nuitka's containing_dir points beside the packaged program, including onefile builds.
        binary_config = Path(compiled.containing_dir) / "appconfig.json"
        cwd_config = Path.cwd() / "appconfig.json"
        config_file = cwd_config if cwd_config.exists() and not binary_config.exists() else binary_config

    cfg = load_config(str(config_file))
    logger = Logger.create("euler", cfg.log_level, use_nf=cfg.log_nf)
    logger.set_handler()
    return logger.name_custom("euler.main"), cfg
