"""
parser.py

Автономный слой парсинга OCR-результата.

Главная идея:
- parse_requisites(...) возвращает explainable-формат для тестов и архитектуры:
  {"value": ..., "confidence": ..., "source": ...}
- parse_requisites_simple(...) возвращает компактный формат для Puzzle RPA.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


PARSER_VERSION = "4.0.0"


def _field(value: Any = None, confidence: float = 0.0, source: str = "not_found") -> Dict[str, Any]:
    return {
        "value": value,
        "confidence": round(float(confidence), 3),
        "source": source,
    }


def parse_requisites(vision_response: Dict[str, Any] | str | None) -> Dict[str, Any]:
    """
    Возвращает explainable-формат:
    каждое значимое поле лежит в {"value", "confidence", "source"}.

    Этот формат ждут unit-тесты и он удобен для защиты:
    можно объяснить, как именно найдено поле.
    """
    compact = parse_requisites_simple(vision_response)
    return make_explainable_result(compact)


def parse_requisites_simple(vision_response: Dict[str, Any] | str | None) -> Dict[str, Any]:
    """
    Возвращает компактный формат для Puzzle RPA:
    document.type -> "Счёт", а не {"value": "Счёт", ...}.
    """
    raw_text = extract_text_from_vision_response(vision_response)
    table_rows = extract_table_rows_from_vision_response(vision_response)
    parsed = parse_text(raw_text, table_rows=table_rows)

    return {
        "success": True,
        **parsed,
        "meta": {
            "parser_version": PARSER_VERSION,
            "raw_text_length": len(raw_text or ""),
            "items_count": len(parsed.get("items", [])),
            "counterparties_count": len(parsed.get("counterparties", [])),
        },
    }


class ParserResult(dict):
    """
    Совместимость с кодом, который мог ждать .to_dict().
    """
    def to_dict(self, include_explainability: bool = True) -> Dict[str, Any]:
        if include_explainability:
            return dict(self)

        return make_compact_from_explainable(dict(self))


def parse_requisites_result(vision_response: Dict[str, Any] | str | None) -> ParserResult:
    return ParserResult(parse_requisites(vision_response))


def make_explainable_result(compact: Dict[str, Any]) -> Dict[str, Any]:
    document = compact.get("document") or {}

    explainable_counterparties = []

    for party in compact.get("counterparties", []):
        explainable_counterparties.append(
            {
                "name": _field(
                    party.get("name"),
                    0.85 if party.get("name") else 0.0,
                    "role_section" if party.get("name") else "not_found",
                ),
                "inn": _field(
                    party.get("inn"),
                    0.95 if party.get("inn") else 0.0,
                    "inn_regex" if party.get("inn") else "not_found",
                ),
                "kpp": _field(
                    party.get("kpp"),
                    0.95 if party.get("kpp") else 0.0,
                    "kpp_regex" if party.get("kpp") else "not_found",
                ),
                "role": party.get("role") or "unknown",
            }
        )

    explainable_items = []

    for item in compact.get("items", []):
        explainable = {
            "name": _field(
                item.get("name"),
                0.85 if item.get("name") else 0.0,
                "table_or_line_item",
            ),
            "quantity": _field(
                item.get("quantity"),
                0.85 if item.get("quantity") is not None else 0.0,
                "table_or_line_item",
            ),
            "price": _field(
                item.get("price"),
                0.85 if item.get("price") is not None else 0.0,
                "table_or_line_item",
            ),
            "amount": _field(
                item.get("amount"),
                0.85 if item.get("amount") is not None else 0.0,
                "table_or_line_item",
            ),
            "unit": _field(
                item.get("unit"),
                0.8 if item.get("unit") else 0.0,
                "table_or_line_item",
            ),
        }

        if "position" in item:
            explainable["position"] = item["position"]

        explainable_items.append(explainable)

    return {
        "success": bool(compact.get("success", True)),
        "document": {
            "type": _field(
                document.get("type"),
                0.9 if document.get("type") else 0.0,
                "document_type_regex" if document.get("type") else "not_found",
            ),
            "number": _field(
                document.get("number"),
                0.9 if document.get("number") else 0.0,
                "document_number_regex" if document.get("number") else "not_found",
            ),
            "date": _field(
                document.get("date"),
                0.9 if document.get("date") else 0.0,
                "date_regex" if document.get("date") else "not_found",
            ),
            "total_amount": _field(
                document.get("total_amount"),
                0.9 if document.get("total_amount") is not None else 0.0,
                "amount_regex" if document.get("total_amount") is not None else "not_found",
            ),
        },
        "counterparties": explainable_counterparties,
        "items": explainable_items,
        "raw_text": (
            compact.get("raw_text", {}).get("preview", "")
            if isinstance(compact.get("raw_text"), dict)
            else compact.get("raw_text", "")
        ),
        "warnings": list(compact.get("warnings", [])),
        "meta": dict(compact.get("meta", {})),
    }


def make_compact_from_explainable(explainable: Dict[str, Any]) -> Dict[str, Any]:
    def value(obj: Any) -> Any:
        if isinstance(obj, dict) and "value" in obj:
            return obj.get("value")
        return obj

    document = explainable.get("document", {})

    return {
        "success": explainable.get("success", True),
        "document": {
            "type": value(document.get("type")),
            "number": value(document.get("number")),
            "date": value(document.get("date")),
            "total_amount": value(document.get("total_amount")),
        },
        "counterparties": [
            {
                "role": party.get("role"),
                "name": value(party.get("name")),
                "inn": value(party.get("inn")),
                "kpp": value(party.get("kpp")),
            }
            for party in explainable.get("counterparties", [])
        ],
        "items": [
            {
                **({"position": item.get("position")} if item.get("position") is not None else {}),
                "name": value(item.get("name")),
                "quantity": value(item.get("quantity")),
                "unit": value(item.get("unit")),
                "price": value(item.get("price")),
                "amount": value(item.get("amount")),
            }
            for item in explainable.get("items", [])
        ],
        "raw_text": explainable.get("raw_text", ""),
        "warnings": list(explainable.get("warnings", [])),
        "meta": dict(explainable.get("meta", {})),
    }


def extract_text_from_vision_response(vision_response: Dict[str, Any] | str | None) -> str:
    if vision_response is None:
        return ""

    if isinstance(vision_response, str):
        return normalize_text(vision_response)

    if not isinstance(vision_response, dict):
        return ""

    if isinstance(vision_response.get("result"), dict):
        inner_text = extract_text_from_vision_response(vision_response["result"])
        if inner_text:
            return inner_text

    full_texts = _collect_values_by_keys(
        vision_response,
        {"fullText", "full_text", "fullTextAnnotation", "full_text_annotation"},
    )
    full_texts = [extract_text_value(value) for value in full_texts]
    full_texts = [value for value in full_texts if _looks_like_text(value)]

    if full_texts:
        return normalize_text(max(full_texts, key=len))

    line_texts = _collect_line_texts(vision_response)

    if line_texts:
        return normalize_text("\n".join(_unique_preserve_order(line_texts)))

    generic_texts = _collect_values_by_keys(vision_response, {"text"})
    generic_texts = [extract_text_value(value) for value in generic_texts]
    generic_texts = [value for value in generic_texts if _looks_like_text(value)]

    if generic_texts:
        return normalize_text("\n".join(_unique_preserve_order(generic_texts)))

    word_texts = _collect_word_texts(vision_response)

    if word_texts:
        return normalize_text(" ".join(word_texts))

    return ""


def extract_text_value(value: Any) -> str:
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        for key in ("text", "fullText", "full_text"):
            if isinstance(value.get(key), str):
                return value[key]

    return ""


def extract_table_rows_from_vision_response(vision_response: Dict[str, Any] | str | None) -> List[List[str]]:
    """
    Достаёт таблицы из JSON вида:
    {"tables": [{"cells": [{"rowIndex": 0, "columnIndex": 0, "text": "..."}]}]}.
    """
    if not isinstance(vision_response, dict):
        return []

    tables = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            maybe_tables = obj.get("tables")

            if isinstance(maybe_tables, list):
                tables.extend(table for table in maybe_tables if isinstance(table, dict))

            for value in obj.values():
                if isinstance(value, (dict, list)):
                    walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(vision_response)

    all_rows: List[List[str]] = []

    for table in tables:
        cells = table.get("cells")

        if not isinstance(cells, list):
            continue

        grid: Dict[int, Dict[int, str]] = {}

        for cell in cells:
            if not isinstance(cell, dict):
                continue

            row_index = cell.get("rowIndex", cell.get("row_index", cell.get("row")))
            col_index = cell.get("columnIndex", cell.get("column_index", cell.get("column")))

            try:
                row_index = int(row_index)
                col_index = int(col_index)
            except (TypeError, ValueError):
                continue

            text = extract_text_value(cell.get("text", cell))
            text = normalize_single_line(text)

            grid.setdefault(row_index, {})[col_index] = text

        for row_index in sorted(grid):
            row_map = grid[row_index]
            max_col = max(row_map) if row_map else -1
            row = [row_map.get(col, "") for col in range(max_col + 1)]
            all_rows.append(row)

    return all_rows


def parse_text(raw_text: str, table_rows: Optional[List[List[str]]] = None) -> Dict[str, Any]:
    text = normalize_text(raw_text)
    flat = normalize_single_line(text)

    document = {
        "type": find_document_type(flat),
        "number": find_document_number(flat),
        "date": find_document_date(flat),
        "total_amount": find_total_amount(flat),
    }

    counterparties = find_counterparties(flat)

    items = []

    if table_rows:
        items.extend(find_items_from_table_rows(table_rows))

    items.extend(find_items(text))
    items = deduplicate_items(items)

    warnings = build_warnings(document, counterparties, items)

    return {
        "document": document,
        "counterparties": counterparties,
        "items": items,
        "raw_text": format_raw_text(text),
        "warnings": warnings,
    }


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\u00a0", " ")
    text = text.replace("\u202f", " ")
    text = text.replace("\\n", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = []

    for line in text.split("\n"):
        cleaned = re.sub(r"[ \t]+", " ", line).strip()

        if cleaned:
            lines.append(cleaned)

    return "\n".join(lines)


def normalize_single_line(text: str) -> str:
    text = normalize_text(text)
    return re.sub(r"\s+", " ", text).strip()


def format_raw_text(text: str, max_lines: int = 120) -> Dict[str, Any]:
    text = normalize_text(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    preview = re.sub(r"\s+", " ", " ".join(lines)).strip()

    return {
        "preview": preview[:1500],
        "lines": lines[:max_lines],
        "line_count": len(lines),
        "truncated": len(lines) > max_lines,
    }


def find_document_type(flat: str) -> Optional[str]:
    search = flat.lower()

    patterns = [
        ("Счет-фактура", r"\bсч[её]т[\s-]*фактура\b"),
        ("УПД", r"\b(упд|универсальный передаточный документ)\b"),
        ("Накладная", r"\b(накладная|товарная накладная|торг-?12)\b"),
        ("Акт", r"\bакт\b"),
        ("Договор", r"\b(договор|contract|agreement)\b"),
        ("Счёт", r"\b(сч[её]т|счет на оплату)\b"),
        ("Invoice", r"\b(invoice|commercial invoice|tax invoice)\b"),
    ]

    for label, pattern in patterns:
        if re.search(pattern, search, flags=re.IGNORECASE):
            return label

    return None


def find_document_number(flat: str) -> Optional[str]:
    search_area = flat[:1500]

    patterns = [
        r"(?:invoice\s*(?:number|no\.?|#)\s*[:\-]?\s*)([A-Za-z0-9_.\-\/\\]+)",
        r"(?:document\s*(?:number|no\.?|#)\s*[:\-]?\s*)([A-Za-z0-9_.\-\/\\]+)",
        r"(?:номер\s*(?:документа)?\s*[:\-]?\s*)([A-Za-zА-Яа-я0-9_.\-\/\\]+)",
        r"(?:№|n[oо]?\.?)\s*([A-Za-zА-Яа-я0-9_.\-\/\\]+)",
        r"(?:сч[её]т|invoice|акт|накладная|договор|упд).{0,100}?(?:№|n[oо]?\.?|number|#)\s*[:\-]?\s*([A-Za-zА-Яа-я0-9_.\-\/\\]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, search_area, flags=re.IGNORECASE)

        if not match:
            continue

        number = clean_document_number(match.group(1))

        if not number:
            continue

        if re.fullmatch(r"\d{10,12}", number):
            continue

        if re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", number):
            continue

        if len(number) > 50:
            continue

        return number

    return None


def clean_document_number(value: str) -> Optional[str]:
    if not value:
        return None

    value = value.strip().replace("\\", "/")
    value = value.strip(".,;:()[]{}<>")
    value = re.sub(r"\s*(?:от|date|dated)$", "", value, flags=re.IGNORECASE).strip()

    return value or None


def find_document_date(flat: str) -> Optional[str]:
    search_area = flat[:1800]

    month_pattern = (
        r"[«\"]?(\d{1,2})[»\"]?\s*"
        r"(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
        r"\s*(\d{4})"
    )

    match = re.search(month_pattern, search_area, flags=re.IGNORECASE)

    if match:
        return normalize_date_from_parts(match.group(1), month_to_number(match.group(2)), match.group(3))

    patterns = [
        r"(?:invoice\s*date|document\s*date|date|дата|от)\s*[:\-]?\s*(\d{4}[./-]\d{1,2}[./-]\d{1,2})",
        r"(?:invoice\s*date|document\s*date|date|дата|от)\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        r"\b(\d{4}[./-]\d{1,2}[./-]\d{1,2})\b",
        r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, search_area, flags=re.IGNORECASE)

        if match:
            return normalize_date(match.group(1))

    return None


def month_to_number(month_name: str) -> str:
    months = {
        "января": "01",
        "февраля": "02",
        "марта": "03",
        "апреля": "04",
        "мая": "05",
        "июня": "06",
        "июля": "07",
        "августа": "08",
        "сентября": "09",
        "октября": "10",
        "ноября": "11",
        "декабря": "12",
    }

    return months.get(month_name.lower(), "01")


def normalize_date_from_parts(day: str, month: str, year: str) -> str:
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def normalize_date(value: str) -> str:
    value = value.strip().replace("/", ".").replace("-", ".")
    parts = value.split(".")

    if len(parts) != 3:
        return value

    if len(parts[0]) == 4:
        year = parts[0]
        month = parts[1].zfill(2)
        day = parts[2].zfill(2)
    else:
        day = parts[0].zfill(2)
        month = parts[1].zfill(2)
        year = parts[2]

        if len(year) == 2:
            year = "20" + year

    return f"{year}-{month}-{day}"


def find_total_amount(flat: str) -> Optional[float]:
    rub_kop_patterns = [
        r"(?:итого|всего|сумма|к оплате).{0,80}?([0-9][0-9\s\u00a0\u202f]*)\s*руб\.?\s*(\d{1,2})\s*коп",
        r"(?:итого|всего|сумма|к оплате).{0,80}?([0-9][0-9\s\u00a0\u202f]*)-(\d{1,2})\b",
    ]

    for pattern in rub_kop_patterns:
        match = re.search(pattern, flat, flags=re.IGNORECASE)

        if match:
            whole = re.sub(r"\s+", "", match.group(1))
            cents = match.group(2).zfill(2)
            return parse_amount(f"{whole}.{cents}")

    priority_patterns = [
        r"(?:grand\s*total|total\s*amount|total\s*due|amount\s*due|invoice\s*total)\s*[:\-]?\s*(?:USD|EUR|RUB|₽|\$)?\s*([0-9][0-9\s\u00a0\u202f,.]*[,.]\d{2}|[0-9]+)",
        r"(?:итого\s*к\s*оплате|всего\s*к\s*оплате|сумма\s*к\s*оплате|на\s*сумму)\s*[:\-]?\s*([0-9][0-9\s\u00a0\u202f,.]*[,.]\d{2}|[0-9]+)",
        r"(?:итого\s*с\s*ндс|итого\s*без\s*ндс|всего\s*без\s*ндс|итого|всего|сумма)\s*[:\-]?\s*([0-9][0-9\s\u00a0\u202f,.]*[,.]\d{2}|[0-9]+)",
        r"(?:total|subtotal)\s*[:\-]?\s*(?:USD|EUR|RUB|₽|\$)?\s*([0-9][0-9\s\u00a0\u202f,.]*[,.]\d{2}|[0-9]+)",
    ]

    candidates = []

    for pattern in priority_patterns:
        for match in re.finditer(pattern, flat, flags=re.IGNORECASE):
            amount = parse_amount(match.group(1))

            if amount is not None:
                candidates.append(amount)

    if candidates:
        return max(candidates)

    cleaned = remove_dates_and_ids_for_amount_fallback(flat)
    numbers = re.findall(r"\b([0-9]+(?:[,.]\d{1,2})?)\b", cleaned)

    values = [parse_amount(value) for value in numbers]
    values = [value for value in values if value is not None and value > 0]

    if values:
        return max(values)

    return None


def remove_dates_and_ids_for_amount_fallback(flat: str) -> str:
    text = re.sub(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", " ", flat)
    text = re.sub(r"\b\d{4}[./-]\d{1,2}[./-]\d{1,2}\b", " ", text)
    text = re.sub(r"\b\d{9,12}\b", " ", text)

    return text


def parse_amount(value: str) -> Optional[float]:
    if value is None:
        return None

    value = str(value)
    value = value.replace("\u00a0", " ").replace("\u202f", " ")
    value = re.sub(r"(USD|EUR|RUB|руб\.?|рублей|рубля|р\.|₽|\$)", "", value, flags=re.IGNORECASE)
    value = value.strip()
    value = re.sub(r"(?<=\d)-(?=\d{1,2}\b)", ".", value)

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")

    elif "," in value and "." not in value:
        if re.search(r",\d{1,2}$", value):
            value = value.replace(",", ".")
        else:
            value = value.replace(",", "")

    elif "." in value and "," not in value:
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", value):
            value = value.replace(".", "")

    value = value.replace(" ", "")
    value = re.sub(r"[^0-9.\-]", "", value)

    if not value or value in ("-", ".", "-."):
        return None

    try:
        return float(value)
    except ValueError:
        return None


def find_counterparties(flat: str) -> List[Dict[str, Any]]:
    role_specs = [
        ("seller", ["Поставщик", "Продавец", "Supplier", "Vendor", "Seller", "Provider"]),
        ("buyer", ["Покупатель", "Buyer", "Customer", "Client", "Bill To"]),
        ("executor", ["Исполнитель", "Contractor", "Executor"]),
        ("customer", ["Заказчик", "Customer"]),
    ]

    stop_labels = [
        "Поставщик",
        "Продавец",
        "Покупатель",
        "Исполнитель",
        "Заказчик",
        "Supplier",
        "Vendor",
        "Seller",
        "Buyer",
        "Customer",
        "Client",
        "Bill To",
        "Ship To",
        "Items",
        "Table",
        "Основание",
        "Назначение",
        "Итого",
        "Всего",
        "Total",
        "Subtotal",
    ]

    parties = []

    for role, labels in role_specs:
        section = find_role_section(flat, labels=labels, stop_labels=stop_labels)

        if not section:
            continue

        name = clean_org_name(extract_name_from_section(section))
        inn = find_inn_in_section(section)
        kpp = find_kpp_in_section(section)

        if name or inn or kpp:
            parties.append(
                {
                    "role": role,
                    "name": name,
                    "inn": inn,
                    "kpp": kpp,
                }
            )

    if parties:
        return fill_missing_party_ids(deduplicate_counterparties(parties), flat)

    org_entries = find_org_entries(flat)

    if org_entries:
        roles = ["seller", "buyer"]
        result = []

        for index, entry in enumerate(org_entries[:2]):
            result.append(
                {
                    "role": roles[index] if index < len(roles) else "unknown",
                    "name": entry.get("name"),
                    "inn": entry.get("inn"),
                    "kpp": entry.get("kpp"),
                }
            )

        return result

    all_inns = find_all_inn(flat)
    all_kpps = find_all_kpp(flat)

    result = []

    if all_inns or all_kpps:
        roles = ["seller", "buyer"]
        count = max(len(all_inns), len(all_kpps), 1)

        for index in range(min(count, 2)):
            result.append(
                {
                    "role": roles[index] if index < len(roles) else "unknown",
                    "name": None,
                    "inn": all_inns[index] if index < len(all_inns) else None,
                    "kpp": all_kpps[index] if index < len(all_kpps) else None,
                }
            )

    if not result:
        result.append(
            {
                "role": "unknown",
                "name": None,
                "inn": None,
                "kpp": None,
            }
        )

    return result


def find_role_section(flat: str, labels: List[str], stop_labels: List[str], max_len: int = 600) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(label) for label in stop_labels if label not in labels)

    match = re.search(rf"\b(?:{label_pattern})\b\s*[:\-]?\s*", flat, flags=re.IGNORECASE)

    if not match:
        return ""

    start = match.end()
    end = min(len(flat), start + max_len)

    stop_match = re.search(rf"\b(?:{stop_pattern})\b\s*[:\-]?", flat[start:end], flags=re.IGNORECASE)

    if stop_match:
        end = start + stop_match.start()

    return flat[start:end].strip()


def extract_name_from_section(section: str) -> Optional[str]:
    if not section:
        return None

    section = section.strip()

    cut_patterns = [
        r"\bИНН\b",
        r"\bКПП\b",
        r"\bINN\b",
        r"\bKPP\b",
        r"\bTax\s*ID\b",
        r"\bAddress\b",
        r"\bАдрес\b",
        r"\bпоставщика\b",
        r"\bпокупателя\b",
        r"\bSupplier\s*INN\b",
        r"\bBuyer\s*INN\b",
        r"\bCustomer\s*INN\b",
        r"\d{9,12}",
    ]

    cut_at = len(section)

    for pattern in cut_patterns:
        match = re.search(pattern, section, flags=re.IGNORECASE)

        if match:
            cut_at = min(cut_at, match.start())

    name = section[:cut_at].strip(" :-,;")

    if not name:
        org_match = re.search(
            r"((?:ООО|АО|ПАО|ЗАО|ОАО|ИП|LLC|Ltd\.?|Limited|Inc\.?|Corp\.?|Company)\s+[^,;:]{2,120})",
            section,
            flags=re.IGNORECASE,
        )

        if org_match:
            name = org_match.group(1)

    return name or None


def clean_org_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None

    name = str(name)
    name = name.replace('\\"', '"').replace("\\'", "'")
    name = name.replace("«", "").replace("»", "")
    name = name.replace('"', "").replace("'", "").replace("`", "")

    name = re.sub(
        r"\b(?:поставщика|покупателя|supplier|buyer|customer|vendor|seller|provider)\s*[:\-]?",
        "",
        name,
        flags=re.IGNORECASE,
    )
    name = re.sub(r"\b(?:ИНН|КПП|INN|KPP|Tax\s*ID|Address|Адрес)\b.*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\d{6,}.*$", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(" ,;:-")

    return name or None


def find_org_entries(flat: str) -> List[Dict[str, Any]]:
    entries = []

    pattern = re.compile(
        r"((?:ООО|АО|ПАО|ЗАО|ОАО|ИП|LLC|Ltd\.?|Limited|Inc\.?|Corp\.?|Company)\s+.{2,80}?)"
        r"\s+(?:ИНН|INN|Tax\s*ID)\s*[:\-]?\s*((?:\d[\s]*){10,12})"
        r"(?:\s+(?:КПП|KPP)\s*[:\-]?\s*((?:\d[\s]*){9}))?",
        flags=re.IGNORECASE,
    )

    for match in pattern.finditer(flat):
        entries.append(
            {
                "name": clean_org_name(match.group(1)),
                "inn": normalize_digits(match.group(2)),
                "kpp": normalize_digits(match.group(3)) if match.group(3) else None,
            }
        )

    return entries


def fill_missing_party_ids(parties: List[Dict[str, Any]], flat: str) -> List[Dict[str, Any]]:
    """
    Дозаполняет ИНН/КПП только там, где это безопасно.

    Важно:
    - ИП / физлица с 12-значным ИНН обычно не имеют КПП;
    - нельзя брать первый найденный КПП из всего документа и лепить его первому контрагенту;
    - особенно нельзя присваивать КПП исполнителю, если это ИП.
    """
    all_inns = find_all_inn(flat)
    all_kpps = find_all_kpp(flat)

    used_inns = {party.get("inn") for party in parties if party.get("inn")}
    used_kpps = {party.get("kpp") for party in parties if party.get("kpp")}

    free_inns = [inn for inn in all_inns if inn not in used_inns]
    free_kpps = [kpp for kpp in all_kpps if kpp not in used_kpps]

    for party in parties:
        role = party.get("role")
        inn = party.get("inn")
        kpp = party.get("kpp")

        # Если у стороны уже есть ИНН и КПП, ничего не трогаем.
        if inn and kpp:
            continue

        # 12-значный ИНН обычно означает ИП/физлицо.
        # Для него КПП не подставляем из общего списка.
        is_individual_or_ip = bool(inn and len(str(inn)) == 12)

        if not inn and free_inns:
            party["inn"] = free_inns.pop(0)
            inn = party["inn"]
            is_individual_or_ip = bool(inn and len(str(inn)) == 12)

        if kpp:
            continue

        # Исполнителю с 12-значным ИНН КПП не нужен.
        if role == "executor" and is_individual_or_ip:
            party["kpp"] = None
            continue

        # Любой стороне с 12-значным ИНН КПП не навязываем.
        if is_individual_or_ip:
            party["kpp"] = None
            continue

        # КПП дозаполняем только юрлицам и только если есть свободный КПП.
        if free_kpps:
            party["kpp"] = free_kpps.pop(0)

    return parties


def find_all_inn(flat: str) -> List[str]:
    values = []

    pattern = r"\b(?:ИНН|INN|Tax\s*ID)\b[^\d]{0,40}((?:\d[\s]*){10,12})\b"

    for match in re.finditer(pattern, flat, flags=re.IGNORECASE):
        values.append(normalize_digits(match.group(1)))

    for match in re.finditer(r"\b((?:\d[\s]*){10,12})\b", flat):
        normalized = normalize_digits(match.group(1))

        if len(normalized) in (10, 12):
            values.append(normalized)

    return _unique_preserve_order(values)


def find_all_kpp(flat: str) -> List[str]:
    values = []

    pattern = r"\b(?:КПП|KPP)\b[^\d]{0,40}((?:\d[\s]*){9})\b"

    for match in re.finditer(pattern, flat, flags=re.IGNORECASE):
        values.append(normalize_digits(match.group(1)))

    for match in re.finditer(r"\b((?:\d[\s]*){9})\b", flat):
        normalized = normalize_digits(match.group(1))

        if len(normalized) == 9:
            values.append(normalized)

    return _unique_preserve_order(values)


def find_inn_in_section(section: str) -> Optional[str]:
    if not section:
        return None

    match = re.search(r"\b(?:ИНН|INN|Tax\s*ID)\b[^\d]{0,40}((?:\d[\s]*){10,12})\b", section, flags=re.IGNORECASE)

    if match:
        return normalize_digits(match.group(1))

    match = re.search(r"\b((?:\d[\s]*){10,12})\b", section)

    return normalize_digits(match.group(1)) if match else None


def find_kpp_in_section(section: str) -> Optional[str]:
    if not section:
        return None

    match = re.search(r"\b(?:КПП|KPP)\b[^\d]{0,40}((?:\d[\s]*){9})\b", section, flags=re.IGNORECASE)

    if match:
        return normalize_digits(match.group(1))

    match = re.search(r"\b((?:\d[\s]*){9})\b", section)

    return normalize_digits(match.group(1)) if match else None


def normalize_digits(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    digits = re.sub(r"\D", "", str(value))

    return digits or None


def deduplicate_counterparties(counterparties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    seen = set()

    for party in counterparties:
        key = (party.get("role"), party.get("inn"), party.get("kpp"), party.get("name"))

        if key in seen:
            continue

        seen.add(key)
        result.append(party)

    return result


def find_items_from_table_rows(rows: List[List[str]]) -> List[Dict[str, Any]]:
    if not rows:
        return []

    header_index = None
    header = []

    for index, row in enumerate(rows):
        joined = normalize_single_line(" ".join(row)).lower()

        if any(word in joined for word in ("наименование", "description", "item", "service")) and any(
            word in joined for word in ("сумма", "amount", "total")
        ):
            header_index = index
            header = [normalize_single_line(cell).lower() for cell in row]
            break

    if header_index is None:
        return []

    def find_col(*names: str) -> Optional[int]:
        for i, cell in enumerate(header):
            if any(name in cell for name in names):
                return i
        return None

    name_col = find_col("наименование", "description", "item", "service")
    qty_col = find_col("кол", "quantity", "qty")
    unit_col = find_col("ед", "unit")
    price_col = find_col("цена", "price")
    amount_col = find_col("сумма", "amount", "total")

    items = []

    for row in rows[header_index + 1:]:
        if not row or not any(cell.strip() for cell in row):
            continue

        name = clean_item_name(row[name_col]) if name_col is not None and name_col < len(row) else None

        if not name:
            continue

        if re.search(r"\b(?:итого|всего|total|subtotal)\b", name, flags=re.IGNORECASE):
            continue

        item = {
            "position": len(items) + 1,
            "name": name,
            "quantity": parse_quantity(row[qty_col]) if qty_col is not None and qty_col < len(row) else None,
            "unit": row[unit_col].strip() if unit_col is not None and unit_col < len(row) and row[unit_col].strip() else None,
            "price": parse_amount(row[price_col]) if price_col is not None and price_col < len(row) else None,
            "amount": parse_amount(row[amount_col]) if amount_col is not None and amount_col < len(row) else None,
        }

        items.append(item)

    return items


def find_items(text: str) -> List[Dict[str, Any]]:
    lines = [line.strip() for line in normalize_text(text).splitlines() if line.strip()]
    items = []
    buffer = ""

    for line in lines:
        if is_total_line(line):
            continue

        if buffer:
            merged = f"{buffer} {line}"
            item = parse_item_line(merged)

            if item:
                items.append(item)
                buffer = ""
                continue

        item = parse_item_line(line)

        if item:
            items.append(item)
            buffer = ""
            continue

        item = parse_item_without_row_number(line)

        if item:
            items.append(item)
            buffer = ""
            continue

        if re.match(r"^\s*\d+[.)]?\s+", line):
            buffer = line

    if items:
        return items

    flat = normalize_single_line(text)
    item = parse_item_without_row_number(flat)

    return [item] if item else []


def parse_item_line(line: str) -> Optional[Dict[str, Any]]:
    line = normalize_single_line(line)

    if not line or is_total_line(line):
        return None

    pattern_with_unit = re.compile(
        r"^\s*(\d+)[.)]?\s+"
        r"(.{3,140}?)\s+"
        r"(?:(\d+(?:[,.]\d+)?)\s+)?"
        r"(шт|усл|ед|pcs|piece|pieces|service|services|hour|hours)\.?\s+"
        r"([0-9][0-9\s\u00a0\u202f,.]*(?:[,.]\d{2})|[0-9]+)\s+"
        r"([0-9][0-9\s\u00a0\u202f,.]*(?:[,.]\d{2})|[0-9]+)\s*$",
        flags=re.IGNORECASE,
    )

    match = pattern_with_unit.search(line)

    if match:
        name = clean_item_name(match.group(2))

        if not name:
            return None

        return {
            "position": int(match.group(1)),
            "name": name,
            "quantity": parse_quantity(match.group(3)) if match.group(3) else None,
            "unit": match.group(4).strip().strip("."),
            "price": parse_amount(match.group(5)),
            "amount": parse_amount(match.group(6)),
        }

    pattern_no_unit = re.compile(
        r"^\s*(\d+)[.)]?\s+"
        r"(.{3,160}?)\s+"
        r"(\d+(?:[,.]\d+)?)\s+"
        r"([0-9][0-9\s\u00a0\u202f,.]*(?:[,.]\d{2})|[0-9]+)\s+"
        r"([0-9][0-9\s\u00a0\u202f,.]*(?:[,.]\d{2})|[0-9]+)\s*$",
        flags=re.IGNORECASE,
    )

    match = pattern_no_unit.search(line)

    if match:
        name = clean_item_name(match.group(2))

        if not name:
            return None

        return {
            "position": int(match.group(1)),
            "name": name,
            "quantity": parse_quantity(match.group(3)),
            "unit": None,
            "price": parse_amount(match.group(4)),
            "amount": parse_amount(match.group(5)),
        }

    return None


def parse_item_without_row_number(line: str) -> Optional[Dict[str, Any]]:
    if is_total_line(line):
        return None

    line = normalize_single_line(line)

    match = re.search(
        r"(.{3,120}?)\s+"
        r"(\d+(?:[,.]\d+)?)\s+"
        r"([0-9][0-9\s\u00a0\u202f,.]*(?:[,.]\d{2})|[0-9]+)\s+"
        r"([0-9][0-9\s\u00a0\u202f,.]*(?:[,.]\d{2})|[0-9]+)\s*$",
        line,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    name = clean_item_name(match.group(1))

    if not name:
        return None

    return {
        "position": 1,
        "name": name,
        "quantity": parse_quantity(match.group(2)),
        "unit": None,
        "price": parse_amount(match.group(3)),
        "amount": parse_amount(match.group(4)),
    }


def is_total_line(line: str) -> bool:
    return bool(re.search(r"\b(?:итого|всего|ндс|total|subtotal|amount due|grand total)\b", line, flags=re.IGNORECASE))


def clean_item_name(name: str) -> Optional[str]:
    if not name:
        return None

    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(" ,;:-")

    if len(name) < 2:
        return None

    return name


def parse_quantity(value: Optional[str]) -> Optional[float]:
    if not value:
        return None

    value = str(value).replace(",", ".")
    value = re.sub(r"[^0-9.\-]", "", value)

    if not value:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def deduplicate_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    seen = set()

    for item in items:
        key = (item.get("name"), item.get("quantity"), item.get("price"), item.get("amount"))

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def build_warnings(
    document: Dict[str, Any],
    counterparties: List[Dict[str, Any]],
    items: List[Dict[str, Any]],
) -> List[str]:
    warnings = []

    if not document.get("type"):
        warnings.append("Не удалось определить тип документа")

    if not document.get("number"):
        warnings.append("Не удалось определить номер документа")

    if not document.get("date"):
        warnings.append("Не удалось определить дату документа")

    if document.get("total_amount") is None:
        warnings.append("Не удалось определить итоговую сумму")

    if not counterparties or not any(party.get("inn") for party in counterparties):
        warnings.append("Не удалось определить ИНН контрагента")

    if not counterparties or not any(party.get("kpp") for party in counterparties):
        warnings.append("Не удалось определить КПП контрагента")

    if not items:
        warnings.append("Не удалось распознать табличные позиции")

    return warnings


def _collect_values_by_keys(obj: Any, keys: set) -> List[Any]:
    values = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in keys:
                    values.append(nested)

                if isinstance(nested, (dict, list)):
                    walk(nested)

        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(obj)

    return values


def _collect_line_texts(obj: Any) -> List[str]:
    lines = []

    def line_to_text(line: Any) -> Optional[str]:
        if isinstance(line, str):
            return line

        if isinstance(line, dict):
            if isinstance(line.get("text"), str):
                return line["text"]

            if isinstance(line.get("words"), list):
                words = []

                for word in line["words"]:
                    if isinstance(word, dict) and isinstance(word.get("text"), str):
                        words.append(word["text"])
                    elif isinstance(word, str):
                        words.append(word)

                if words:
                    return " ".join(words)

        return None

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            maybe_lines = value.get("lines")

            if isinstance(maybe_lines, list):
                for line in maybe_lines:
                    text = line_to_text(line)

                    if text:
                        lines.append(text)

            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    walk(nested)

        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(obj)

    return [normalize_single_line(line) for line in lines if normalize_single_line(line)]


def _collect_word_texts(obj: Any) -> List[str]:
    words = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            maybe_words = value.get("words")

            if isinstance(maybe_words, list):
                for word in maybe_words:
                    if isinstance(word, dict) and isinstance(word.get("text"), str):
                        words.append(word["text"])
                    elif isinstance(word, str):
                        words.append(word)

            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    walk(nested)

        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(obj)

    return [normalize_single_line(word) for word in words if normalize_single_line(word)]


def _looks_like_text(value: str) -> bool:
    return isinstance(value, str) and len(value.strip()) > 1


def _unique_preserve_order(items: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))