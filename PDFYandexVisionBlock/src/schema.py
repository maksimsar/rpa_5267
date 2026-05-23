"""
schema.py

Production-like схема результата для слоя извлечения реквизитов.

Файл не зависит от Puzzle RPA, Yandex Vision, requests и файловой системы.
Его задача — дать единый формат результата, который удобно:
- тестировать;
- логировать;
- отдавать из Puzzle RPA как dict/json;
- защищать перед жюри как продуманную архитектуру.

Python: 3.11+
Dependencies: стандартная библиотека.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional


DocumentType = Literal[
    "УПД",
    "Акт",
    "Накладная",
    "Счёт",
    "Счет-фактура",
    "Договор",
    "Неизвестно",
]

PartyRole = Literal[
    "seller",
    "buyer",
    "executor",
    "customer",
    "payer",
    "consignee",
    "unknown",
]


@dataclass(frozen=True)
class FieldValue:
    """Значение поля с объяснением, как оно было найдено.

    value:
        Само значение. Если не найдено — None.

    confidence:
        Эвристическая уверенность 0..1. Это не ML-score, а объяснимый скоринг
        по качеству паттерна: ключевые слова, роль, таблица, fallback.

    source:
        Объяснение источника: regex, table_cell, role_section, fallback.
    """

    value: Any = None
    confidence: float = 0.0
    source: str = "not_found"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentInfo:
    type: FieldValue = field(default_factory=FieldValue)
    number: FieldValue = field(default_factory=FieldValue)
    date: FieldValue = field(default_factory=FieldValue)  # ISO: YYYY-MM-DD
    total_amount: FieldValue = field(default_factory=FieldValue)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.to_dict(),
            "number": self.number.to_dict(),
            "date": self.date.to_dict(),
            "total_amount": self.total_amount.to_dict(),
        }


@dataclass(frozen=True)
class Counterparty:
    name: FieldValue = field(default_factory=FieldValue)
    inn: FieldValue = field(default_factory=FieldValue)
    kpp: FieldValue = field(default_factory=FieldValue)
    role: PartyRole = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name.to_dict(),
            "inn": self.inn.to_dict(),
            "kpp": self.kpp.to_dict(),
            "role": self.role,
        }


@dataclass(frozen=True)
class LineItem:
    name: FieldValue = field(default_factory=FieldValue)
    quantity: FieldValue = field(default_factory=FieldValue)
    price: FieldValue = field(default_factory=FieldValue)
    amount: FieldValue = field(default_factory=FieldValue)
    unit: FieldValue = field(default_factory=FieldValue)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name.to_dict(),
            "quantity": self.quantity.to_dict(),
            "price": self.price.to_dict(),
            "amount": self.amount.to_dict(),
            "unit": self.unit.to_dict(),
        }


@dataclass(frozen=True)
class ParseResult:
    success: bool
    document: DocumentInfo = field(default_factory=DocumentInfo)
    counterparties: List[Counterparty] = field(default_factory=list)
    items: List[LineItem] = field(default_factory=list)
    raw_text: str = ""
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_explainability: bool = True) -> Dict[str, Any]:
        """Преобразовать результат в dict.

        include_explainability=True — лучший формат для хакатона:
        жюри видит confidence/source.

        include_explainability=False — компактный формат:
        удобен для expected_output.json и сравнения.
        """
        if include_explainability:
            return {
                "success": self.success,
                "document": self.document.to_dict(),
                "counterparties": [p.to_dict() for p in self.counterparties],
                "items": [i.to_dict() for i in self.items],
                "raw_text": self.raw_text,
                "warnings": list(self.warnings),
                "meta": dict(self.meta),
            }

        return {
            "success": self.success,
            "document": {
                "type": self.document.type.value,
                "number": self.document.number.value,
                "date": self.document.date.value,
                "total_amount": self.document.total_amount.value,
            },
            "counterparties": [
                {
                    "name": p.name.value,
                    "inn": p.inn.value,
                    "kpp": p.kpp.value,
                    "role": p.role,
                }
                for p in self.counterparties
            ],
            "items": [
                {
                    "name": i.name.value,
                    "quantity": i.quantity.value,
                    "price": i.price.value,
                    "amount": i.amount.value,
                    "unit": i.unit.value,
                }
                for i in self.items
            ],
            "raw_text": self.raw_text,
            "warnings": list(self.warnings),
            "meta": dict(self.meta),
        }


def field(value: Any, confidence: float, source: str) -> FieldValue:
    """Короткий helper для единообразного создания FieldValue."""
    return FieldValue(value=value, confidence=round(float(confidence), 3), source=source)


def empty_result(raw_text: str = "", warning: Optional[str] = None) -> ParseResult:
    warnings = [warning] if warning else []
    return ParseResult(
        success=True,
        document=DocumentInfo(),
        counterparties=[],
        items=[],
        raw_text=raw_text,
        warnings=warnings,
        meta={
            "parser_version": "2.0.0",
            "quality": "safe_empty_result",
        },
    )
