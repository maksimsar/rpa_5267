"""
normalizer.py

Устойчивые функции нормализации OCR-результата.

Этот модуль специально изолирован:
- не знает про Puzzle RPA;
- не знает про Yandex Vision;
- не делает HTTP;
- не читает файлы.

Именно поэтому его легко покрывать тестами.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


MONTHS_RU = {
    "января": 1,
    "январь": 1,
    "февраля": 2,
    "февраль": 2,
    "марта": 3,
    "март": 3,
    "апреля": 4,
    "апрель": 4,
    "мая": 5,
    "май": 5,
    "июня": 6,
    "июнь": 6,
    "июля": 7,
    "июль": 7,
    "августа": 8,
    "август": 8,
    "сентября": 9,
    "сентябрь": 9,
    "октября": 10,
    "октябрь": 10,
    "ноября": 11,
    "ноябрь": 11,
    "декабря": 12,
    "декабрь": 12,
}

OCR_REPLACEMENTS = {
    "\u00a0": " ",
    "\u202f": " ",
    "—": "-",
    "–": "-",
    "−": "-",
    "№ ": "№",
    "N ": "N",
    "No ": "No",
    "«": "«",
    "»": "»",
}

COMMON_OCR_WORD_FIXES = {
    # Только безопасные замены для реквизитных слов.
    "иин": "инн",
    "кnп": "кпп",
    "kпп": "кпп",
    "счeт": "счет",
    "счётъ": "счёт",
}


def normalize_text(text: str | None) -> str:
    """Нормализует многострочный OCR-текст без потери переводов строк."""
    if text is None:
        return ""

    text = str(text)

    for old, new in OCR_REPLACEMENTS.items():
        text = text.replace(old, new)

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Убираем лишние пробелы, но сохраняем строки.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Часто OCR разрывает большие числа: 25 500,50 должно остаться корректным,
    # но одиночные лишние пробелы между тысячами не мешают normalize_amount.
    return text.strip()


def normalize_single_line(text: str | None) -> str:
    """Делает одну чистую строку."""
    return re.sub(r"\s+", " ", normalize_text(text)).strip()


def normalize_for_search(text: str | None) -> str:
    """Нормализация для regex-поиска без изменения исходного raw_text."""
    text = normalize_single_line(text).lower()
    for old, new in COMMON_OCR_WORD_FIXES.items():
        text = text.replace(old, new)
    return text


def normalize_digits(value: str | None) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r"\D+", "", str(value))
    return digits or None


def normalize_inn(value: str | None) -> Optional[str]:
    digits = normalize_digits(value)
    if digits and len(digits) in (10, 12):
        return digits
    return None


def normalize_kpp(value: str | None) -> Optional[str]:
    digits = normalize_digits(value)
    if digits and len(digits) == 9:
        return digits
    return None


def normalize_document_number(value: str | None) -> Optional[str]:
    if value is None:
        return None

    value = normalize_single_line(value)
    value = value.strip(" .,:;№Nn")

    # Обрезаем типовые хвосты, если regex захватил лишнее.
    value = re.split(
        r"\s+(?:от|дата|за|на)\s+",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    value = value.strip(" .,:;")

    if not value:
        return None

    # Номер не должен быть обычным словом без цифр/дефисов/слеша,
    # иначе "Акт выполненных работ" даст "выполненных".
    if not re.search(r"[\dA-Za-zА-Яа-я]", value):
        return None

    return value


def normalize_org_name(value: str | None) -> Optional[str]:
    if value is None:
        return None

    value = normalize_single_line(value)
    value = value.strip(" «»\"'.,;:-")

    # Убираем служебные реквизиты и хвосты.
    value = re.split(
        r"\b(?:ИНН|КПП|ОГРН|ОГРНИП|БИК|р/с|к/с|адрес|тел\.?|e-mail)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    value = normalize_single_line(value).strip(" «»\"'.,;:-")
    return value or None


def normalize_unit(value: str | None) -> Optional[str]:
    if value is None:
        return None
    value = normalize_single_line(value).lower().strip(" .,:;")
    aliases = {
        "штука": "шт",
        "штуки": "шт",
        "шт.": "шт",
        "шт": "шт",
        "усл": "усл",
        "усл.": "усл",
        "ед": "ед",
        "ед.": "ед",
        "кг": "кг",
        "м2": "м2",
        "м²": "м2",
        "час": "час",
        "часа": "час",
        "часов": "час",
        "компл": "компл",
        "компл.": "компл",
    }
    return aliases.get(value, value or None)


def normalize_amount(value: str | int | float | Decimal | None) -> Optional[float]:
    """Преобразует сумму/цену/количество в float.

    Поддерживает:
    - 25 500,50
    - 25500.50
    - 25.500,50
    - 12,345.67
    - 25 500 руб. 50 коп.
    - 25500-50
    - 1 000
    """
    if value is None:
        return None

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (int, float)):
        return float(value)

    raw = normalize_single_line(str(value)).lower()
    if not raw:
        return None

    raw = raw.replace("₽", " руб ")

    # 25500-50 как рубли-копейки. Проверяем до rub/kop,
    # иначе "25500-50" может быть прочитано как одно большое число.
    dash = re.fullmatch(r"\s*(-?\d[\d\s.]*)-(\d{2})\s*", raw)
    if dash:
        rub = _parse_decimal_number(dash.group(1))
        if rub is not None:
            sign = -1 if rub < 0 else 1
            return float(rub + sign * Decimal(int(dash.group(2))) / Decimal(100))

    # 25 500 руб. 50 коп. Здесь слово "руб" обязательно.
    rub_kop = re.search(
        r"(?P<rub>-?\d[\d\s.,]*)\s*(?:руб(?:\.|лей|ля|ль)?|р\.?)\s*"
        r"(?P<kop>\d{1,2})?\s*(?:коп(?:\.|еек|ейки)?|к\.?)?",
        raw,
        flags=re.IGNORECASE,
    )
    if rub_kop:
        rub = _parse_decimal_number(rub_kop.group("rub"))
        if rub is not None:
            kop_raw = rub_kop.group("kop")
            kop = int(kop_raw) if kop_raw and kop_raw.isdigit() else 0
            sign = -1 if rub < 0 else 1
            return float(rub + sign * Decimal(kop) / Decimal(100))

    # dash уже обработан выше.
    dash = None
    if dash:
        rub = _parse_decimal_number(dash.group(1))
        if rub is not None:
            sign = -1 if rub < 0 else 1
            return float(rub + sign * Decimal(int(dash.group(2))) / Decimal(100))

    cleaned = re.sub(r"[^\d,.\-\s]", "", raw).strip()
    return _decimal_to_float(_parse_decimal_number(cleaned))


def _decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
    return float(value) if value is not None else None


def _parse_decimal_number(raw: str | None) -> Optional[Decimal]:
    if raw is None:
        return None

    raw = str(raw).strip()
    if not raw:
        return None

    raw = raw.replace("\u00a0", " ").replace("\u202f", " ")
    raw = re.sub(r"[^\d,.\-\s]", "", raw).strip()

    if not raw or raw in {"-", ".", ","}:
        return None

    sign = ""
    if raw.startswith("-"):
        sign = "-"
        raw = raw[1:]

    raw = raw.strip()

    last_comma = raw.rfind(",")
    last_dot = raw.rfind(".")

    if last_comma == -1 and last_dot == -1:
        normalized = re.sub(r"\s+", "", raw)
    else:
        decimal_sep = "," if last_comma > last_dot else "."
        other_sep = "." if decimal_sep == "," else ","

        # Если единственный разделитель выглядит как разделитель тысяч: 1.000 или 1,000.
        sep_count = raw.count(decimal_sep)
        after = raw.rsplit(decimal_sep, 1)[-1]
        before = raw.rsplit(decimal_sep, 1)[0]
        only_one_type = other_sep not in raw

        if only_one_type and sep_count >= 1 and len(after) == 3 and all(len(x) == 3 for x in raw.split(decimal_sep)[1:]):
            normalized = raw.replace(decimal_sep, "")
        else:
            normalized = raw.replace(other_sep, "")
            normalized = normalized.replace(decimal_sep, ".")

        normalized = normalized.replace(" ", "")

    if not normalized:
        return None

    try:
        return Decimal(sign + normalized)
    except InvalidOperation:
        return None


def normalize_date(value: str | None) -> Optional[str]:
    """Нормализует дату к YYYY-MM-DD.

    Поддерживает:
    - 22.05.2026
    - 22/05/26
    - 2026-05-22
    - 22 мая 2026
    - «22» мая 2026 г.
    """
    if value is None:
        return None

    text = normalize_single_line(value).lower()
    text = text.replace("г.", "").replace("года", "").strip()

    # «22» мая 2026
    text = text.replace("«", "").replace("»", "").replace('"', "")

    # dd.mm.yyyy / dd-mm-yy / dd/mm/yyyy
    match = re.search(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\b", text)
    if match:
        day, month, year = match.groups()
        return _safe_date(_normalize_year(year), int(month), int(day))

    # yyyy-mm-dd / yyyy.mm.dd
    match = re.search(r"\b(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\b", text)
    if match:
        year, month, day = match.groups()
        return _safe_date(int(year), int(month), int(day))

    # 22 мая 2026
    month_names = "|".join(sorted(MONTHS_RU, key=len, reverse=True))
    match = re.search(rf"\b(\d{{1,2}})\s+({month_names})\s+(\d{{2,4}})\b", text)
    if match:
        day, month_name, year = match.groups()
        return _safe_date(_normalize_year(year), MONTHS_RU[month_name], int(day))

    return None


def _normalize_year(year: str) -> int:
    year_int = int(year)
    if len(year) == 2:
        return 2000 + year_int if year_int < 70 else 1900 + year_int
    return year_int


def _safe_date(year: int, month: int, day: int) -> Optional[str]:
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def amounts_close(left: Optional[float], right: Optional[float], tolerance: float = 0.03) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance
