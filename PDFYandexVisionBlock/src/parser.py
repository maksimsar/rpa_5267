"""
parser.py

Автономный слой парсинга OCR-результата.

Задача файла:
Yandex Vision / Yandex OCR JSON или OCR-текст -> нормальный структурированный dict.

Этот файл не делает HTTP-запросы, не читает PDF и не зависит от Puzzle RPA.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


PARSER_VERSION = "3.0.0"


def parse_requisites(vision_response: Dict[str, Any] | str | None) -> Dict[str, Any]:
    """
    Публичная функция парсера.

    Возвращает компактный структурированный результат.
    Оставлена для совместимости с предыдущей архитектурой.
    """
    return parse_requisites_simple(vision_response)


def parse_requisites_simple(vision_response: Dict[str, Any] | str | None) -> Dict[str, Any]:
    """
    Основная публичная функция.

    Принимает:
    - сырой JSON Yandex OCR / Vision;
    - строку OCR-текста;
    - None.

    Возвращает dict, который удобно отдавать из Puzzle RPA как dict/json.
    """
    raw_text = extract_text_from_vision_response(vision_response)
    parsed = parse_text(raw_text)

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
    Мини-совместимость со старой идеей parse_requisites_result(...).to_dict(...).

    Да, это чуть некрасиво, зато не ломает чужой код, который мог ждать .to_dict().
    """
    def to_dict(self, include_explainability: bool = False) -> Dict[str, Any]:
        return dict(self)


def parse_requisites_result(vision_response: Dict[str, Any] | str | None) -> ParserResult:
    """
    Совместимость со старым parser.py.

    Раньше эта функция могла возвращать объект схемы.
    Сейчас возвращает dict-подобный объект с методом to_dict().
    """
    return ParserResult(parse_requisites_simple(vision_response))


def extract_text_from_vision_response(vision_response: Dict[str, Any] | str | None) -> str:
    """
    Достаёт OCR-текст из ответа Yandex.

    Поддерживает:
    - обычную строку;
    - старый Vision JSON;
    - новый async OCR wrapper вида {"ocr_api": ..., "result": {...}};
    - вложенные pages/blocks/lines/words;
    - ключи text/fullText/full_text.
    """
    if vision_response is None:
        return ""

    if isinstance(vision_response, str):
        return normalize_text(vision_response)

    if not isinstance(vision_response, dict):
        return ""

    # Если yandex_client вернул wrapper async OCR, основное содержимое лежит внутри result.
    if isinstance(vision_response.get("result"), dict):
        inner_text = extract_text_from_vision_response(vision_response["result"])
        if inner_text:
            return inner_text

    full_texts = _collect_values_by_keys(
        vision_response,
        {"fullText", "full_text", "fullTextAnnotation"},
    )
    full_texts = [value for value in full_texts if _looks_like_text(value)]

    if full_texts:
        return normalize_text(max(full_texts, key=len))

    line_texts = _collect_line_texts(vision_response)

    if line_texts:
        return normalize_text("\n".join(_unique_preserve_order(line_texts)))

    generic_texts = _collect_values_by_keys(vision_response, {"text"})
    generic_texts = [value for value in generic_texts if _looks_like_text(value)]

    if generic_texts:
        return normalize_text("\n".join(_unique_preserve_order(generic_texts)))

    word_texts = _collect_word_texts(vision_response)

    if word_texts:
        return normalize_text(" ".join(word_texts))

    return ""


def extract_table_rows_from_vision_response(vision_response: Dict[str, Any] | str | None) -> List[List[str]]:
    """
    Совместимость с прежним parser.py.

    Пока возвращает пустой список, потому что текущий рабочий парсер
    надёжнее вытаскивает позиции из OCR-текста.
    """
    return []


def parse_text(raw_text: str) -> Dict[str, Any]:
    """
    Парсит уже извлечённый OCR-текст.
    """
    text = normalize_text(raw_text)
    flat = normalize_single_line(text)

    document = {
        "type": find_document_type(flat),
        "number": find_document_number(flat),
        "date": find_document_date(flat),
        "total_amount": find_total_amount(flat),
    }

    counterparties = find_counterparties(flat)
    items = find_items(text)

    warnings = build_warnings(document, counterparties, items)

    return {
        "document": document,
        "counterparties": counterparties,
        "items": items,
        "raw_text": format_raw_text(text),
        "warnings": warnings,
    }


