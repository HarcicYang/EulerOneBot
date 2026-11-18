"""Prepare a disposable source tree for PyPI builds."""

from __future__ import annotations

import sys
from pathlib import Path

GIT_DEPENDENCY = '"hiro-qq @ git+https://github.com/HarcicYang/hiro-qq.git"'
PYPI_DEPENDENCY = '"hiro-qq>=0.2.0,<0.3.0"'


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} PROJECT_DIR")

    pyproject = Path(sys.argv[1]) / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    matches = content.count(GIT_DEPENDENCY)
    if matches != 1:
        raise SystemExit(f"expected exactly one git dependency, found {matches}")

    pyproject.write_text(content.replace(GIT_DEPENDENCY, PYPI_DEPENDENCY), encoding="utf-8")
    print(f"replaced {GIT_DEPENDENCY} with {PYPI_DEPENDENCY}")


if __name__ == "__main__":
    main()
