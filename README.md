# PDFYandexVisionBlock

PDFYandexVisionBlock - пользовательский блок Puzzle RPA для распознавания PDF-документов через Yandex Vision и извлечения реквизитов в формат `dict` или JSON.

Проект готовится как хакатонное решение: блок принимает PDF-файл, учетные данные Yandex Cloud, язык распознавания и формат вывода, отправляет документ в Yandex Vision API, получает OCR-ответ и возвращает структурированный результат без падения процесса при типовых ошибках.

## Что делает блок

1. Получает параметры из Puzzle RPA: `TOKEN`, `FOLDER_ID`, `FILE_PATH`, `LANGUAGE`, `OUTPUT_FORMAT`.
2. Проверяет доступность файла и обязательных параметров.
3. Отправляет PDF в Yandex Vision через `PDFYandexVisionBlock/src/yandex_client.py`.
4. Обрабатывает ответ OCR и ошибки API в едином формате.
5. Возвращает результат как Python `dict` или JSON-строку.

Важно: текущий parser demo показывает расширенную структуризацию результата через `parser.py`, `normalizer.py` и `schema.py`. Puzzle RPA entrypoint в `process_pdf(...)` зависит от финального подключения этой логики при сборке блока, поэтому README не предполагает, что все расширенные поля уже гарантированно возвращаются через Puzzle RPA без интеграционной проверки.

## Какие реквизиты извлекаются

Расширенный parser demo поддерживает извлечение и нормализацию:

- тип документа;
- номер документа;
- дата документа;
- сумма;
- ИНН;
- КПП;
- организации и роли контрагентов;
- табличные позиции: наименование, количество, цена, сумма, единица измерения.

В базовом Puzzle RPA entrypoint результат должен быть проверен после финального подключения `process_pdf(...)` к расширенному парсеру.

## Параметры блока

| Параметр | Назначение |
| --- | --- |
| `TOKEN` | OAuth-токен или другой токен доступа, который команда использует для обращения к Yandex Cloud. Не хранить в коде. |
| `FOLDER_ID` | ID каталога Yandex Cloud, в котором доступен Yandex Vision. |
| `FILE_PATH` | Путь к PDF-файлу на машине, где выполняется робот. |
| `LANGUAGE` | Язык распознавания: `ru`, `en`, `ru-en`. |
| `OUTPUT_FORMAT` | Формат результата: `dict` или `json`. |

## Фактическая структура проекта

```text
rpa_5267/
├── README.md
├── demo_video_link.txt
├── docs/
│   ├── DEMO_SCRIPT.md
│   ├── ARCHITECTURE.md
│   └── TROUBLESHOOTING.md
├── examples/
│   └── sample_response_yandex.json
└── PDFYandexVisionBlock/
    ├── block.json
    ├── meta.json
    ├── values.xml
    ├── code.value.py
    ├── libs.py.json
    ├── typeToName.json
    ├── requirements.txt
    ├── src/
    ├── examples/
    │   ├── demo_result.json
    │   └── expected_output_simple.json
    ├── tools/
    │   ├── run_parser_demo.py
    │   └── validate_output.py
    └── tests/
```

В корне нет `tools/smoke_test.py`, `examples/test_input.pdf` и `examples/expected_output.json`; команды ниже используют только существующие файлы.

## Установка в Puzzle RPA Studio

1. Скопировать или импортировать папку `PDFYandexVisionBlock/` как пользовательское расширение Puzzle RPA Studio согласно механизму вашей версии Studio.
2. Проверить, что рядом с `block.json` лежат `meta.json`, `values.xml`, `code.value.py`, `typeToName.json`, `libs.py.json` и `requirements.txt`.
3. Установить зависимости из `PDFYandexVisionBlock/requirements.txt` в Python-окружение, которое использует Puzzle RPA.
4. Перезапустить Puzzle RPA Studio или обновить список пользовательских блоков.
5. Найти блок в категории `Обработка документов -> OCR`.

## Локальный запуск демо

Parser demo не вызывает Yandex Vision и не требует секретов. Он показывает, как расширенный парсер структурирует текст документа.

```powershell
cd PDFYandexVisionBlock
python tools\run_parser_demo.py
python -X utf8 tools\validate_output.py examples\demo_result.json
```

Файлы демо:

