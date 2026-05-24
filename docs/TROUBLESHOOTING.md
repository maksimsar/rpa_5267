# Troubleshooting

Этот документ помогает быстро понять причину ошибки при запуске блока или проверочных скриптов.

## Ошибки входных параметров

| Код | Причина | Как исправить |
|---|---|---|
| `EMPTY_TOKEN` | Не передан токен Yandex Cloud. | Передать `TOKEN` в параметрах блока. |
| `EMPTY_FOLDER_ID` | Не передан Folder ID. | Передать корректный `FOLDER_ID`. |
| `EMPTY_FILE_PATH` | Не передан путь к PDF. | Указать путь в `FILE_PATH`. |
| `FILE_NOT_FOUND` | Файл не найден по указанному пути. | Проверить путь и наличие файла. |
| `FILE_PATH_IS_NOT_FILE` | Передан путь к папке, а не к файлу. | Указать конкретный PDF-файл. |
| `INVALID_FILE_TYPE` | Файл не имеет расширения `.pdf`. | Использовать PDF-документ. |
| `FILE_TOO_LARGE` | PDF превышает допустимый размер клиента. | Сжать PDF или разделить документ. |

## Ошибки зависимостей

| Код | Причина | Как исправить |
|---|---|---|
| `MISSING_DEPENDENCY` | Не установлена библиотека `requests` или другие зависимости. | Выполнить установку из `requirements.txt`. |

Команда:

```powershell
cd PDFYandexVisionBlock
python -m pip install -r requirements.txt
```

## Ошибки Yandex Cloud

| Код | Причина | Как исправить |
|---|---|---|
| `YANDEX_AUTH_ERROR` | Неверный токен или нет доступа к каталогу. | Проверить токен, Folder ID и права доступа. |
| `YANDEX_FOLDER_NOT_FOUND` | Каталог не найден или недоступен. | Проверить `FOLDER_ID`. |
| `YANDEX_QUOTA_ERROR` | Превышена квота OCR. | Проверить лимиты в Yandex Cloud или повторить позже. |
| `YANDEX_IAM_TOKEN_ERROR` | Не удалось получить IAM-токен по OAuth. | Проверить OAuth-токен. |
| `YANDEX_IAM_TOKEN_MISSING` | IAM API не вернул токен. | Повторить запрос и проверить ответ Yandex. |
| `YANDEX_SERVER_ERROR` | Ошибка на стороне Yandex API. | Повторить позже. |
| `YANDEX_TIMEOUT` | API не ответил вовремя. | Проверить сеть, размер PDF и повторить запуск. |
| `YANDEX_CONNECTION_ERROR` | Нет соединения с Yandex API. | Проверить интернет, proxy или firewall. |
| `YANDEX_INVALID_JSON` | API вернул некорректный JSON. | Посмотреть `details`, повторить запрос. |

## Блок не появился в Puzzle RPA Studio

Проверьте, что импортируется именно папка:

```text
PDFYandexVisionBlock/
```

Внутри должны быть файлы:

```text
block.json
meta.json
values.xml
code.value.py
libs.py.json
typeToName.json
requirements.txt
src/__init__.py
```

После добавления расширения перезапустите Puzzle RPA Studio и проверьте категорию:

```text
Обработка документов → OCR
```

## Offline-проверка не запускается

Запускайте команды из корня проекта:

```powershell
python -X utf8 tools\smoke_test.py
python -X utf8 tools\validate_output.py examples\expected_output.json
```

Если возникает ошибка импорта, убедитесь, что рядом находится папка `PDFYandexVisionBlock/`.

## Live OCR не работает

Проверьте четыре условия:

1. Есть интернет.
2. `TOKEN` действителен.
3. `FOLDER_ID` принадлежит нужному каталогу.
4. `FILE_PATH` указывает на существующий PDF.

Для демонстрации без live OCR используйте примеры из `examples/` и проверочные скрипты из `tools/`.

## Как не раскрыть секреты

Не храните реальные токены в:

- README;
- документации;
- примерах;
- скриншотах;
- видео;
- `.env` внутри архива сдачи.

Перед отправкой архива проверьте проект на секреты и мусорные файлы.
