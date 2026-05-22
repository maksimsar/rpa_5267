import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests

from .errors import make_error, make_success


YANDEX_VISION_URL = "https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze"
MAX_FILE_SIZE_MB = 20


def _normalize_language(language: str) -> List[str]:
    """
    Приводит значение из выпадающего списка Puzzle RPA
    к списку языков для Yandex Vision.
    """
    language = (language or "ru").strip().lower()

    if language in ("ru-en", "ru_en", "both", "mixed"):
        return ["ru", "en"]

    if language in ("ru", "en"):
        return [language]

    return ["ru"]


def _validate_pdf_file(file_path: str) -> Dict[str, Any] | None:
    """
    Проверяет существование PDF-файла и базовые ограничения.
    Возвращает ошибку или None, если всё нормально.
    """
    if not file_path:
        return make_error(
            "EMPTY_FILE_PATH",
            "Не передан путь к PDF-файлу",
        )

    path = Path(file_path)

    if not path.exists():
        return make_error(
            "FILE_NOT_FOUND",
            "PDF-файл не найден",
            str(path),
        )

    if not path.is_file():
        return make_error(
            "FILE_PATH_IS_NOT_FILE",
            "Переданный путь не является файлом",
            str(path),
        )

    if path.suffix.lower() != ".pdf":
        return make_error(
            "INVALID_FILE_TYPE",
            "Файл должен быть PDF",
            str(path),
        )

    file_size_mb = path.stat().st_size / 1024 / 1024
    if file_size_mb > MAX_FILE_SIZE_MB:
        return make_error(
            "FILE_TOO_LARGE",
            f"PDF-файл больше {MAX_FILE_SIZE_MB} МБ",
            {
                "file_path": str(path),
                "size_mb": round(file_size_mb, 2),
            },
        )

    return None


def _read_file_base64(file_path: str) -> str:
    """
    Читает PDF и возвращает base64-строку.
    """
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def _build_payload(folder_id: str, encoded_pdf: str, language: str) -> Dict[str, Any]:
    """
    Формирует тело запроса к Yandex Vision.

    По ТЗ хакатона используется batchAnalyze
    и feature DOCUMENT_RECOGNITION.
    """
    return {
        "folderId": folder_id,
        "analyze_specs": [
            {
                "content": encoded_pdf,
                "mime_type": "application/pdf",
                "features": [
                    {
                        "type": "DOCUMENT_RECOGNITION",
                        "documentRecognitionConfig": {
                            "languageCodes": _normalize_language(language)
                        },
                    }
                ],
            }
        ],
    }


def _parse_yandex_error(response: requests.Response) -> Dict[str, Any]:
    """
    Преобразует HTTP-ошибку Yandex Vision в наш единый формат.
    """
    status_code = response.status_code

    try:
        body = response.json()
    except ValueError:
        body = response.text

    if status_code in (401, 403):
        return make_error(
            "YANDEX_AUTH_ERROR",
            "Неверный токен или нет доступа к каталогу Yandex Cloud",
            body,
        )

    if status_code == 404:
        return make_error(
            "YANDEX_FOLDER_NOT_FOUND",
            "Каталог Yandex Cloud не найден или недоступен",
            body,
        )

    if status_code == 413:
        return make_error(
            "YANDEX_FILE_TOO_LARGE",
            "Yandex Vision отклонил файл из-за размера",
            body,
        )

    if status_code == 429:
        return make_error(
            "YANDEX_QUOTA_ERROR",
            "Превышена квота Yandex Vision",
            body,
        )

    if 500 <= status_code <= 599:
        return make_error(
            "YANDEX_SERVER_ERROR",
            f"Ошибка на стороне Yandex Vision: HTTP {status_code}",
            body,
        )

    return make_error(
        "YANDEX_API_ERROR",
        f"Ошибка Yandex Vision: HTTP {status_code}",
        body,
    )


def call_yandex_vision(
    token: str,
    folder_id: str,
    file_path: str,
    language: str = "ru",
    timeout: int = 45,
) -> Dict[str, Any]:
    """
    Отправляет PDF в Yandex Vision и возвращает JSON-ответ.

    Возвращает:
    {
        "success": true,
        "data": {...}
    }

    или:
    {
        "success": false,
        "error": {
            "code": "...",
            "message": "...",
            "details": ...
        }
    }
    """
    if not token:
        return make_error(
            "EMPTY_TOKEN",
            "Не передан OAuth-токен Yandex Cloud",
        )

    if not folder_id:
        return make_error(
            "EMPTY_FOLDER_ID",
            "Не передан Folder ID Yandex Cloud",
        )

    file_error = _validate_pdf_file(file_path)
    if file_error:
        return file_error

    try:
        encoded_pdf = _read_file_base64(file_path)
    except PermissionError as exc:
        return make_error(
            "FILE_PERMISSION_ERROR",
            "Нет прав на чтение PDF-файла",
            str(exc),
        )
    except OSError as exc:
        return make_error(
            "FILE_READ_ERROR",
            "Не удалось прочитать PDF-файл",
            str(exc),
        )

    payload = _build_payload(folder_id, encoded_pdf, language)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            YANDEX_VISION_URL,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    except requests.Timeout:
        return make_error(
            "YANDEX_TIMEOUT",
            f"Yandex Vision не ответил за {timeout} секунд",
        )

    except requests.ConnectionError as exc:
        return make_error(
            "YANDEX_CONNECTION_ERROR",
            "Нет соединения с Yandex Vision или отсутствует интернет",
            str(exc),
        )

    except requests.RequestException as exc:
        return make_error(
            "YANDEX_REQUEST_ERROR",
            "Ошибка HTTP-запроса к Yandex Vision",
            str(exc),
        )

    if response.status_code >= 400:
        return _parse_yandex_error(response)

    try:
        response_json = response.json()
    except json.JSONDecodeError as exc:
        return make_error(
            "YANDEX_INVALID_JSON",
            "Yandex Vision вернул некорректный JSON",
            {
                "exception": str(exc),
                "response_text": response.text[:1000],
            },
        )

    return make_success(response_json)