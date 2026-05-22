"""
tools/validate_output.py

Строгий валидатор результата parse_requisites.

Запуск:
    python tools/validate_output.py examples/demo_result.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_TOP_LEVEL = ("success", "document", "counterparties", "items", "raw_text", "warnings", "meta")
REQUIRED_DOCUMENT = ("type", "number", "date", "total_amount")
REQUIRED_FIELD_KEYS = ("value", "confidence", "source")
REQUIRED_PARTY_FIELDS = ("name", "inn", "kpp")
REQUIRED_ITEM_FIELDS = ("name", "quantity", "price", "amount", "unit")


def validate_output(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            errors.append(f"Нет верхнеуровневого ключа: {key}")

    if not isinstance(data.get("success"), bool):
        errors.append("success должен быть bool")

    _validate_document(data.get("document"), errors)
    _validate_counterparties(data.get("counterparties"), errors)
    _validate_items(data.get("items"), errors)

    if not isinstance(data.get("warnings", []), list):
        errors.append("warnings должен быть списком")

    if not isinstance(data.get("meta", {}), dict):
        errors.append("meta должен быть объектом")

    return errors


def _validate_document(document: Any, errors: List[str]) -> None:
    if not isinstance(document, dict):
        errors.append("document должен быть объектом")
        return

    for key in REQUIRED_DOCUMENT:
        _validate_field_value(document.get(key), f"document.{key}", errors)


def _validate_counterparties(counterparties: Any, errors: List[str]) -> None:
    if not isinstance(counterparties, list):
        errors.append("counterparties должен быть списком")
        return

    for idx, party in enumerate(counterparties):
        if not isinstance(party, dict):
            errors.append(f"counterparties[{idx}] должен быть объектом")
            continue

        for key in REQUIRED_PARTY_FIELDS:
            _validate_field_value(party.get(key), f"counterparties[{idx}].{key}", errors)

        if "role" not in party:
            errors.append(f"counterparties[{idx}].role отсутствует")


def _validate_items(items: Any, errors: List[str]) -> None:
    if not isinstance(items, list):
        errors.append("items должен быть списком")
        return

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"items[{idx}] должен быть объектом")
            continue

        for key in REQUIRED_ITEM_FIELDS:
            _validate_field_value(item.get(key), f"items[{idx}].{key}", errors)


def _validate_field_value(field: Any, path: str, errors: List[str]) -> None:
    if not isinstance(field, dict):
        errors.append(f"{path} должен быть FieldValue-объектом")
        return

    for key in REQUIRED_FIELD_KEYS:
        if key not in field:
            errors.append(f"{path}.{key} отсутствует")

    confidence = field.get("confidence")
    if not isinstance(confidence, (int, float)):
        errors.append(f"{path}.confidence должен быть числом")
    elif not 0 <= confidence <= 1:
        errors.append(f"{path}.confidence должен быть в диапазоне 0..1")


def main() -> int:
    if len(sys.argv) != 2:
        print("Использование: python tools/validate_output.py examples/demo_result.json")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Файл не найден: {path}")
        return 2

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Некорректный JSON: {exc}")
        return 1

    errors = validate_output(data)
    if errors:
        print("❌ JSON не прошёл проверку:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("✅ JSON соответствует расширенной схеме")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