- `PDFYandexVisionBlock/tools/run_parser_demo.py` - локальный запуск парсера на встроенном примере;
- `PDFYandexVisionBlock/tools/validate_output.py` - проверка JSON по расширенной схеме;
- `PDFYandexVisionBlock/examples/demo_result.json` - расширенный результат parser demo;
- `PDFYandexVisionBlock/examples/expected_output_simple.json` - компактный ожидаемый результат;
- `examples/sample_response_yandex.json` - пример OCR-ответа Yandex Vision.

Для полноценного Puzzle RPA demo перед записью видео нужно подставить реальный PDF в `FILE_PATH` и реальные значения `TOKEN`/`FOLDER_ID` через параметры робота. Секреты нельзя показывать на видео.

## Пример успешного JSON

Сокращенный пример результата:

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
  "counterparties": [
    {
      "name": {
        "value": "ООО Ромашка",
        "confidence": 0.78,
        "source": "role_section"
      },
      "inn": {
        "value": "7701234567",
        "confidence": 0.97,
        "source": "role_section"
      },
      "kpp": {
        "value": "770101001",
        "confidence": 0.94,
        "source": "role_section"
      },
      "role": "seller"
    }
  ],
  "items": [
    {
      "name": {
        "value": "Услуга разработки",
        "confidence": 0.9,
        "source": "text_line"
      },
      "quantity": {
        "value": 2.0,
        "confidence": 0.9,
        "source": "text_line"
      },
      "price": {
        "value": 10000.0,
        "confidence": 0.9,
        "source": "text_line"
      },
      "amount": {
        "value": 20000.0,
        "confidence": 0.9,
        "source": "text_line"
      },
      "unit": {
        "value": "шт",
        "confidence": 0.66,
        "source": "text_line"
      }
    }
  ],
  "warnings": [],
  "meta": {
    "parser_version": "2.0.0"
  }
}
```

Полный пример лежит в `PDFYandexVisionBlock/examples/demo_result.json`.

## Пример ошибки

Блок должен возвращать ошибку как данные, а не падать с traceback:

```json
{
  "success": false,
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "PDF-файл не найден",
    "details": "C:\\path\\to\\missing.pdf"
  }
}
```

## Как получить OAuth-токен и Folder ID

OAuth-токен нужен для аутентификации пользователя Yandex Cloud. Актуальное описание формата и ограничений есть в документации Yandex Cloud: <https://yandex.cloud/docs/iam/concepts/authorization/oauth-token>.

Folder ID можно взять в консоли Yandex Cloud на странице каталога или через CLI. Официальная инструкция: <https://yandex.cloud/docs/resource-manager/operations/folder/get-id>.

Практический порядок:

1. Войти в Yandex Cloud под аккаунтом проекта.
2. Убедиться, что у аккаунта есть доступ к каталогу и сервису Yandex Vision.
3. Скопировать `FOLDER_ID` из карточки каталога.
4. Получить токен способом, согласованным командой.
5. Передавать `TOKEN` и `FOLDER_ID` только как параметры блока или переменные окружения, не коммитить их в репозиторий.

## Частые ошибки

- `EMPTY_TOKEN` - не передан токен.
- `EMPTY_FOLDER_ID` - не передан ID каталога.
- `FILE_NOT_FOUND` - путь к PDF указан неверно.
- `INVALID_FILE_TYPE` - выбран не PDF-файл.
- `YANDEX_AUTH_ERROR` - токен неверный или у него нет доступа.
- `YANDEX_QUOTA_ERROR` - превышена квота Yandex Vision.
- `YANDEX_TIMEOUT` - сервис не ответил за отведенное время.
- `MISSING_DEPENDENCY` - не установлены зависимости Python.

Подробная таблица находится в `docs/TROUBLESHOOTING.md`.

## Ограничения

- Распознавание зависит от качества скана, языка документа и ответа Yandex Vision.
- Большие PDF могут быть отклонены локальной проверкой или API.
- Локальный parser demo не является сетевым smoke test и не проверяет настоящий доступ к Yandex Vision.
- В текущем репозитории нет `examples/test_input.pdf`; реальный PDF для демонстрации команда подставляет отдельно.
- Перед защитой нужно убедиться, что финальный `process_pdf(...)` использует нужный parser/result format.

## Безопасность

- Не хранить `TOKEN`, `FOLDER_ID`, OAuth-токены, ключи сервисных аккаунтов и другие секреты в коде.
- Не добавлять секреты в README, docs, examples, screenshots и видео.
- Не коммитить `.env`, `secrets.json`, файлы с token/credentials в названии.
- Перед сдачей запускать поиск по секретам и просматривать совпадения вручную.

## Видеодемонстрация

Ссылка и требования к видео находятся в `demo_video_link.txt`.
