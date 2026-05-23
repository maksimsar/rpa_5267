import json
import os
import re
from typing import Any, Dict, List, Optional

try:
    import requests
except ModuleNotFoundError:
    requests = None

from .yandex_client import call_yandex_vision

try:
    from puzzle_logger import log_decorator, window_logger
except Exception:
    # Чтобы файл можно было запускать вне Puzzle RPA во время локальной отладки.
    def log_decorator(func):
        return func

    def window_logger(func):
        return func


def _error(code: str, message: str, details: Optional[Any] = None) -> Dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def _clean_text(value: Any) -> str:
    """
    Очищает входы из Puzzle RPA от None, пробелов и случайных кавычек.
    """
    if value is None:
        return ""
    return str(value).strip().strip('"').strip("'")


def _format_result(result: Dict[str, Any], output_format: str):
    """
    Возвращает результат в нужном формате: dict или красиво отформатированный JSON.
    """
    output_format = _clean_text(output_format).lower() or "dict"

    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    return result


def _extract_text_from_response(response_json: Dict[str, Any]) -> str:
    """
    Извлекает текст из ответа Yandex Vision.

    Yandex может возвращать текст в разных вложенных структурах.
    Поэтому проходим по JSON рекурсивно и забираем значения text/fullText.
    """
    chunks: List[str] = []

    def walk(obj: Any):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ("text", "fullText") and isinstance(value, str):
                    cleaned = value.strip()
                    if cleaned:
                        chunks.append(cleaned)
                else:
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(response_json)

    unique_chunks = list(dict.fromkeys(chunks))
    return "\n".join(unique_chunks)


