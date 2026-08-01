#!/usr/bin/env python3
"""Generate appconfig.schema.json from the BotConfig model.

Usage: python scripts/gen_schema.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from euleronebot.config import build_schema

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "appconfig.schema.json")


def main() -> None:
    schema = build_schema()

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Schema 已写入 {os.path.relpath(OUTPUT)}")


if __name__ == "__main__":
    main()
