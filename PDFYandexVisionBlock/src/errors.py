from typing import Any, Dict, Optional


def make_error(code: str, message: str, details: Optional[Any] = None) -> Dict[str, Any]:
    # Единый формат ошибки блока.
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def make_success(data: Dict[str, Any]) -> Dict[str, Any]:
    # Единый формат успешного ответа.
    return {
        "success": True,
        "data": data,
    }
