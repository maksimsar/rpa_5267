"""
INTEGRATION_PATCH_FOR_SRC_INIT.py

Этот фрагмент нужен Кириллу/Стасу для подключения твоей Python-части
к главному файлу PDFYandexVisionBlock/src/__init__.py.

После получения vision_json от Yandex Vision старый парсинг заменить на:

    from .parser import parse_requisites, parse_requisites_simple

    parsed = parse_requisites(vision_json)

    if output_format == "json":
        return json.dumps(parsed, ensure_ascii=False, indent=2)

    return parsed

Если нужен компактный формат без confidence/source:

    parsed = parse_requisites_simple(vision_json)
"""
