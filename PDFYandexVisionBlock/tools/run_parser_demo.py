"""
tools/run_parser_demo.py

Локальное демо без Puzzle RPA и без Yandex Vision.
Нужно Максиму С, чтобы показывать свою часть независимо от остальных.

Запуск:
    python tools/run_parser_demo.py
    python tools/validate_output.py examples/demo_result.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.parser import parse_requisites


SAMPLE_TEXT = """
Счёт на оплату № ABC-123 от 22.05.2026

Поставщик: ООО «Ромашка» ИНН 7701234567 КПП 770101001
Покупатель: ООО «Василек» ИНН 7812345678 КПП 781201001

№ Наименование Кол-во Ед. Цена Сумма
1 Услуга разработки 2 шт 10 000,00 20 000,00
2 Поддержка проекта 1 усл 5 500,50 5 500,50

Итого к оплате: 25 500,50 руб.
"""


def main() -> None:
    result = parse_requisites(SAMPLE_TEXT)
    output = Path("examples/demo_result.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nСохранено: {output}")


if __name__ == "__main__":
    main()
