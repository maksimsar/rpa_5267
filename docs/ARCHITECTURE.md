# Архитектура PDFYandexVisionBlock

`PDFYandexVisionBlock` построен как расширение Puzzle RPA Studio с отдельным Python-слоем для OCR, парсинга и нормализации результата.

## Общая схема

```text
Puzzle RPA Studio
  → block.json / values.xml
  → code.value.py
  → src.process_pdf(...)
  → src/yandex_client.py
  → Yandex Vision / OCR API
  → src/parser.py
  → src/normalizer.py
  → dict или JSON
```

## Слои решения

### 1. Puzzle RPA слой

Файлы:

```text
PDFYandexVisionBlock/block.json
PDFYandexVisionBlock/meta.json
PDFYandexVisionBlock/values.xml
PDFYandexVisionBlock/code.value.py
PDFYandexVisionBlock/libs.py.json
PDFYandexVisionBlock/typeToName.json
```

Назначение слоя:

- описывает визуальный блок;
- задаёт входные параметры;
- размещает блок в категории **Обработка документов → OCR**;
- связывает визуальный блок с Python-функцией `process_pdf`.

### 2. Entry point

Файл:

```text
PDFYandexVisionBlock/src/__init__.py
```

Основная функция:

```python
process_pdf(token, folder_id, file_path, language="ru", output_format="dict", ...)
```

Она отвечает за валидацию входных параметров, вызов OCR-клиента, запуск парсера и возврат результата в выбранном формате.

### 3. OCR client

Файл:

```text
PDFYandexVisionBlock/src/yandex_client.py
```

Задачи:

- проверить PDF-файл;
- прочитать файл и закодировать его в base64;
- подготовить HTTP-запрос к Yandex Vision / OCR API;
- обработать авторизацию через OAuth/IAM;
- дождаться результата распознавания;
- вернуть OCR-ответ или структурированную ошибку.

### 4. Parser

Файл:

```text
PDFYandexVisionBlock/src/parser.py
```

Парсер извлекает из OCR-ответа:

- тип документа;
- номер;
- дату;
- сумму;
- ИНН и КПП;
- контрагентов;
- строки табличной части.

Парсер рассчитан на документы с разным качеством распознавания, поэтому использует несколько стратегий: поиск по ключевым словам, регулярные выражения, анализ строк и обработку табличных данных.

### 5. Normalizer

Файл:

```text
PDFYandexVisionBlock/src/normalizer.py
```

Нормализатор приводит значения к единому виду:

- даты — к стандартному формату;
- суммы — к числам;
- ИНН и КПП — к очищенным строкам;
- текст — к устойчивому виду после OCR;
- единицы измерения — к коротким понятным обозначениям.

### 6. Error handling

Файл:

```text
PDFYandexVisionBlock/src/errors.py
```

Все типовые ошибки приводятся к формату:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Описание ошибки",
    "details": {}
  }
}
```

Это важно для RPA: робот может продолжить выполнение по альтернативной ветке, а не завершиться с traceback.

## Формат результата

Результат успешной обработки содержит основные разделы:

```text
success
├── document
├── counterparties
├── items
├── raw_text
├── warnings
└── meta
```

`document` хранит общие реквизиты документа, `counterparties` — участников, `items` — табличные позиции, `warnings` — предупреждения о неполном извлечении.

## Точки расширения

| Что нужно изменить | Где менять |
|---|---|
| Внешний вид блока | `block.json`, `values.xml` |
| Вызов Python-функции из Puzzle RPA | `code.value.py` |
| Интеграцию с Yandex API | `src/yandex_client.py` |
| Логику поиска реквизитов | `src/parser.py` |
| Очистку и нормализацию значений | `src/normalizer.py` |
| Формат ошибок | `src/errors.py` |
| Проверочные сценарии | `tools/` и `examples/` |

## Принцип проектирования

Решение разделено так, чтобы изменение одного слоя не требовало переписывать остальные. Например, можно доработать парсер или заменить способ вызова Yandex API, не меняя визуальный блок в Puzzle RPA Studio.
