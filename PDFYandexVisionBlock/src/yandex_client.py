import base64
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .errors import make_error, make_success


YANDEX_OCR_ASYNC_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeTextAsync"
YANDEX_OCR_GET_RECOGNITION_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/getRecognition"
YANDEX_IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"

MAX_FILE_SIZE_MB = 10
OCR_ASYNC_MAX_WAIT_SECONDS = 180
OCR_ASYNC_POLL_INTERVAL_SECONDS = 5


def _clean_text(value: Any) -> str:
    """
    Приводит вход из Puzzle RPA к обычной строке:
    убирает None, пробелы и случайные кавычки по краям.
    """
    if value is None:
        return ""
    return str(value).strip().strip('"').strip("'")


def _is_oauth_token(token: str) -> bool:
    """
    OAuth-токен Яндекса обычно начинается с y0_.
    IAM-токен обычно начинается с t1.
    """
    token = _clean_text(token)
    return token.startswith("y0_")


def _get_iam_token(oauth_token: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Получает IAM-токен по OAuth-токену.

    Это нужно, чтобы пользователь мог вставить OAuth-токен прямо в блок Puzzle RPA,
    а код сам получил временный IAM-токен для Yandex OCR API.
    """
    oauth_token = _clean_text(oauth_token)

    if not oauth_token:
        return make_error(
            "EMPTY_OAUTH_TOKEN",
            "Не передан OAuth-токен для получения IAM-токена",
        )

    try:
        response = requests.post(
            YANDEX_IAM_URL,
            json={"yandexPassportOauthToken": oauth_token},
            timeout=timeout,
        )

        if response.status_code >= 400:
            return _parse_http_error(
                response,
                "YANDEX_IAM_TOKEN_ERROR",
                "Не удалось получить IAM-токен по OAuth-токену",
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            return make_error(
                "YANDEX_IAM_INVALID_JSON",
                "Yandex IAM вернул некорректный JSON",
                {
                    "exception": str(exc),
                    "response_text": response.text[:1000],
                },
            )

        iam_token = data.get("iamToken")

        if not iam_token:
            return make_error(
                "YANDEX_IAM_TOKEN_MISSING",
                "Yandex IAM не вернул поле iamToken",
                data,
            )

        return make_success(iam_token)

    except requests.Timeout:
        return make_error(
            "YANDEX_IAM_TIMEOUT",
            f"Yandex IAM не ответил за {timeout} секунд",
        )

    except requests.ConnectionError as exc:
        return make_error(
            "YANDEX_IAM_CONNECTION_ERROR",
            "Нет соединения с Yandex IAM или отсутствует интернет",
            str(exc),
        )

    except requests.RequestException as exc:
        return make_error(
            "YANDEX_IAM_REQUEST_ERROR",
            "Ошибка HTTP-запроса к Yandex IAM",
            str(exc),
        )


def _normalize_language(language: str) -> List[str]:
    """
    Приводит значение из выпадающего списка Puzzle RPA
    к списку языков для Yandex OCR API.
    """
    language = _clean_text(language).lower() or "ru"

    if language in ("ru-en", "ru_en", "ru + en", "russian + english", "both", "mixed", "русский + английский"):
        return ["ru", "en"]

    if language in ("ru", "русский", "russian"):
        return ["ru"]

    if language in ("en", "английский", "english"):
        return ["en"]

    if language in ("auto", "*", "авто", "автоматически"):
        return ["*"]

    return ["ru"]


def _validate_pdf_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Проверяет существование PDF-файла и базовые ограничения OCR API.
    """
    file_path = _clean_text(file_path)

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
            f"PDF-файл больше {MAX_FILE_SIZE_MB} МБ. Yandex OCR API ограничивает размер PDF-файла.",
            {
                "file_path": str(path),
                "size_mb": round(file_size_mb, 2),
                "max_size_mb": MAX_FILE_SIZE_MB,
            },
        )

    return None


def _read_file_base64(file_path: str) -> str:
    """
    Читает PDF и возвращает base64-строку.
    """
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def _build_ocr_payload(encoded_pdf: str, language: str) -> Dict[str, Any]:
    """
    Формирует payload для Yandex OCR API.

    Для PDF используем async OCR API, потому что он подходит для многостраничных документов.
    """
    language_codes = _normalize_language(language)

    return {
        "mimeType": "application/pdf",
        "languageCodes": language_codes if language_codes else ["*"],
        "model": "page",
        "content": encoded_pdf,
    }


