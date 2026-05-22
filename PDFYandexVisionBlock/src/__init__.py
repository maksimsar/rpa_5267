import base64
import json
import os
import re
from typing import Any, Dict, Optional

import requests

try:
    from puzzle_logger import log_decorator, window_logger
except Exception:
    # Чтобы файл можно было запускать вне Puzzle RPA во время локальной отладки.
    def log_decorator(func):
        return func

    def window_logger(func):
        return func


YANDEX_VISION_URL = "https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze"


def _error(code: str, message: str, details: Optional[str] = None) -> Dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def _extract_text_from_response(response_json: Dict[str, Any]) -> str:
    """Минимальное извлечение текста из ответа Yandex Vision.

    В финальной версии эту функцию стоит расширить под полный формат ответа
    DOCUMENT_RECOGNITION: страницы, блоки, строки, таблицы.
    """
    chunks = []

    def walk(obj: Any):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ("text", "fullText") and isinstance(value, str):
                    chunks.append(value)
                else:
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(response_json)
    return "\n".join(dict.fromkeys(chunks))


def _parse_requisites(text: str) -> Dict[str, Any]:
    """Базовый regex-парсер. Нужен как минимальная стартовая версия."""
    normalized = re.sub(r"\s+", " ", text or "").strip()

    doc_type = None
    for candidate in ["УПД", "Акт", "Накладная", "Счёт", "Счет", "Договор"]:
        if re.search(candidate, normalized, flags=re.IGNORECASE):
            doc_type = candidate
            break

    number_match = re.search(r"(?:№|N|Номер[:\s]*)\s*([A-Za-zА-Яа-я0-9\-\/]+)", normalized, re.IGNORECASE)
    date_match = re.search(r"\b(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\b", normalized)
    inn_match = re.search(r"\bИНН\s*[:№]?\s*(\d{10}|\d{12})\b", normalized, re.IGNORECASE)
    kpp_match = re.search(r"\bКПП\s*[:№]?\s*(\d{9})\b", normalized, re.IGNORECASE)
    amount_match = re.search(
        r"(?:Итого|Всего|Сумма)\s*[:\-]?\s*([0-9\s]+(?:[,.]\d{2})?)",
        normalized,
        re.IGNORECASE
    )

    amount = None
    if amount_match:
        raw_amount = amount_match.group(1).replace(" ", "").replace(",", ".")
        try:
            amount = float(raw_amount)
        except ValueError:
            amount = None

    return {
        "document": {
            "type": doc_type,
            "number": number_match.group(1) if number_match else None,
            "date": date_match.group(1) if date_match else None,
            "total_amount": amount,
        },
        "counterparties": [
            {
                "name": None,
                "inn": inn_match.group(1) if inn_match else None,
                "kpp": kpp_match.group(1) if kpp_match else None,
                "role": None,
            }
        ],
        "items": [],
        "raw_text": text,
        "warnings": [],
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
):
    """Главная функция блока Puzzle RPA.

    Принимает PDF, отправляет в Yandex Vision, возвращает dict или JSON-строку.
    """
    try:
        if not token:
            result = _error("EMPTY_TOKEN", "Не передан OAuth-токен Yandex Cloud")
            return json.dumps(result, ensure_ascii=False) if output_format == "json" else result

        if not folder_id:
            result = _error("EMPTY_FOLDER_ID", "Не передан Folder ID Yandex Cloud")
            return json.dumps(result, ensure_ascii=False) if output_format == "json" else result

        if not file_path or not os.path.exists(file_path):
            result = _error("FILE_NOT_FOUND", "PDF-файл не найден", file_path)
            return json.dumps(result, ensure_ascii=False) if output_format == "json" else result

        with open(file_path, "rb") as f:
            encoded_file = base64.b64encode(f.read()).decode("utf-8")

        # Базовый payload. При необходимости адаптируйте поля под актуальный формат Yandex Vision.
        payload = {
            "folderId": folder_id,
            "analyze_specs": [
                {
                    "content": encoded_file,
                    "features": [
                        {
                            "type": "DOCUMENT_RECOGNITION",
                            "documentRecognitionConfig": {
                                "languageCodes": ["ru", "en"] if language == "ru-en" else [language]
                            },
                        }
                    ],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            YANDEX_VISION_URL,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

        if response.status_code in (401, 403):
            result = _error("YANDEX_AUTH_ERROR", "Неверный токен или нет доступа к каталогу", response.text)
            return json.dumps(result, ensure_ascii=False) if output_format == "json" else result

        if response.status_code == 429:
            result = _error("YANDEX_QUOTA_ERROR", "Превышена квота Yandex Vision", response.text)
            return json.dumps(result, ensure_ascii=False) if output_format == "json" else result

        if response.status_code >= 400:
            result = _error("YANDEX_API_ERROR", f"Ошибка Yandex Vision: HTTP {response.status_code}", response.text)
            return json.dumps(result, ensure_ascii=False) if output_format == "json" else result

        try:
            vision_json = response.json()
        except Exception as exc:
            result = _error("BAD_JSON_RESPONSE", "Yandex Vision вернул некорректный JSON", str(exc))
            return json.dumps(result, ensure_ascii=False) if output_format == "json" else result

        text = _extract_text_from_response(vision_json)
        parsed = _parse_requisites(text)

        result = {
            "success": True,
            **parsed,
        }

        return json.dumps(result, ensure_ascii=False, indent=2) if output_format == "json" else result

    except requests.Timeout:
        result = _error("TIMEOUT", "Yandex Vision не ответил за отведённое время")
        return json.dumps(result, ensure_ascii=False) if output_format == "json" else result

    except requests.RequestException as exc:
        result = _error("NETWORK_ERROR", "Сетевая ошибка при обращении к Yandex Vision", str(exc))
        return json.dumps(result, ensure_ascii=False) if output_format == "json" else result

    except Exception as exc:
        result = _error("UNKNOWN_ERROR", "Непредвиденная ошибка блока", str(exc))
        return json.dumps(result, ensure_ascii=False) if output_format == "json" else result
