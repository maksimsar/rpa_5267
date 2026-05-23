# PDFYandexVisionBlock

PDFYandexVisionBlock - хакатонный пользовательский блок Puzzle RPA для распознавания PDF-документов через Yandex Vision и извлечения реквизитов в `dict` или JSON.

Блок принимает PDF-файл, `TOKEN`, `FOLDER_ID`, язык OCR и формат вывода, отправляет документ в Yandex Vision API, получает OCR-ответ и возвращает результат без падения процесса при типовых ошибках.

## Что делает блок

1. Получает входные параметры из Puzzle RPA.
2. Проверяет обязательные параметры и доступность PDF-файла.
3. Отправляет PDF в Yandex Vision через `PDFYandexVisionBlock/src/yandex_client.py`.
4. Обрабатывает ответ OCR или ошибку API.
5. Возвращает результат как Python `dict` или JSON-строку.

Текущий важный нюанс: расширенные `parser.py`, `normalizer.py` и `schema.py` уже есть и проверяются через parser demo. При этом `process_pdf(...)` в `PDFYandexVisionBlock/src/__init__.py` сейчас после OCR использует базовую встроенную структуризацию из этого же файла. Перед финальной демонстрацией через Puzzle RPA нужно убедиться, что entrypoint подключен к нужному формату результата.

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

`examples/test_input.pdf` не хранится в репозитории. Реальный PDF добавляется локально перед live demo, если документ не содержит приватных данных или команда готова показывать его на записи.

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
2. Проверить, что внутри есть `block.json`, `meta.json`, `values.xml`, `code.value.py`, `typeToName.json`, `libs.py.json`, `requirements.txt`.
3. Установить зависимости в Python-окружение Puzzle RPA:

```powershell
cd PDFYandexVisionBlock
python -m pip install -r requirements.txt
```

4. Перезапустить Studio или обновить список пользовательских блоков.
5. Найти блок в категории `Обработка документов -> OCR`.

## Root-level проверки для сдачи

Эти команды запускаются из корня проекта и не требуют реальных секретов:

```powershell
python -X utf8 tools\smoke_test.py
python -X utf8 tools\validate_output.py examples\expected_output.json
```

`tools/smoke_test.py` проверяет структуру, импорт `process_pdf`, базовый JSON и offline-парсинг sample response. Live OCR не запускается без реальных `TOKEN`, `FOLDER_ID`, PDF и сети.

## Старые dev-проверки

Эти команды сохранены для совместимости и запускаются из `PDFYandexVisionBlock/`:

```powershell
python -B -m unittest discover -s tests
python -X utf8 tools\run_parser_demo.py
python -X utf8 tools\validate_output.py examples\demo_result.json
python -X utf8 -c "from src import process_pdf; print(callable(process_pdf))"
```

`tools/run_parser_demo.py` генерирует `PDFYandexVisionBlock/examples/demo_result.json` из встроенного текста и показывает расширенный parser demo без обращения к Yandex Vision.

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

## OAuth-токен и Folder ID

Токен и `FOLDER_ID` команда получает в Yandex Cloud под аккаунтом, которому разрешен доступ к каталогу и Yandex Vision. Актуальные инструкции нужно сверять с официальной документацией Yandex Cloud:

- OAuth-токены: <https://yandex.cloud/docs/iam/concepts/authorization/oauth-token>
- Folder ID: <https://yandex.cloud/docs/resource-manager/operations/folder/get-id>

Не сохраняйте реальные значения в репозитории, docs, screenshots или видео.

## Безопасность

- Секреты не хранятся в коде.
- `TOKEN` и `FOLDER_ID` передаются только как параметры робота или безопасные runtime-значения.
- `.env`, `secrets.json`, файлы с token/credentials в названии не коммитятся.
- Перед сдачей выполнить secret scan:

```powershell
rg -n -i -uu --glob "!.git/**" "y0_|bearer [a-z0-9_\-\.]+|oauth_token|real_token|secret|\.env" .
```

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
- `examples/test_input.pdf` может не храниться в репозитории, если содержит приватные данные.
- Установку блока в Puzzle RPA Studio нужно проверить отдельно на машине демонстрации.

## Видео

Ссылка и состав видео находятся в `demo_video_link.txt`.
