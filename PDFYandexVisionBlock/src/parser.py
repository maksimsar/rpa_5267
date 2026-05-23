"""
parser.py

Максимально автономный слой извлечения реквизитов:
Yandex Vision JSON / OCR text -> структурированный dict.

Ключевые идеи:
1. Safe-by-design: парсер не должен падать на пустых/битых данных.
2. Explainability: каждое поле имеет confidence/source.
3. Priority extraction: fullText -> lines -> words, чтобы не плодить дубли.
4. Fallback extraction: если нет таблиц в JSON, пытаемся разобрать строки текста.
5. Testability: нет HTTP, файловой системы и Puzzle RPA.

Python: 3.11+
Dependencies: стандартная библиотека.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from .normalizer import (
        amounts_close,
        normalize_amount,
        normalize_date,
        normalize_document_number,
        normalize_for_search,
        normalize_inn,
        normalize_kpp,
        normalize_org_name,
        normalize_single_line,
        normalize_text,
        normalize_unit,
    )
    from .schema import Counterparty, DocumentInfo, FieldValue, LineItem, ParseResult, field
except ImportError:
    from normalizer import (  # type: ignore
        amounts_close,
        normalize_amount,
        normalize_date,
        normalize_document_number,
        normalize_for_search,
        normalize_inn,
        normalize_kpp,
        normalize_org_name,
        normalize_single_line,
        normalize_text,
        normalize_unit,
    )
    from schema import Counterparty, DocumentInfo, FieldValue, LineItem, ParseResult, field  # type: ignore


PARSER_VERSION = "2.0.0"

DOC_TYPE_PATTERNS: Sequence[Tuple[str, str, float]] = (
    ("УПД", r"\b(?:упд|универсальн\w+\s+передаточн\w+\s+документ)\b", 0.97),
    ("Счет-фактура", r"\b(?:сч[её]т[\s-]*фактура)\b", 0.94),
    ("Счёт", r"\b(?:сч[её]т(?:\s+на\s+оплату)?)\b", 0.92),
    ("Акт", r"\b(?:акт(?:\s+выполненных\s+работ|\s+оказанных\s+услуг)?)\b", 0.9),
    ("Накладная", r"\b(?:товарная\s+накладная|накладная|торг-?12)\b", 0.9),
    ("Договор", r"\b(?:договор(?:\s+поставки|\s+оказания\s+услуг|\s+подряда)?)\b", 0.86),
)

NUMBER_PATTERNS: Sequence[Tuple[str, float]] = (
    (
        r"(?:№|n[oо]?\.?|номер(?:\s+документа)?)\s*[:\-]?\s*"
        r"([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9_.\-\/\\]*)",
        0.92,
    ),
    (
        r"(?:сч[её]т|акт|накладная|упд|договор|сч[её]т[\s-]*фактура)"
        r".{0,80}?\b(?:№|n[oо]?\.?|номер)\s*[:\-]?\s*"
        r"([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9_.\-\/\\]*)",
        0.9,
    ),
)

DATE_PATTERNS: Sequence[Tuple[str, float]] = (
    (r"(?:от|дата|дата\s+составления)\s*[:\-]?\s*((?:«?\d{1,2}»?\s+[а-яё]+\s+\d{2,4})|(?:\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})|(?:\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}))", 0.92),
    (r"\b(«?\d{1,2}»?\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{2,4}\s*(?:г\.?|года)?)\b", 0.86),
    (r"\b(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})\b", 0.78),
    (r"\b(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})\b", 0.78),
)

AMOUNT_VALUE = r"(?:-?\d[\d\s.]*-\d{2}|-?\d[\d\s.,]*(?:\s*(?:руб\.?|рублей|рубля|р\.?|₽)\s*\d{1,2}\s*(?:коп\.?|копеек|копейки|к\.?)?)?)"

AMOUNT_PATTERNS: Sequence[Tuple[str, float]] = (
    (rf"(?:итого\s+к\s+оплате|всего\s+к\s+оплате|сумма\s+к\s+оплате)\s*[:\-]?\s*({AMOUNT_VALUE})", 0.98),
    (rf"(?:итого\s+с\s+ндс|всего\s+с\s+ндс|итого\s+по\s+счету|итого\s+по\s+документу)\s*[:\-]?\s*({AMOUNT_VALUE})", 0.96),
    (rf"(?:всего\s+наименований\s+\d+\s*,?\s*на\s+сумму)\s*({AMOUNT_VALUE})", 0.95),
    (rf"(?:итого|всего|сумма)\s*[:\-]?\s*({AMOUNT_VALUE})", 0.88),
    (rf"(?:на\s+сумму)\s*[:\-]?\s*({AMOUNT_VALUE})", 0.78),
)

INN_PATTERN = re.compile(r"\b(?:ИНН|ИИН)\s*[:№\-]?\s*(\d[\d\s\-]{8,16}\d)\b", re.IGNORECASE)
KPP_PATTERN = re.compile(r"\b(?:КПП|KПП)\s*[:№\-]?\s*(\d[\d\s\-]{7,12}\d)\b", re.IGNORECASE)

ROLE_KEYWORDS: Dict[str, str] = {
    "поставщик": "seller",
    "продавец": "seller",
    "исполнитель": "executor",
    "подрядчик": "executor",
    "покупатель": "buyer",
    "заказчик": "customer",
    "плательщик": "payer",
    "грузополучатель": "consignee",
}

ROLE_WORDS = "|".join(sorted(ROLE_KEYWORDS, key=len, reverse=True))

MONEY_NUMBER_PATTERN = re.compile(
    r"(?<![\w./-])"
    r"-?\d{1,3}(?:[ \u00a0\u202f]\d{3})*(?:[,.]\d{1,2})?"
    r"|(?<![\w./-])-?\d+(?:[,.]\d{1,2})?",
    re.IGNORECASE,
)

ITEM_NUMBER_PATTERN = re.compile(
    r"(?<![\w./-])"
    r"(?:-?\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[,.]\d{1,2})|-?\d+(?:[,.]\d{1,2})?)"
    r"(?![\w./-])",
    re.IGNORECASE,
)

UNIT_PATTERN = re.compile(r"\b(шт\.?|усл\.?|ед\.?|кг|м2|м²|час(?:а|ов)?|компл\.?)\b", re.IGNORECASE)

HEADER_ALIASES = {
    "name": ("наименование", "товар", "работ", "услуг", "описание", "номенклатура"),
    "quantity": ("кол", "кол-во", "количество", "qty"),
    "unit": ("ед", "ед.", "единица", "единицы", "изм"),
    "price": ("цена", "price"),
    "amount": ("сумма", "стоимость", "amount", "итого"),
}


def parse_requisites(vision_response: Dict[str, Any] | str | None) -> Dict[str, Any]:
    """Публичная функция: результат с confidence/source."""
    return parse_requisites_result(vision_response).to_dict(include_explainability=True)


def parse_requisites_simple(vision_response: Dict[str, Any] | str | None) -> Dict[str, Any]:
    """Публичная функция: компактный результат без confidence/source."""
    return parse_requisites_result(vision_response).to_dict(include_explainability=False)


def parse_requisites_result(vision_response: Dict[str, Any] | str | None) -> ParseResult:
    raw_text = extract_text_from_vision_response(vision_response)
    text = normalize_text(raw_text)
    flat = normalize_single_line(text)

    document = DocumentInfo(
        type=_find_document_type(flat),
        number=_find_document_number(flat),
        date=_find_document_date(flat),
        total_amount=_find_total_amount(flat),
    )

    table_rows = extract_table_rows_from_vision_response(vision_response)
    counterparties = _find_counterparties(text)
    items = _find_items(text, table_rows=table_rows)
    warnings = _build_warnings(document, counterparties, items)

    return ParseResult(
        success=True,
        document=document,
        counterparties=counterparties,
        items=items,
        raw_text=text,
        warnings=warnings,
        meta={
            "parser_version": PARSER_VERSION,
            "items_count": len(items),
            "counterparties_count": len(counterparties),
            "table_rows_detected": len(table_rows),
            "input_kind": type(vision_response).__name__,
        },
    )


def extract_text_from_vision_response(vision_response: Dict[str, Any] | str | None) -> str:
    """Извлекает OCR-текст с приоритетом fullText -> line.text -> words.

    Это важно: если собрать вообще все ключи "text", появятся дубли
    fullText + строки + слова. Поэтому используются уровни приоритета.
    """
    if vision_response is None:
        return ""

    if isinstance(vision_response, str):
        return normalize_text(vision_response)

    if not isinstance(vision_response, dict):
        return ""

    full_texts = _collect_values_by_keys(vision_response, {"fullText", "full_text", "fullTextAnnotation"})
    full_texts = [t for t in full_texts if _looks_like_text(t)]

    if full_texts:
        # Берём самый длинный fullText: обычно это самый полный OCR.
        return normalize_text(max(full_texts, key=len))

    line_texts = _collect_line_texts(vision_response)
    if line_texts:
        return normalize_text("\n".join(_unique_preserve_order(line_texts)))

    word_texts = _collect_word_texts(vision_response)
    if word_texts:
        return normalize_text(" ".join(word_texts))

    generic_texts = _collect_values_by_keys(vision_response, {"text"})
    generic_texts = [t for t in generic_texts if _looks_like_text(t)]
    return normalize_text("\n".join(_unique_preserve_order(generic_texts)))


def extract_table_rows_from_vision_response(vision_response: Dict[str, Any] | str | None) -> List[List[str]]:
    """Пытается извлечь строки таблиц из произвольного JSON ответа.

    Поддерживает частые структуры:
    - {"tables": [{"rows": [{"cells": [{"text": "..."}]}]}]}
    - {"cells": [{"rowIndex": 0, "columnIndex": 1, "text": "..."}]}
    - snake_case варианты row_index/column_index.
    """
    if not isinstance(vision_response, dict):
        return []

    rows: List[List[str]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if isinstance(obj.get("rows"), list):
                parsed = _parse_rows_structure(obj.get("rows"))
                rows.extend(parsed)

            if isinstance(obj.get("cells"), list):
                parsed = _parse_cells_structure(obj.get("cells"))
                rows.extend(parsed)

            for value in obj.values():
                if isinstance(value, (dict, list)):
                    walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(vision_response)
    return [row for row in rows if any(cell.strip() for cell in row)]


def _collect_values_by_keys(obj: Any, keys: set[str]) -> List[str]:
    values: List[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in keys and isinstance(nested, str):
                    values.append(nested)
                elif key in keys and isinstance(nested, dict):
                    text = nested.get("text")
                    if isinstance(text, str):
                        values.append(text)
                if isinstance(nested, (dict, list)):
                    walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(obj)
    return values


def _collect_line_texts(obj: Any) -> List[str]:
    lines: List[str] = []

    def text_from_line(line: Any) -> Optional[str]:
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
                    text = text_from_line(line)
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
    words: List[str] = []

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


def _find_document_type(text: str) -> FieldValue:
    search = normalize_for_search(text)
    for label, pattern, confidence in DOC_TYPE_PATTERNS:
        if re.search(pattern, search, flags=re.IGNORECASE):
            return field(label, confidence, f"regex:{pattern}")
    return field(None, 0.0, "not_found")


def _find_document_number(text: str) -> FieldValue:
    search_area = text[:600]  # номер почти всегда в шапке
    candidates: List[Tuple[str, float, str, int]] = []

    for pattern, confidence in NUMBER_PATTERNS:
        for match in re.finditer(pattern, search_area, flags=re.IGNORECASE):
            raw = match.group(1)
            number = normalize_document_number(raw)
            if not number:
                continue

            # Отсекаем ИНН/КПП, даты и слишком длинные фрагменты.
            if normalize_inn(number) or normalize_kpp(number) or normalize_date(number):
                continue
            if len(number) > 40:
                continue

            candidates.append((number, confidence, f"regex:{pattern}", match.start()))

    if candidates:
        # Предпочитаем более ранний и более уверенный номер.
        candidates.sort(key=lambda x: (-x[1], x[3]))
        number, confidence, source, _ = candidates[0]
        return field(number, confidence, source)

    return field(None, 0.0, "not_found")


def _find_document_date(text: str) -> FieldValue:
    search_area = text[:1000]
    for pattern, confidence in DATE_PATTERNS:
        for match in re.finditer(pattern, search_area, flags=re.IGNORECASE):
            normalized = normalize_date(match.group(1))
            if normalized:
                return field(normalized, confidence, f"regex:{pattern}")
    return field(None, 0.0, "not_found")


def _find_total_amount(text: str) -> FieldValue:
    candidates: List[Tuple[float, float, str, int]] = []

    for pattern, confidence in AMOUNT_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            raw = match.group(1)
            amount = normalize_amount(raw)
            if amount is not None:
                candidates.append((amount, confidence, f"regex:{pattern}", match.start()))

    if candidates:
        # Приоритет: confidence, потом более поздняя строка, потом сумма.
        amount, confidence, source, _ = max(candidates, key=lambda x: (x[1], x[3], x[0]))
        return field(amount, confidence, source)

    # Fallback: выбираем максимальное простое число из документа, если ключи не найдены.
    # Здесь специально не считаем "100 200 300" одной суммой.
    money_values: List[float] = []
    fallback_number_pattern = re.compile(r"(?<![\w./-])-?\d+(?:[,.]\d{1,2})?(?![\w./-])")
    for match in fallback_number_pattern.finditer(text):
        value = normalize_amount(match.group(0))
        if value is not None and value > 0:
            money_values.append(value)

    if money_values:
        return field(max(money_values), 0.45, "fallback:max_money_like_number")

    return field(None, 0.0, "not_found")


def _find_counterparties(text: str) -> List[Counterparty]:
    parties: List[Counterparty] = []
    parties.extend(_find_counterparties_by_role_sections(text))

    if len(parties) < 2:
        parties.extend(_find_counterparties_by_inn_fallback(text, existing=parties))

    return _deduplicate_parties(parties)


def _find_counterparties_by_role_sections(text: str) -> List[Counterparty]:
    flat = normalize_single_line(text)
    parties: List[Counterparty] = []

    section_pattern = re.compile(
        rf"\b(?P<label>{ROLE_WORDS})\b\s*[:\-]?\s*"
        rf"(?P<body>.{{0,350}}?)"
        rf"(?=(?:\b(?:{ROLE_WORDS})\b\s*[:\-])|$)",
        flags=re.IGNORECASE,
    )

    for match in section_pattern.finditer(flat):
        label = match.group("label").lower()
        body = normalize_single_line(match.group("body"))
        role = ROLE_KEYWORDS.get(label, "unknown")

        inn_match = INN_PATTERN.search(body)
        kpp_match = KPP_PATTERN.search(body)

        inn = normalize_inn(inn_match.group(1)) if inn_match else None
        kpp = normalize_kpp(kpp_match.group(1)) if kpp_match else None

        name_fragment = body
        if inn_match:
            name_fragment = body[: inn_match.start()]
        name = _extract_org_name_from_fragment(name_fragment)

        if not inn and not name:
            continue

        parties.append(
            Counterparty(
                name=field(name, 0.78 if name else 0.0, f"role_section:{label}:name" if name else "not_found"),
                inn=field(inn, 0.97 if inn else 0.0, f"role_section:{label}:inn" if inn else "not_found"),
                kpp=field(kpp, 0.94 if kpp else 0.0, f"role_section:{label}:kpp" if kpp else "not_found"),
                role=role,  # type: ignore[arg-type]
            )
        )

    return parties


def _find_counterparties_by_inn_fallback(text: str, existing: Sequence[Counterparty]) -> List[Counterparty]:
    flat = normalize_single_line(text)
    existing_inns = {p.inn.value for p in existing if p.inn.value}

    inns = [(m.start(), m.end(), normalize_inn(m.group(1))) for m in INN_PATTERN.finditer(flat)]
    kpps = [(m.start(), m.end(), normalize_kpp(m.group(1))) for m in KPP_PATTERN.finditer(flat)]

    parties: List[Counterparty] = []

    for idx, (start, end, inn) in enumerate(inns):
        if not inn or inn in existing_inns:
            continue

        nearest_kpp = _nearest_value(start, kpps, max_distance=150)
        role = "seller" if idx == 0 else "buyer"
        name = _guess_org_name_before_position(flat, start)

        parties.append(
            Counterparty(
                name=field(name, 0.52 if name else 0.0, "fallback:context_before_inn" if name else "not_found"),
                inn=field(inn, 0.92, "fallback:regex_inn"),
                kpp=field(nearest_kpp, 0.78 if nearest_kpp else 0.0, "fallback:nearest_kpp" if nearest_kpp else "not_found"),
                role=role,  # type: ignore[arg-type]
            )
        )

    return parties


def _extract_org_name_from_fragment(fragment: str) -> Optional[str]:
    fragment = normalize_single_line(fragment)
    fragment = fragment.strip(" .,:;")

    # Убираем вводные слова, которые часто остаются в секции.
    fragment = re.sub(
        r"^(?:организация|наименование|контрагент)\s*[:\-]?\s*",
        "",
        fragment,
        flags=re.IGNORECASE,
    ).strip()

    patterns = [
        r"((?:ООО|АО|ПАО|ЗАО|ОАО|ИП)\s+[«\"']?[^,;:]{2,120})",
        r"((?:Общество\s+с\s+ограниченной\s+ответственностью)\s+[«\"']?[^,;:]{2,120})",
    ]

    for pattern in patterns:
        match = re.search(pattern, fragment, flags=re.IGNORECASE)
        if match:
            return normalize_org_name(match.group(1))

    return normalize_org_name(fragment)


def _guess_org_name_before_position(flat_text: str, position: int) -> Optional[str]:
    start = max(0, position - 220)
    fragment = flat_text[start:position]
    return _extract_org_name_from_fragment(fragment)


def _nearest_value(position: int, values: Iterable[Tuple[int, int, Optional[str]]], max_distance: int) -> Optional[str]:
    best: Tuple[int, Optional[str]] | None = None

    for start, end, value in values:
        if value is None:
            continue
        distance = min(abs(position - start), abs(position - end))
        if distance <= max_distance and (best is None or distance < best[0]):
            best = (distance, value)

    return best[1] if best else None


def _deduplicate_parties(parties: Sequence[Counterparty]) -> List[Counterparty]:
    result: List[Counterparty] = []
    seen: set[Tuple[Optional[str], str]] = set()

    for party in parties:
        key = (party.inn.value, party.role)
        if key in seen:
            continue
        seen.add(key)
        result.append(party)

    return result


def _find_items(text: str, table_rows: Sequence[Sequence[str]]) -> List[LineItem]:
    items: List[LineItem] = []

    items.extend(_find_items_from_table_rows(table_rows))
    existing_keys = {_item_key(item) for item in items}

    for item in _find_items_from_text(text):
        key = _item_key(item)
        if key not in existing_keys:
            items.append(item)
            existing_keys.add(key)

    return items


def _find_items_from_table_rows(table_rows: Sequence[Sequence[str]]) -> List[LineItem]:
    if not table_rows:
        return []

    items: List[LineItem] = []
    header_map: Optional[Dict[str, int]] = None

    for row in table_rows:
        clean_row = [normalize_single_line(cell) for cell in row]
        if not any(clean_row):
            continue

        maybe_header = _detect_header(clean_row)
        if maybe_header:
            header_map = maybe_header
            continue

        if header_map:
            item = _parse_item_from_mapped_row(clean_row, header_map)
            if item:
                items.append(item)
        else:
            # Если JSON дал строки без заголовка, собираем строку и используем text fallback.
            line = " ".join(clean_row)
            item = _parse_item_line(line)
            if item:
                items.append(item)

    return items


def _detect_header(row: Sequence[str]) -> Optional[Dict[str, int]]:
    lower = [cell.lower() for cell in row]
    mapping: Dict[str, int] = {}

    for logical_name, aliases in HEADER_ALIASES.items():
        for idx, cell in enumerate(lower):
            if any(alias in cell for alias in aliases):
                mapping[logical_name] = idx
                break

    if "name" in mapping and ("amount" in mapping or "price" in mapping):
        return mapping

    return None


def _parse_item_from_mapped_row(row: Sequence[str], mapping: Dict[str, int]) -> Optional[LineItem]:
    def get(name: str) -> Optional[str]:
        idx = mapping.get(name)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    name = normalize_single_line(get("name"))
    quantity = normalize_amount(get("quantity"))
    price = normalize_amount(get("price"))
    amount = normalize_amount(get("amount"))
    unit = normalize_unit(get("unit"))

    if not name or amount is None:
        return None

    confidence = _score_item(quantity, price, amount, base=0.88)

    return LineItem(
        name=field(name, confidence, "table_cells:name"),
        quantity=field(quantity, confidence if quantity is not None else 0.0, "table_cells:quantity" if quantity is not None else "not_found"),
        price=field(price, confidence if price is not None else 0.0, "table_cells:price" if price is not None else "not_found"),
        amount=field(amount, confidence, "table_cells:amount"),
        unit=field(unit, 0.8 if unit else 0.0, "table_cells:unit" if unit else "not_found"),
    )


def _find_items_from_text(text: str) -> List[LineItem]:
    lines = [
        normalize_single_line(line)
        for line in normalize_text(text).splitlines()
        if normalize_single_line(line)
    ]

    lines = [
        line
        for line in lines
        if not _looks_like_table_header(line) and not _looks_like_non_item_line(line)
    ]

    items: List[LineItem] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        item = _parse_item_line(line)

        # Multiline fallback: название на одной строке, числа на следующей.
        # Не склеиваем служебные строки документа с позициями.
        if item is None and i + 1 < len(lines):
            combined = f"{line} {lines[i + 1]}"
            item = _parse_item_line(combined)
            if item is not None:
                i += 1

        if item is not None:
            items.append(item)

        i += 1

    return items


def _parse_item_line(line: str) -> Optional[LineItem]:
    line = normalize_single_line(line)
    if not line:
        return None

    # Не парсим строки итогов как позиции.
    if re.search(r"\b(?:итого|всего|ндс|сумма\s+к\s+оплате|к\s+оплате)\b", line, flags=re.IGNORECASE):
        return None

    numeric_matches = list(ITEM_NUMBER_PATTERN.finditer(line))
    if len(numeric_matches) < 3:
        return None

    # Если первая цифра — номер строки, исключаем её.
    if numeric_matches and numeric_matches[0].start() <= 2 and len(numeric_matches) >= 4:
        numeric_matches = numeric_matches[1:]

    if len(numeric_matches) < 3:
        return None

    quantity_match, price_match, amount_match = numeric_matches[-3:]

    quantity = normalize_amount(quantity_match.group(0))
    price = normalize_amount(price_match.group(0))
    amount = normalize_amount(amount_match.group(0))

    if amount is None:
        return None

    name_fragment = line[: quantity_match.start()]
    name_fragment = re.sub(r"^\s*\d{1,3}[\).]?\s+", "", name_fragment)
    name = normalize_single_line(name_fragment).strip(" .,:;-")

    if not name or len(name) < 2:
        return None

    # Единица измерения обычно стоит между количеством и ценой.
    between_qty_price = line[quantity_match.end(): price_match.start()]
    unit_match = UNIT_PATTERN.search(between_qty_price)
    unit = normalize_unit(unit_match.group(1)) if unit_match else None

    confidence = _score_item(quantity, price, amount, base=0.78)

    return LineItem(
        name=field(name, confidence, "text_line:name"),
        quantity=field(quantity, confidence if quantity is not None else 0.0, "text_line:quantity" if quantity is not None else "not_found"),
        price=field(price, confidence if price is not None else 0.0, "text_line:price" if price is not None else "not_found"),
        amount=field(amount, confidence, "text_line:amount"),
        unit=field(unit, 0.66 if unit else 0.0, "text_line:unit" if unit else "not_found"),
    )


def _score_item(quantity: Optional[float], price: Optional[float], amount: Optional[float], base: float) -> float:
    if quantity is not None and price is not None and amount is not None:
        if amounts_close(quantity * price, amount, tolerance=max(0.03, amount * 0.01)):
            return min(0.97, base + 0.12)
        return max(0.5, base - 0.18)
    return base


def _looks_like_non_item_line(line: str) -> bool:
    lower = line.lower()

    # Строки шапки документа и контрагентов не должны становиться товарными позициями.
    # Важно: ищем по словам, иначе "разработки" содержит "акт" и ошибочно отсекается.
    if re.search(r"\b(?:сч[её]т|счет|акт|накладная|договор|упд|счет-фактура)\b", lower):
        return True

    if re.search(
        r"\b(?:поставщик|продавец|исполнитель|подрядчик|покупатель|заказчик|плательщик|грузополучатель|инн|кпп|дата|номер\s+документа)\b",
        lower,
    ):
        return True

    if re.search(r"\b(?:итого|всего|ндс|сумма\s+к\s+оплате|к\s+оплате)\b", lower):
        return True

    return False


def _looks_like_table_header(line: str) -> bool:
    lower = line.lower()
    header_words = ("наименование", "кол-во", "количество", "цена", "сумма", "стоимость")
    return sum(1 for word in header_words if word in lower) >= 2


def _item_key(item: LineItem) -> Tuple[Any, Any, Any]:
    return (item.name.value, item.quantity.value, item.amount.value)


def _parse_rows_structure(rows: Any) -> List[List[str]]:
    parsed: List[List[str]] = []
    if not isinstance(rows, list):
        return parsed

    for row in rows:
        if isinstance(row, list):
            parsed.append([_cell_text(cell) for cell in row])
        elif isinstance(row, dict):
            cells = row.get("cells")
            if isinstance(cells, list):
                parsed.append([_cell_text(cell) for cell in cells])
    return parsed


def _parse_cells_structure(cells: Any) -> List[List[str]]:
    if not isinstance(cells, list):
        return []

    grouped: Dict[int, Dict[int, str]] = {}
    fallback_row = 0

    for idx, cell in enumerate(cells):
        if not isinstance(cell, dict):
            continue

        row_idx = _first_int(cell, ("rowIndex", "row_index", "row", "row_id"))
        col_idx = _first_int(cell, ("columnIndex", "column_index", "col", "column", "col_id"))

        if row_idx is None:
            row_idx = fallback_row
        if col_idx is None:
            col_idx = idx

        grouped.setdefault(row_idx, {})[col_idx] = _cell_text(cell)

    rows: List[List[str]] = []
    for row_idx in sorted(grouped):
        cols = grouped[row_idx]
        rows.append([cols[col_idx] for col_idx in sorted(cols)])
    return rows


def _first_int(obj: Dict[str, Any], keys: Sequence[str]) -> Optional[int]:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _cell_text(cell: Any) -> str:
    if isinstance(cell, str):
        return normalize_single_line(cell)
    if not isinstance(cell, dict):
        return ""

    for key in ("text", "fullText", "value", "content"):
        value = cell.get(key)
        if isinstance(value, str):
            return normalize_single_line(value)
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            return normalize_single_line(value["text"])

    return ""


def _build_warnings(document: DocumentInfo, counterparties: Sequence[Counterparty], items: Sequence[LineItem]) -> List[str]:
    warnings: List[str] = []

    if document.type.value is None:
        warnings.append("Не удалось определить тип документа")
    if document.number.value is None:
        warnings.append("Не удалось найти номер документа")
    if document.date.value is None:
        warnings.append("Не удалось найти дату документа")
    if document.total_amount.value is None:
        warnings.append("Не удалось найти итоговую сумму")
    if not counterparties:
        warnings.append("Не удалось найти контрагентов")
    if not items:
        warnings.append("Не удалось извлечь табличные позиции")

    return warnings
