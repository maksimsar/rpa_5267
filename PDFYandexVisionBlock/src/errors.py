from typing import Any, Dict, Optional


def make_error(code: str, message: str, details: Optional[Any] = None) -> Dict[str, Any]:
    """
    Единый формат ошибки для всего блока. Нужен, чтобы Puzzle RPA не падал с traceback,
    а возвращал понятный JSON/dict.
    """
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def make_success(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Единый формат успешного ответа API-клиента.
    """
    return {
        "success": True,
        "data": data,
    }