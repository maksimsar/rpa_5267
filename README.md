# PDFYandexVisionBlock — базовая минимальная структура

Это стартовый ZIP для кейса с блоком Puzzle RPA:
PDF → Yandex Vision → извлечение реквизитов → dict/json.

## Что внутри

- `PDFYandexVisionBlock/block.json` — описание блока и входов.
- `PDFYandexVisionBlock/meta.json` — режим value и внутреннее логирование.
- `PDFYandexVisionBlock/values.xml` — категория `Обработка документов → OCR`.
- `PDFYandexVisionBlock/code.value.py` — вызов `process_pdf`.
- `PDFYandexVisionBlock/requirements.txt` — зависимости.
- `PDFYandexVisionBlock/src/__init__.py` — минимальная базовая Python-логика.

## Важно

Это минимальная заготовка. Перед финальной сдачей нужно:
1. Проверить точный формат `values.xml` и `code.value.py` под вашу версию Puzzle RPA.
2. Расширить парсер таблиц и контрагентов.
3. Протестировать на реальном PDF и сохранить `expected_output.json`.
4. Не хранить токен и folder_id в коде.