def _build_ocr_headers(token: str, folder_id: str) -> Dict[str, str]:
    """
    Заголовки для OCR API.
    Folder ID передаётся через x-folder-id.
    """
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "x-folder-id": folder_id,
        "x-data-logging-enabled": "true",
    }


def _safe_response_body(response: requests.Response) -> Any:
    """
    Безопасно достаёт тело HTTP-ответа.
    """
    try:
        return response.json()
    except ValueError:
        return response.text[:2000]


def _parse_http_error(
    response: requests.Response,
    default_code: str,
    default_message: str,
) -> Dict[str, Any]:
    """
    Универсально разбирает HTTP-ошибку в единый формат.
    """
    details = _safe_response_body(response)
    status_code = response.status_code

    if status_code in (401, 403):
        return make_error(
            "YANDEX_AUTH_ERROR",
            "Неверный токен или нет доступа к каталогу Yandex Cloud",
            details,
        )

    if status_code == 404:
        return make_error(
            "YANDEX_FOLDER_NOT_FOUND",
            "Каталог Yandex Cloud не найден или недоступен",
            details,
        )

    if status_code == 413:
        return make_error(
            "YANDEX_FILE_TOO_LARGE",
            "Yandex OCR отклонил файл из-за размера",
            details,
        )

    if status_code == 429:
        return make_error(
            "YANDEX_QUOTA_ERROR",
            "Превышена квота Yandex OCR",
            details,
        )

    if status_code == 499:
        return make_error(
            "YANDEX_SERVER_CANCELLED",
            "Yandex OCR отменил обработку документа. Документ может быть слишком большим или сложным для текущей операции.",
            details,
        )

    if 500 <= status_code <= 599:
        return make_error(
            "YANDEX_SERVER_ERROR",
            f"Ошибка на стороне Yandex OCR: HTTP {status_code}",
            details,
        )

    return make_error(
        default_code,
        f"{default_message}: HTTP {status_code}",
        details,
    )


def _parse_json_or_json_lines(response: requests.Response) -> Dict[str, Any]:
    """
    Разбирает ответ Yandex OCR.

    Обычно это обычный JSON.
    Но если сервис вернёт несколько JSON-секций построчно,
    мы тоже не падаем, а собираем их в pages.
    """
    try:
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"result": data}
    except json.JSONDecodeError:
        pass

    text = response.text.strip()

    if not text:
        raise json.JSONDecodeError("Empty response", response.text, 0)

    pages = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            pages.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if pages:
        return {
            "result": {
                "pages": pages
            }
        }

    raise json.JSONDecodeError("Invalid JSON response", response.text, 0)


def _is_operation_not_ready(response: requests.Response) -> bool:
    """
    Проверяет, что async-операция ещё не готова.

    У разных API это может выглядеть по-разному,
    поэтому проверка мягкая, а не хрупкая до истерики.
    """
    if response.status_code in (202, 204, 408, 409, 425, 429):
        return True

    body = _safe_response_body(response)
    text = json.dumps(body, ensure_ascii=False).lower()

    markers = (
        "not ready",
        "not completed",
        "in progress",
        "running",
        "try later",
        "operation is not completed",
        "operation not completed",
    )

    return response.status_code in (400, 404, 409, 429) and any(marker in text for marker in markers)