def _normalize_for_regex(text: str) -> str:
    """
    Делает OCR-текст удобным для regex-парсинга.
    """
    text = text or ""
    text = text.replace("\u00a0", " ")
    text = text.replace("\\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_raw_text_lines(text: str, max_lines: int = 80) -> Dict[str, Any]:
    """
    Делает raw_text красивым для JSON.

    Вместо одной огромной строки с \\n возвращаем:
    - preview;
    - список строк;
    - количество строк;
    - признак обрезки.
    """
    prepared = (text or "").replace("\\n", "\n")

    lines = []
    for line in prepared.splitlines():
        cleaned = line.strip()
        if cleaned:
            lines.append(cleaned)

    preview = " ".join(lines)
    preview = re.sub(r"\s+", " ", preview).strip()

    return {
        "preview": preview[:1000],
        "lines": lines[:max_lines],
        "line_count": len(lines),
        "truncated": len(lines) > max_lines,
    }


def _parse_amount(raw_value: str) -> Optional[float]:
    """
    Превращает сумму вида 15 800,50 или 15800.50 в float.
    """
    if not raw_value:
        return None

    cleaned = (
        raw_value
        .replace("\u00a0", "")
        .replace(" ", "")
        .replace(",", ".")
        .strip()
    )

    try:
        return float(cleaned)
    except ValueError:
        return None


def _find_total_amount(normalized: str) -> Optional[float]:
    """
    Ищет итоговую сумму.

    Важно: сначала ищем суммы рядом с итоговыми словами.
    Если не нашли, берём максимальную сумму из документа,
    а не первую попавшуюся цену из таблицы.
    """
    priority_patterns = [
        r"(?:Итого\s*к\s*оплате|Всего\s*к\s*оплате).{0,120}?([0-9]{1,3}(?:[\s\u00a0]?[0-9]{3})*(?:[,.]\d{2}))",
        r"(?:Итого\s*без\s*НДС|Всего\s*без\s*НДС|Итого).{0,120}?([0-9]{1,3}(?:[\s\u00a0]?[0-9]{3})*(?:[,.]\d{2}))",
        r"(?:Всего|Сумма).{0,120}?([0-9]{1,3}(?:[\s\u00a0]?[0-9]{3})*(?:[,.]\d{2}))",
    ]

    for pattern in priority_patterns:
        matches = re.findall(pattern, normalized, flags=re.IGNORECASE)
        parsed_values = [_parse_amount(value) for value in matches]
        parsed_values = [value for value in parsed_values if value is not None]

        if parsed_values:
            return max(parsed_values)

    all_amounts = re.findall(
        r"\b([0-9]{1,3}(?:[\s\u00a0]?[0-9]{3})*(?:[,.]\d{2}))\s*(?:руб|р\.|₽)?\b",
        normalized,
        flags=re.IGNORECASE,
    )

    parsed_values = [_parse_amount(value) for value in all_amounts]
    parsed_values = [value for value in parsed_values if value is not None]

    if parsed_values:
        return max(parsed_values)

    return None


def _find_party_name(normalized: str, label: str) -> Optional[str]:
    """
    Пытается извлечь название организации после Поставщик/Покупатель.
    """
    pattern = (
        rf"{label}\s*[:\-]?\s*"
        rf"(.{{2,120}}?)"
        rf"(?=\s*(?:ИНН|КПП|Адрес|Поставщик|Покупатель|Основание|Назначение|$))"
    )

    match = re.search(pattern, normalized, flags=re.IGNORECASE)

    if not match:
        return None

    name = match.group(1).strip(" :-")
    name = re.sub(r"\s+", " ", name).strip()

    if len(name) < 2:
        return None

    return name


def _extract_counterparties(normalized: str) -> List[Dict[str, Any]]:
    """
    Извлекает поставщика и покупателя.

    Сейчас это не полноценный бухгалтерский парсер,
    но для чекпоинта вытаскивает основные ИНН/КПП гораздо стабильнее.
    """
    all_inn = re.findall(r"\b\d{10}|\b\d{12}", normalized)
    all_kpp = re.findall(r"\b\d{9}\b", normalized)

    supplier_name = _find_party_name(normalized, "Поставщик")
    buyer_name = _find_party_name(normalized, "Покупатель")

    supplier_inn_match = re.search(
        r"(?:ИНН\s*поставщика|ИНН).{0,40}?(\d{10}|\d{12})",
        normalized,
        flags=re.IGNORECASE,
    )

    supplier_kpp_match = re.search(
        r"(?:КПП).{0,40}?(\d{9})",
        normalized,
        flags=re.IGNORECASE,
    )

    buyer_match = re.search(
        r"(?:Покупатель).{0,180}?(\d{10}|\d{12}).{0,40}?(\d{9})",
        normalized,
        flags=re.IGNORECASE,
    )

    counterparties: List[Dict[str, Any]] = []

    supplier_inn = supplier_inn_match.group(1) if supplier_inn_match else (all_inn[0] if all_inn else None)
    supplier_kpp = supplier_kpp_match.group(1) if supplier_kpp_match else (all_kpp[0] if all_kpp else None)

    if supplier_name or supplier_inn or supplier_kpp:
        counterparties.append(
            {
                "role": "supplier",
                "name": supplier_name,
                "inn": supplier_inn,
                "kpp": supplier_kpp,
            }
        )

    buyer_inn = None
    buyer_kpp = None

    if buyer_match:
        buyer_inn = buyer_match.group(1)
        buyer_kpp = buyer_match.group(2)
    elif len(all_inn) > 1 or len(all_kpp) > 1:
        buyer_inn = all_inn[1] if len(all_inn) > 1 else None
        buyer_kpp = all_kpp[1] if len(all_kpp) > 1 else None

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

    return counterparties


def _extract_items(normalized: str) -> List[Dict[str, Any]]:
    """
    Пробует извлечь табличные позиции.

    Формат не идеальный, потому что OCR может ломать таблицы,
    но для тестового счёта вытаскивает основные строки.
    """
    items: List[Dict[str, Any]] = []

    item_pattern = re.compile(
        r"\b(\d+)\s+"
        r"(.{3,90}?)\s+"
        r"(\d+(?:[,.]\d+)?)\s+"
        r"(шт|усл|ед|pcs|service)\.?\s+"
        r"([0-9]{1,3}(?:[\s\u00a0]?[0-9]{3})*(?:[,.]\d{2}))\s+"
        r"([0-9]{1,3}(?:[\s\u00a0]?[0-9]{3})*(?:[,.]\d{2}))",
        flags=re.IGNORECASE,
    )

    for match in item_pattern.finditer(normalized):
        quantity_raw = match.group(3).replace(",", ".")

        try:
            quantity = float(quantity_raw)
        except ValueError:
            quantity = None

        items.append(
            {
                "position": int(match.group(1)),
                "name": re.sub(r"\s+", " ", match.group(2)).strip(),
                "quantity": quantity,
                "unit": match.group(4),
                "price": _parse_amount(match.group(5)),
                "amount": _parse_amount(match.group(6)),
            }
        )

    return items


def _parse_requisites(text: str) -> Dict[str, Any]:
    """
    Извлекает основные реквизиты из OCR-текста.
    """
    normalized = _normalize_for_regex(text)

    doc_type = None
    for candidate in ["УПД", "Акт", "Накладная", "Счёт", "Счет", "Договор"]:
        if re.search(candidate, normalized, flags=re.IGNORECASE):
            doc_type = "Счет" if candidate in ("Счёт", "Счет") else candidate
            break

    number_match = re.search(
        r"(?:№|N|Номер[:\s]*)\s*([A-Za-zА-Яа-я0-9\-\/]+)",
        normalized,
        flags=re.IGNORECASE,
    )

    date_match = re.search(
        r"\b(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\b",
        normalized,
    )

    total_amount = _find_total_amount(normalized)
    counterparties = _extract_counterparties(normalized)
    items = _extract_items(normalized)

    warnings = []

    if total_amount is None:
        warnings.append("TOTAL_AMOUNT_NOT_FOUND")

    if not counterparties or not any(item.get("inn") for item in counterparties):
        warnings.append("INN_NOT_FOUND")

    if not items:
        warnings.append("ITEMS_NOT_FOUND_OR_TABLE_NOT_RECOGNIZED")

    return {
        "document": {
            "type": doc_type,
            "number": number_match.group(1) if number_match else None,
            "date": date_match.group(1) if date_match else None,
            "total_amount": total_amount,
        },
        "counterparties": counterparties,
        "items": items,
        "raw_text": _split_raw_text_lines(text),
        "warnings": warnings,
    }


@window_logger
@log_decorator
def process_pdf(
    token: str,
    folder_id: str,
    file_path: str,
    language: str = "ru",
    output_format: str = "dict",
    timeout: int = 45,
    puzzle_logger_path=None,
    block_text=None,
    block_id=None,
    window_log=False,
    current_language=None,
    **kwargs,
):
    """
    Главная функция блока Puzzle RPA.

    Принимает PDF, отправляет в Yandex Vision,
    парсит результат и возвращает dict или JSON-строку.
    """
    try:
        token = _clean_text(token)
        folder_id = _clean_text(folder_id)
        file_path = _clean_text(file_path)
        language = _clean_text(language) or "ru"
        output_format = _clean_text(output_format).lower() or "dict"

        if requests is None:
            return _format_result(
                _error(
                    "MISSING_DEPENDENCY",
                    "Не установлена библиотека requests. Выполните: python -m pip install -r requirements.txt",
                ),
                output_format,
            )

        if not token:
            return _format_result(
                _error("EMPTY_TOKEN", "Не передан токен Yandex Cloud"),
                output_format,
            )

        if not folder_id:
            return _format_result(
                _error("EMPTY_FOLDER_ID", "Не передан Folder ID Yandex Cloud"),
                output_format,
            )

        if not file_path or not os.path.exists(file_path):
            return _format_result(
                _error("FILE_NOT_FOUND", "PDF-файл не найден", file_path),
                output_format,
            )

        vision_result = call_yandex_vision(
            token=token,
            folder_id=folder_id,
            file_path=file_path,
            language=language,
            timeout=timeout,
        )

        if not vision_result.get("success"):
            return _format_result(vision_result, output_format)

        vision_json = vision_result["data"]

        text = _extract_text_from_response(vision_json)
        parsed = _parse_requisites(text)

        result = {
            "success": True,
            **parsed,
        }

        return _format_result(result, output_format)

    except Exception as exc:
        return _format_result(
            _error("UNKNOWN_ERROR", "Непредвиденная ошибка блока", str(exc)),
            output_format if "output_format" in locals() else "dict",
        )