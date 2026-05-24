# Валидатор результата для сдачи проекта.

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_TOP_LEVEL = ("success", "document", "counterparties", "items", "warnings")


def validate_output(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            errors.append(f"Missing top-level key: {key}")

    if "success" in data and not isinstance(data["success"], bool):
        errors.append("success must be bool")

    if "document" in data and not isinstance(data["document"], dict):
        errors.append("document must be object")

    if "counterparties" in data and not isinstance(data["counterparties"], list):
        errors.append("counterparties must be list")

    if "items" in data and not isinstance(data["items"], list):
        errors.append("items must be list")

    if "warnings" in data and not isinstance(data["warnings"], list):
        errors.append("warnings must be list")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -X utf8 tools\\validate_output.py examples\\expected_output.json")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        return 2

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}")
        return 1

    if not isinstance(data, dict):
        print("Invalid output: root JSON value must be an object")
        return 1

    errors = validate_output(data)
    if errors:
        print("Output validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"OK: {path} contains required result fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
