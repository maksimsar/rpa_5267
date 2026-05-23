# ARCHITECTURE

PDFYandexVisionBlock разделен на Puzzle RPA extension, Python-логику блока, root-level слой сдачи и документацию.

## Поток данных

```text
Puzzle RPA block
→ PDFYandexVisionBlock/code.value.py
→ PDFYandexVisionBlock/src/process_pdf(...)
→ yandex_client.call_yandex_vision(...)
→ Yandex Vision API
→ parser.py
→ normalizer.py
→ schema.py
→ dict/json result
```

Текущий интеграционный риск: расширенные `parser.py`, `normalizer.py` и `schema.py` уже есть и покрыты проверками, но `process_pdf(...)` в `PDFYandexVisionBlock/src/__init__.py` сейчас после OCR использует базовую встроенную структуризацию из `src/__init__.py`. Перед live Puzzle RPA demo нужно подтвердить, какой формат результата должен возвращать entrypoint.

## Слои

### Puzzle RPA слой

Файлы:

- `PDFYandexVisionBlock/block.json`
- `PDFYandexVisionBlock/values.xml`
- `PDFYandexVisionBlock/code.value.py`
- `PDFYandexVisionBlock/meta.json`
- `PDFYandexVisionBlock/typeToName.json`
- `PDFYandexVisionBlock/libs.py.json`

Слой отвечает за описание визуального блока, категорию `Обработка документов -> OCR`, входные параметры `TOKEN`, `FOLDER_ID`, `FILE_PATH`, `LANGUAGE`, `OUTPUT_FORMAT` и вызов `process_pdf(...)`.

### API слой

Файл: `PDFYandexVisionBlock/src/yandex_client.py`.

Задачи: проверить PDF, собрать payload, вызвать Yandex Vision, обработать HTTP-ошибки, timeout и некорректный JSON.

### Error handling слой

Файл: `PDFYandexVisionBlock/src/errors.py`.

Слой задает единый формат `success: false` с `error.code`, `error.message`, `error.details`.

### Parser слой

Файл: `PDFYandexVisionBlock/src/parser.py`.

Извлекает тип документа, номер, дату, сумму, контрагентов, ИНН/КПП и табличные позиции из текста или OCR-ответа.

### Normalizer слой

Файл: `PDFYandexVisionBlock/src/normalizer.py`.

Нормализует даты, суммы, ИНН, КПП, названия организаций, единицы измерения и типовые OCR-артефакты.

### Schema/result слой

Файл: `PDFYandexVisionBlock/src/schema.py`.

Описывает расширенный результат с `value`, `confidence` и `source`, чтобы результат был понятен на защите и проверяем в тестах.

### Examples слой

Root `examples/` предназначен для жюри и упаковки:

- `examples/sample_response_yandex.json` - пример ответа OCR;
- `examples/expected_output.json` - ожидаемый JSON для root validator;
- `examples/README_TEST_INPUT.md` - почему реальный `test_input.pdf` не хранится в репозитории.

Старые dev-примеры сохранены в `PDFYandexVisionBlock/examples/`.

### Tools/checking слой

Root `tools/` предназначен для быстрой проверки сдачи:

- `tools/smoke_test.py`
- `tools/validate_output.py`

Старые dev-tools сохранены в `PDFYandexVisionBlock/tools/` для обратной совместимости.

### Docs/demo слой

`docs/`, `README.md`, `CHECKPOINTS.md` и `demo_video_link.txt` описывают установку, демонстрацию, troubleshooting и чек-лист защиты.

## Почему root-level tools/examples удобны для жюри

- Проверки запускаются из корня проекта без знания внутренней структуры блока.
- `examples/expected_output.json` дает готовый результат для просмотра.
- `tools/smoke_test.py` не требует секретов и сети.
- Внутренняя Puzzle RPA папка остается чистым extension-пакетом.

## Точки расширения

- OCR-провайдера менять в API-слое или через адаптер рядом с `yandex_client.py`.
- Парсер улучшать в `parser.py`, нормализацию - в `normalizer.py`.
- Формат результата менять в `schema.py` и валидаторах.
- Puzzle RPA UI менять в `block.json`, `values.xml` и связанных meta-файлах.
