# PDFYandexVisionBlock

PDFYandexVisionBlock - пользовательский блок Puzzle RPA для распознавания PDF-документов через Yandex Vision и извлечения реквизитов в `dict` или JSON.

Блок принимает PDF-файл, `TOKEN`, `FOLDER_ID`, язык OCR и формат вывода, отправляет документ в Yandex Vision API, получает OCR-ответ и возвращает результат без падения процесса при типовых ошибках.

## Что делает блок

1. Получает входные параметры из Puzzle RPA.
2. Проверяет обязательные параметры и доступность PDF-файла.
3. Отправляет PDF в Yandex Vision через `PDFYandexVisionBlock/src/yandex_client.py`.
4. Обрабатывает ответ OCR или ошибку API.
5. Возвращает результат как Python `dict` или JSON-строку.


## Извлекаемые поля

Расширенный parser demo показывает извлечение:

- тип документа;
- номер;
- дата;
- сумма;
- ИНН;
- КПП;
- организации и роли контрагентов;
- табличные позиции: наименование, количество, цена, сумма, единица измерения.

## Структура проекта

```text
pdf-yandex-vision-rpa/
├── PDFYandexVisionBlock/
│   ├── block.json
│   ├── meta.json
│   ├── values.xml
│   ├── code.value.py
│   ├── libs.py.json
│   ├── typeToName.json
│   ├── requirements.txt
│   ├── src/
│   ├── tools/
│   │   ├── run_parser_demo.py
│   │   └── validate_output.py
│   ├── examples/
│   │   ├── demo_result.json
│   │   └── expected_output_simple.json
│   └── tests/
├── examples/
│   ├── sample_response_yandex.json
│   ├── expected_output.json
│   └── README_TEST_INPUT.md
├── tools/
│   ├── smoke_test.py
│   └── validate_output.py
├── docs/
│   ├── DEMO_SCRIPT.md
│   ├── ARCHITECTURE.md
│   └── TROUBLESHOOTING.md
├── README.md
├── CHECKPOINTS.md
└── demo_video_link.txt
```

`examples/test_input.pdf` не хранится в репозитории. Реальный PDF добавляется локально перед live demo, если документ не содержит приватных данных.

## Параметры блока

| Параметр | Назначение |
| --- | --- |
| `TOKEN` | Токен доступа к Yandex Cloud. Передается только как параметр или безопасное runtime-значение. |
| `FOLDER_ID` | ID каталога Yandex Cloud, где доступен Yandex Vision. |
| `FILE_PATH` | Путь к PDF-файлу на машине, где выполняется робот. |
| `LANGUAGE` | Язык распознавания: `ru`, `en`, `ru-en`. |
| `OUTPUT_FORMAT` | Формат результата: `dict` или `json`. |

## Установка в Puzzle RPA Studio

1. Импортировать или скопировать папку `PDFYandexVisionBlock/` как пользовательское расширение Puzzle RPA Studio.
2. Проверить, что внутри есть `block.json`, `meta.json`, `values.xml`, `code.value.py`, `typeToName.json`, `libs.py.json`.
4. Перезапустить Studio или обновить список пользовательских блоков.
5. Найти блок в категории `Обработка документов -> OCR`.

## Root-level проверки для сдачи

Эти команды запускаются из корня проекта и не требуют реальных секретов:

```powershell
python -X utf8 tools\smoke_test.py
python -X utf8 tools\validate_output.py examples\expected_output.json
```

`tools/smoke_test.py` проверяет структуру, импорт `process_pdf`, базовый JSON и offline-парсинг sample response. Live OCR не запускается без реальных `TOKEN`, `FOLDER_ID`, PDF и сети.

## Пример success JSON

Сокращенный пример из `examples/expected_output.json`:

```json
{
  "success": true,
  "document": {
    "type": {
      "value": "Счёт",
      "confidence": 0.92,
      "source": "regex"
    },
    "number": {
      "value": "ABC-123",
      "confidence": 0.92,
      "source": "regex"
    },
    "date": {
      "value": "2026-05-22",
      "confidence": 0.92,
      "source": "regex"
    },
    "total_amount": {
      "value": 25500.5,
      "confidence": 0.98,
      "source": "regex"
    }
  },
  "counterparties": [],
  "items": [],
  "warnings": []
}
```

Полный расширенный пример находится в `examples/expected_output.json` и `PDFYandexVisionBlock/examples/demo_result.json`.

## Пример success false

```json
{
  "success": false,
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "PDF-файл не найден",
    "details": "path/to/missing.pdf"
  }
}
```

## Безопасность

- Секреты не хранятся в коде.
- `TOKEN` и `FOLDER_ID` передаются только как параметры робота или безопасные runtime-значения.
- `.env`, `secrets.json`, файлы с token/credentials в названии не коммитятся.

## Частые ошибки

- `EMPTY_TOKEN` - не передан токен.
- `EMPTY_FOLDER_ID` - не передан ID каталога.
- `FILE_NOT_FOUND` - PDF не найден.
- `INVALID_FILE_TYPE` - выбран не PDF.
- `YANDEX_AUTH_ERROR` - нет доступа к Yandex Cloud.
- `YANDEX_TIMEOUT` - Yandex Vision не ответил вовремя.
- `MISSING_DEPENDENCY` - не установлены зависимости.

Подробности: `docs/TROUBLESHOOTING.md`.

## Ограничения

- Для live OCR нужен интернет.
- Для live OCR нужны реальные `TOKEN`, `FOLDER_ID` и PDF.
- Качество скана влияет на OCR и итоговый парсинг.
- Установку блока в Puzzle RPA Studio нужно проверить отдельно на машине демонстрации.

## Видео

Ссылка и состав видео находятся в `demo_video_link.txt`.
