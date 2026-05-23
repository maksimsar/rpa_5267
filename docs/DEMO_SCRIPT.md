# DEMO_SCRIPT

Сценарий видео до 3 минут для защиты PDFYandexVisionBlock.

## Перед записью

Проверить root-level команды из корня проекта:

```powershell
python -X utf8 tools\smoke_test.py
python -X utf8 tools\validate_output.py examples\expected_output.json
```

Для live demo подготовить реальный PDF и передать реальные `TOKEN`/`FOLDER_ID` только через параметры робота. Не показывать секреты на видео.

## 0:00-0:20 - Блок в Puzzle RPA

Показать Puzzle RPA Studio, наличие блока `PDFYandexVisionBlock` и категорию `Обработка документов -> OCR`.

Текст:

> Это пользовательский блок Puzzle RPA для распознавания PDF через Yandex Vision и возврата реквизитов в dict или JSON.

## 0:20-0:50 - Входные параметры

Показать параметры:

- `TOKEN`;
- `FOLDER_ID`;
- `FILE_PATH`;
- `LANGUAGE`;
- `OUTPUT_FORMAT`.

Текст:

> Секреты не хранятся в коде. На видео реальные значения токена и Folder ID скрыты.

## 0:50-1:30 - Запуск на PDF

Показать запуск робота на PDF-документе. Если live OCR недоступен во время записи, показать root smoke и parser demo:

```powershell
python -X utf8 tools\smoke_test.py
cd PDFYandexVisionBlock
python -X utf8 tools\run_parser_demo.py
```

Текст:

> Offline-проверки подтверждают структуру, импорт блока и JSON-результат. Live OCR отдельно требует настоящий PDF, токен, Folder ID и интернет.

## 1:30-2:10 - JSON-результат

Открыть `examples/expected_output.json`.

Показать:

- `success`;
- `document`;
- `counterparties`;
- `items`;
- `warnings`;
- `meta`.

Текст:

> Результат можно использовать в дальнейших шагах RPA: проверках, маршрутизации, записи в учетную систему или выгрузке.

## 2:10-2:40 - Ошибка success false

Показать пример ошибки: пустой токен, неверный путь к PDF или недоступный каталог.

Текст:

> Вместо traceback блок возвращает `success: false`, код ошибки, сообщение и details. Робот может обработать такую ситуацию штатно.

## 2:40-3:00 - Преимущества

Сказать:

- блок переиспользуемый;
- есть root-level smoke test для жюри;
- старые dev-команды сохранены;
- ошибки стандартизированы;
- архитектура разделена на API, parser, normalizer и schema;
- секреты не попадают в репозиторий.

Финал:

> Решение можно развивать без переписывания всего блока: заменить OCR-провайдера, улучшить парсер или изменить формат результата.
