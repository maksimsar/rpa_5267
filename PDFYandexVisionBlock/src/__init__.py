import json
import os
from typing import Any, Dict, Optional

try:
    import requests
except ModuleNotFoundError:
    requests = None

from .parser import parse_requisites_simple
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
    # Чистим значения из полей блока.
    if value is None:
        return ""
    return str(value).strip().strip('"').strip("'")


def _format_result(result: Dict[str, Any], output_format: str):
    # Возвращаем dict или JSON-строку.
    output_format = _clean_text(output_format).lower() or "dict"

    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    return result


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
    # Точка входа блока Puzzle RPA.
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

        vision_json = vision_result.get("data", {})
        parsed = parse_requisites_simple(vision_json)

        if "success" not in parsed:
            parsed = {
                "success": True,
                **parsed,
            }

        return _format_result(parsed, output_format)

    except Exception as exc:
        return _format_result(
            _error("UNKNOWN_ERROR", "Непредвиденная ошибка блока", str(exc)),
            output_format if "output_format" in locals() else "dict",
        )
