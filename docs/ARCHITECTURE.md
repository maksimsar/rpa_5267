# ARCHITECTURE

PDFYandexVisionBlock состоит из Puzzle RPA слоя, Python entrypoint, API-клиента Yandex Vision, слоя ошибок, парсера, нормализации и схемы результата.

## Общая схема

```text
Puzzle RPA block
→ code.value.py
→ process_pdf(...)
→ yandex_client.call_yandex_vision(...)
→ Yandex Vision API
→ parser
→ normalizer
→ dict/json result
```

## Слои решения

### Puzzle RPA слой

Файлы:

- `PDFYandexVisionBlock/block.json`
- `PDFYandexVisionBlock/values.xml`
- `PDFYandexVisionBlock/code.value.py`
- `PDFYandexVisionBlock/meta.json`
- `PDFYandexVisionBlock/typeToName.json`

Этот слой описывает визуальный блок, категорию `Обработка документов -> OCR`, входные параметры и вызов Python-функции `process_pdf(...)`.

### API-слой

Файл: `PDFYandexVisionBlock/src/yandex_client.py`.

Задачи:

- проверить PDF-файл;
- прочитать PDF и подготовить payload;
- отправить запрос в Yandex Vision;
- обработать HTTP-ошибки и некорректный JSON;
- вернуть единый результат `success: true/false`.

### Слой ошибок

Файл: `PDFYandexVisionBlock/src/errors.py`.

Содержит helpers для единого формата:

```json
{
  "success": false,
  "error": {
    "code": "...",
    "message": "...",
    "details": "..."
  }
}
```

### Слой парсинга

Файл: `PDFYandexVisionBlock/src/parser.py`.

Парсер извлекает из текста или OCR-ответа:

- тип документа;
- номер;
- дату;
- сумму;
- контрагентов;
- ИНН и КПП;
- табличные позиции.

### Слой нормализации

Файл: `PDFYandexVisionBlock/src/normalizer.py`.

Нормализует даты, суммы, ИНН, КПП, названия организаций, единицы измерения и OCR-артефакты.

### Схема результата

Файл: `PDFYandexVisionBlock/src/schema.py`.

Задает dataclass-структуры результата, включая `FieldValue` с `value`, `confidence` и `source`. Это полезно для защиты: видно не только значение, но и способ его извлечения.

### Инструменты проверки

Файлы:

- `PDFYandexVisionBlock/tools/run_parser_demo.py`
- `PDFYandexVisionBlock/tools/validate_output.py`

`run_parser_demo.py` запускает расширенный parser demo без Puzzle RPA и без Yandex Vision. `validate_output.py` проверяет JSON на соответствие расширенной схеме.

## Почему архитектура расширяемая

- Puzzle RPA слой отделен от Python-логики.
- API-клиент отделен от parser/normalizer.
- Ошибки имеют единый формат и не завязаны на конкретный UI.
- Parser и normalizer можно развивать отдельно от сетевого вызова.
- Schema фиксирует контракт результата и упрощает тестирование.

## Где менять OCR-провайдера

Замену OCR-провайдера лучше делать в API-слое: добавить новый клиент рядом с `yandex_client.py` или заменить реализацию вызова в `process_pdf(...)`, сохранив тот же формат успешного OCR-ответа или адаптер к `parser.py`.

## Где улучшать парсер

Парсер улучшается в `PDFYandexVisionBlock/src/parser.py`, а нормализация значений - в `PDFYandexVisionBlock/src/normalizer.py`. Тесты лежат в `PDFYandexVisionBlock/tests/`.

## Где менять формат результата

Формат результата описан в `PDFYandexVisionBlock/src/schema.py`. Проверка расширенного JSON находится в `PDFYandexVisionBlock/tools/validate_output.py`.

## Текущий интеграционный риск

Расширенные `parser.py`, `normalizer.py` и `schema.py` уже есть в проекте и покрыты тестами. Перед финальной сборкой нужно убедиться, что `process_pdf(...)` в `PDFYandexVisionBlock/src/__init__.py` использует именно эту расширенную цепочку, если команда хочет получать расширенный формат напрямую из Puzzle RPA entrypoint.