def normalize_text(text: str) -> str:
    """
    Нормализует OCR-текст, сохраняя переносы строк.
    """
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
    """
    Делает одну строку для regex-поиска.
    """
    text = normalize_text(text)
    return re.sub(r"\s+", " ", text).strip()


def format_raw_text(text: str, max_lines: int = 120) -> Dict[str, Any]:
    """
    Красивый raw_text для JSON.

    Не одна огромная строка с \\n, а нормальный объект:
    preview + lines + line_count + truncated.
    """
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
    patterns = [
        ("Invoice", r"\b(invoice|commercial invoice|tax invoice)\b"),
        ("Счет", r"\b(сч[её]т|счет на оплату)\b"),
        ("Счет-фактура", r"\b(сч[её]т[\s-]*фактура)\b"),
        ("УПД", r"\b(упд|универсальный передаточный документ)\b"),
        ("Акт", r"\b(акт|акт выполненных работ|акт оказанных услуг)\b"),
        ("Накладная", r"\b(накладная|товарная накладная|торг-?12)\b"),
        ("Договор", r"\b(договор|contract|agreement)\b"),
    ]

    search = flat.lower()

    for label, pattern in patterns:
        if re.search(pattern, search, flags=re.IGNORECASE):
            return label

    return None


def find_document_number(flat: str) -> Optional[str]:
    search_area = flat[:1200]

    patterns = [
        r"(?:invoice\s*(?:number|no\.?|#)\s*[:\-]?\s*)([A-Za-z0-9_.\-\/\\]+)",
        r"(?:document\s*(?:number|no\.?|#)\s*[:\-]?\s*)([A-Za-z0-9_.\-\/\\]+)",
        r"(?:номер\s*(?:документа)?\s*[:\-]?\s*)([A-Za-zА-Яа-я0-9_.\-\/\\]+)",
        r"(?:№|n[oо]?\.?)\s*([A-Za-zА-Яа-я0-9_.\-\/\\]+)",
        r"(?:сч[её]т|invoice).{0,80}?(?:№|n[oо]?\.?|number|#)\s*[:\-]?\s*([A-Za-zА-Яа-я0-9_.\-\/\\]+)",
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

        if re.fullmatch(r"\d{2}[./-]\d{2}[./-]\d{4}", number):
            continue

        if len(number) > 40:
            continue

        return number

    return None


def clean_document_number(value: str) -> Optional[str]:
    if not value:
        return None

    value = value.strip()
    value = value.strip(".,;:()[]{}<>")
    value = value.replace("\\", "/")

    # OCR иногда цепляет слово "от" после номера.
    value = re.sub(r"\s*(?:от|date|dated)$", "", value, flags=re.IGNORECASE).strip()

    return value or None


def find_document_date(flat: str) -> Optional[str]:
    search_area = flat[:1500]

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


def normalize_date(value: str) -> str:
    value = value.strip().replace("/", ".").replace("-", ".")

    parts = value.split(".")

    if len(parts) != 3:
        return value

    # YYYY.MM.DD -> YYYY-MM-DD
    if len(parts[0]) == 4:
        year = parts[0]
        month = parts[1].zfill(2)
        day = parts[2].zfill(2)
        return f"{year}-{month}-{day}"

    # DD.MM.YYYY оставляем в привычном виде для русских документов.
    day = parts[0].zfill(2)
    month = parts[1].zfill(2)
    year = parts[2]

    if len(year) == 2:
        year = "20" + year

    return f"{day}.{month}.{year}"


def find_total_amount(flat: str) -> Optional[float]:
    priority_patterns = [
        r"(?:grand\s*total|total\s*amount|total\s*due|amount\s*due|invoice\s*total)\s*[:\-]?\s*(?:USD|EUR|RUB|₽|\$)?\s*([0-9][0-9\s\u00a0\u202f,.]*[,.]\d{2})",
        r"(?:итого\s*к\s*оплате|всего\s*к\s*оплате|сумма\s*к\s*оплате)\s*[:\-]?\s*([0-9][0-9\s\u00a0\u202f,.]*[,.]\d{2})",
        r"(?:итого\s*без\s*ндс|всего\s*без\s*ндс|итого|всего|сумма)\s*[:\-]?\s*([0-9][0-9\s\u00a0\u202f,.]*[,.]\d{2})",
        r"(?:total|subtotal)\s*[:\-]?\s*(?:USD|EUR|RUB|₽|\$)?\s*([0-9][0-9\s\u00a0\u202f,.]*[,.]\d{2})",
    ]

    candidates = []

    for pattern in priority_patterns:
        for match in re.finditer(pattern, flat, flags=re.IGNORECASE):
            amount = parse_amount(match.group(1))

            if amount is not None:
                candidates.append((amount, match.start()))

    if candidates:
        # Берём максимальную из найденных "итоговых" сумм.
        # Это спасает от захвата цены строки таблицы.
        return max(value for value, _ in candidates)

    money_values = []
    money_pattern = r"\b([0-9]{1,3}(?:[\s\u00a0\u202f,][0-9]{3})*(?:[,.]\d{2})|[0-9]+(?:[,.]\d{2}))\b"

    for match in re.finditer(money_pattern, flat):
        amount = parse_amount(match.group(1))

        if amount is not None and amount > 0:
            money_values.append(amount)

    if money_values:
        return max(money_values)

    return None


def parse_amount(value: str) -> Optional[float]:
    if not value:
        return None

    value = str(value)
    value = value.replace("\u00a0", " ").replace("\u202f", " ")
    value = re.sub(r"(USD|EUR|RUB|руб\.?|рублей|рубля|р\.|₽|\$)", "", value, flags=re.IGNORECASE)
    value = value.strip()

    # 15,800.50 -> 15800.50
    if "," in value and "." in value:
        value = value.replace(",", "")
    elif "," in value and "." not in value:
        # 15800,50 -> 15800.50
        if re.search(r",\d{1,2}$", value):
            value = value.replace(",", ".")
        else:
            value = value.replace(",", "")

    value = value.replace(" ", "")
    value = re.sub(r"[^0-9.\-]", "", value)

    if not value or value in ("-", ".", "-."):
        return None

    try:
        return float(value)
    except ValueError:
        return None


def find_counterparties(flat: str) -> List[Dict[str, Any]]:
    supplier_section = find_role_section(
        flat,
        labels=["Поставщик", "Supplier", "Vendor", "Seller", "Provider"],
        stop_labels=["Покупатель", "Buyer", "Customer", "Client", "Consignee", "Bill To", "Ship To", "Items", "Table", "Итого", "Total"],
    )

    buyer_section = find_role_section(
        flat,
        labels=["Покупатель", "Buyer", "Customer", "Client", "Bill To"],
        stop_labels=["Поставщик", "Supplier", "Vendor", "Seller", "Provider", "Items", "Table", "Основание", "Назначение", "Итого", "Total"],
    )

    all_inns = find_all_inn(flat)
    all_kpps = find_all_kpp(flat)

    supplier_name = clean_org_name(extract_name_from_section(supplier_section, "supplier"))
    buyer_name = clean_org_name(extract_name_from_section(buyer_section, "buyer"))

    supplier_inn = find_inn_in_section(supplier_section) or (all_inns[0] if all_inns else None)
    supplier_kpp = find_kpp_in_section(supplier_section) or (all_kpps[0] if all_kpps else None)

    buyer_inn = find_inn_in_section(buyer_section)
    buyer_kpp = find_kpp_in_section(buyer_section)

    if not buyer_inn and len(all_inns) > 1:
        buyer_inn = all_inns[1]

    if not buyer_kpp and len(all_kpps) > 1:
        buyer_kpp = all_kpps[1]

    counterparties = []

    if supplier_name or supplier_inn or supplier_kpp:
        counterparties.append(
            {
                "role": "supplier",
                "name": supplier_name,
                "inn": supplier_inn,
                "kpp": supplier_kpp,
            }
        )

    if buyer_name or buyer_inn or buyer_kpp:
        counterparties.append(
            {
                "role": "buyer",
                "name": buyer_name,
                "inn": buyer_inn,
                "kpp": buyer_kpp,
            }
        )

    if not counterparties:
        counterparties.append(
            {
                "role": None,
                "name": None,
                "inn": None,
                "kpp": None,
            }
        )

    return deduplicate_counterparties(counterparties)


def find_role_section(flat: str, labels: List[str], stop_labels: List[str], max_len: int = 500) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(label) for label in stop_labels)

    match = re.search(rf"\b(?:{label_pattern})\b\s*[:\-]?\s*", flat, flags=re.IGNORECASE)

    if not match:
        return ""

    start = match.end()
    end = min(len(flat), start + max_len)

    stop_match = re.search(rf"\b(?:{stop_pattern})\b\s*[:\-]?", flat[start:end], flags=re.IGNORECASE)

    if stop_match:
        end = start + stop_match.start()

    return flat[start:end].strip()