def _call_yandex_ocr_async_pdf(
    token: str,
    folder_id: str,
    encoded_pdf: str,
    language: str,
    timeout: int = 45,
    max_wait_seconds: int = OCR_ASYNC_MAX_WAIT_SECONDS,
    poll_interval_seconds: int = OCR_ASYNC_POLL_INTERVAL_SECONDS,
) -> Dict[str, Any]:
    """
    Асинхронно распознаёт PDF через Yandex OCR API.

    Подходит для многостраничных и более тяжёлых PDF.
    """
    payload = _build_ocr_payload(encoded_pdf, language)
    headers = _build_ocr_headers(token, folder_id)

    try:
        start_response = requests.post(
            YANDEX_OCR_ASYNC_URL,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    except requests.Timeout:
        return make_error(
            "YANDEX_OCR_ASYNC_START_TIMEOUT",
            f"Yandex OCR не принял задачу за {timeout} секунд",
        )

    except requests.ConnectionError as exc:
        return make_error(
            "YANDEX_OCR_CONNECTION_ERROR",
            "Нет соединения с Yandex OCR или отсутствует интернет",
            str(exc),
        )

    except requests.RequestException as exc:
        return make_error(
            "YANDEX_OCR_REQUEST_ERROR",
            "Ошибка HTTP-запроса к Yandex OCR",
            str(exc),
        )

    if start_response.status_code >= 400:
        return _parse_http_error(
            start_response,
            "YANDEX_OCR_ASYNC_START_ERROR",
            "Ошибка запуска асинхронного OCR",
        )

    try:
        operation = start_response.json()
    except json.JSONDecodeError as exc:
        return make_error(
            "YANDEX_OCR_ASYNC_INVALID_JSON",
            "Yandex OCR вернул некорректный JSON при запуске async-операции",
            {
                "exception": str(exc),
                "response_text": start_response.text[:1000],
            },
        )

    operation_id = operation.get("id")

    if not operation_id:
        return make_error(
            "YANDEX_OCR_OPERATION_ID_MISSING",
            "Yandex OCR не вернул id операции распознавания",
            operation,
        )

    deadline = time.time() + max_wait_seconds
    last_error = None
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        time.sleep(poll_interval_seconds)

        try:
            result_response = requests.get(
                YANDEX_OCR_GET_RECOGNITION_URL,
                headers=headers,
                params={"operationId": operation_id},
                timeout=timeout,
            )

        except requests.Timeout:
            last_error = {
                "code": "YANDEX_OCR_GET_RESULT_TIMEOUT",
                "message": f"Yandex OCR не вернул результат за {timeout} секунд",
                "operation_id": operation_id,
                "attempt": attempt,
            }
            continue

        except requests.ConnectionError as exc:
            return make_error(
                "YANDEX_OCR_CONNECTION_ERROR",
                "Нет соединения с Yandex OCR при получении результата",
                str(exc),
            )

        except requests.RequestException as exc:
            return make_error(
                "YANDEX_OCR_GET_RESULT_REQUEST_ERROR",
                "Ошибка HTTP-запроса при получении результата OCR",
                str(exc),
            )

        if result_response.status_code == 200:
            try:
                result_json = _parse_json_or_json_lines(result_response)
            except json.JSONDecodeError as exc:
                return make_error(
                    "YANDEX_OCR_RESULT_INVALID_JSON",
                    "Yandex OCR вернул некорректный JSON результата",
                    {
                        "exception": str(exc),
                        "response_text": result_response.text[:1000],
                    },
                )

            if isinstance(result_json, dict) and result_json.get("done") is False:
                last_error = {
                    "operation_id": operation_id,
                    "attempt": attempt,
                    "status": "done_false",
                    "response": result_json,
                }
                continue

            return make_success(
                {
                    "ocr_api": "recognizeTextAsync",
                    "operation_id": operation_id,
                    "poll_attempts": attempt,
                    "result": result_json,
                }
            )

        if _is_operation_not_ready(result_response):
            last_error = {
                "operation_id": operation_id,
                "attempt": attempt,
                "status_code": result_response.status_code,
                "response": _safe_response_body(result_response),
            }
            continue

        return _parse_http_error(
            result_response,
            "YANDEX_OCR_GET_RESULT_ERROR",
            "Ошибка получения результата асинхронного OCR",
        )

    return make_error(
        "YANDEX_OCR_ASYNC_TIMEOUT",
        f"Yandex OCR не завершил распознавание за {max_wait_seconds} секунд",
        {
            "operation_id": operation_id,
            "last_error": last_error,
            "max_wait_seconds": max_wait_seconds,
            "poll_interval_seconds": poll_interval_seconds,
        },
    )


def call_yandex_vision(
    token: str,
    folder_id: str,
    file_path: str,
    language: str = "ru",
    timeout: int = 45,
) -> Dict[str, Any]:
    """
    Отправляет PDF в Yandex OCR API и возвращает JSON-ответ.

    Функция называется call_yandex_vision для совместимости с остальным проектом,
    но внутри используется новый OCR API recognizeTextAsync.

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
    token = _clean_text(token)
    folder_id = _clean_text(folder_id)
    file_path = _clean_text(file_path)
    language = _clean_text(language) or "ru"

    if not token:
        return make_error(
            "EMPTY_TOKEN",
            "Не передан токен Yandex Cloud",
        )

    if _is_oauth_token(token):
        iam_result = _get_iam_token(token, timeout=timeout)

        if not iam_result.get("success"):
            return iam_result

        token = iam_result["data"]

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

    return _call_yandex_ocr_async_pdf(
        token=token,
        folder_id=folder_id,
        encoded_pdf=encoded_pdf,
        language=language,
        timeout=timeout,
    )