def extract_name_from_section(section: str, role: str) -> Optional[str]:
    if not section:
        return None

    section = section.strip()

    # Режем по техническим маркерам, чтобы имя не захватывало ИНН/адреса/лишние поля.
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
    ]

    cut_at = len(section)

    for pattern in cut_patterns:
        match = re.search(pattern, section, flags=re.IGNORECASE)

        if match:
            cut_at = min(cut_at, match.start())

    name = section[:cut_at].strip()

    # Если имя пустое, пробуем найти организацию по шаблону прямо в секции.
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

    replacements = {
        '\\"': '"',
        "\\'": "'",
        "«": "",
        "»": "",
        '"': "",
        "'": "",
        "`": "",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    name = re.sub(r"\b(?:поставщика|покупателя|supplier|buyer|customer|vendor)\s*[:\-]?", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\b(?:ИНН|КПП|INN|KPP|Tax\s*ID|Address|Адрес)\b.*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(" ,;:-")

    if not name:
        return None

    return name


def find_all_inn(flat: str) -> List[str]:
    values = []

    # Сначала с явными метками.
    for match in re.finditer(r"\b(?:ИНН|INN|Tax\s*ID)\b[^\d]{0,40}(\d{10}|\d{12})\b", flat, flags=re.IGNORECASE):
        values.append(match.group(1))

    # Потом fallback: любые 10/12-значные числа.
    for match in re.finditer(r"\b(\d{10}|\d{12})\b", flat):
        values.append(match.group(1))

    return _unique_preserve_order(values)


def find_all_kpp(flat: str) -> List[str]:
    values = []

    for match in re.finditer(r"\b(?:КПП|KPP)\b[^\d]{0,40}(\d{9})\b", flat, flags=re.IGNORECASE):
        values.append(match.group(1))

    for match in re.finditer(r"\b(\d{9})\b", flat):
        values.append(match.group(1))

    return _unique_preserve_order(values)


def find_inn_in_section(section: str) -> Optional[str]:
    if not section:
        return None

    match = re.search(r"\b(?:ИНН|INN|Tax\s*ID)\b[^\d]{0,40}(\d{10}|\d{12})\b", section, flags=re.IGNORECASE)

    if match:
        return match.group(1)

    match = re.search(r"\b(\d{10}|\d{12})\b", section)

    return match.group(1) if match else None


def find_kpp_in_section(section: str) -> Optional[str]:
    if not section:
        return None

    match = re.search(r"\b(?:КПП|KPP)\b[^\d]{0,40}(\d{9})\b", section, flags=re.IGNORECASE)

    if match:
        return match.group(1)

    match = re.search(r"\b(\d{9})\b", section)

    return match.group(1) if match else None


def deduplicate_counterparties(counterparties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    seen = set()

    for party in counterparties:
        key = (party.get("role"), party.get("inn"), party.get("kpp"))

        if key in seen:
            continue

        seen.add(key)
        result.append(party)

    return result


def find_items(text: str) -> List[Dict[str, Any]]:
    lines = [line.strip() for line in normalize_text(text).splitlines() if line.strip()]
    items = []

    for line in lines:
        item = parse_item_line(line)

        if item:
            items.append(item)

    if items:
        return items

    # Fallback: иногда OCR склеивает таблицу в одну строку.
    flat = normalize_single_line(text)

    pattern = re.compile(
        r"\b(\d+)\s+"
        r"(.{3,100}?)\s+"
        r"(?:(\d+(?:[,.]\d+)?)\s+)?"
        r"(шт|усл|ед|pcs|piece|pieces|service|services|hour|hours)\.?\s+"
        r"([0-9]{1,3}(?:[\s\u00a0\u202f,][0-9]{3})*(?:[,.]\d{2})|[0-9]+(?:[,.]\d{2}))\s+"
        r"([0-9]{1,3}(?:[\s\u00a0\u202f,][0-9]{3})*(?:[,.]\d{2})|[0-9]+(?:[,.]\d{2}))",
        flags=re.IGNORECASE,
    )

    for match in pattern.finditer(flat):
        name = clean_item_name(match.group(2))

        if not name:
            continue

        quantity = parse_quantity(match.group(3)) if match.group(3) else None

        items.append(
            {
                "position": int(match.group(1)),
                "name": name,
                "quantity": quantity,
                "unit": normalize_unit(match.group(4)),
                "price": parse_amount(match.group(5)),
                "amount": parse_amount(match.group(6)),
            }
        )

    return items


def parse_item_line(line: str) -> Optional[Dict[str, Any]]:
    line = normalize_single_line(line)

    if not line:
        return None

    if re.search(r"\b(?:итого|всего|ндс|total|subtotal|amount due|grand total)\b", line, flags=re.IGNORECASE):
        return None

    pattern = re.compile(
        r"^\s*(\d+)[.)]?\s+"
        r"(.{3,100}?)\s+"
        r"(?:(\d+(?:[,.]\d+)?)\s+)?"
        r"(шт|усл|ед|pcs|piece|pieces|service|services|hour|hours)\.?\s+"
        r"([0-9]{1,3}(?:[\s\u00a0\u202f,][0-9]{3})*(?:[,.]\d{2})|[0-9]+(?:[,.]\d{2}))\s+"
        r"([0-9]{1,3}(?:[\s\u00a0\u202f,][0-9]{3})*(?:[,.]\d{2})|[0-9]+(?:[,.]\d{2}))",
        flags=re.IGNORECASE,
    )

    match = pattern.search(line)

    if not match:
        return None

    name = clean_item_name(match.group(2))

    if not name:
        return None

    return {
        "position": int(match.group(1)),
        "name": name,
        "quantity": parse_quantity(match.group(3)) if match.group(3) else None,
        "unit": normalize_unit(match.group(4)),
        "price": parse_amount(match.group(5)),
        "amount": parse_amount(match.group(6)),
    }


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

    value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return None


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None

    unit = unit.lower().strip().strip(".")

    mapping = {
        "шт": "pcs",
        "pcs": "pcs",
        "piece": "pcs",
        "pieces": "pcs",
        "усл": "service",
        "service": "service",
        "services": "service",
        "ед": "unit",
        "hour": "hour",
        "hours": "hour",
    }

    return mapping.get(unit, unit)


def build_warnings(
    document: Dict[str, Any],
    counterparties: List[Dict[str, Any]],
    items: List[Dict[str, Any]],
) -> List[str]:
    warnings = []

    if not document.get("type"):
        warnings.append("DOCUMENT_TYPE_NOT_FOUND")

    if not document.get("number"):
        warnings.append("DOCUMENT_NUMBER_NOT_FOUND")

    if not document.get("date"):
        warnings.append("DOCUMENT_DATE_NOT_FOUND")

    if document.get("total_amount") is None:
        warnings.append("TOTAL_AMOUNT_NOT_FOUND")

    if not counterparties or not any(party.get("inn") for party in counterparties):
        warnings.append("INN_NOT_FOUND")

    if not counterparties or not any(party.get("kpp") for party in counterparties):
        warnings.append("KPP_NOT_FOUND")

    if not items:
        warnings.append("ITEMS_NOT_FOUND_OR_TABLE_NOT_RECOGNIZED")

    return warnings


def _collect_values_by_keys(obj: Any, keys: set) -> List[str]:
    values = []

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