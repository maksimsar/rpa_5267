# TROUBLESHOOTING

## Ошибки блока

| Код | Причина | Что увидит пользователь | Как исправить |
| --- | --- | --- | --- |
| `FILE_NOT_FOUND` | PDF не найден по пути. | `success: false`, код `FILE_NOT_FOUND`. | Проверить `FILE_PATH` и наличие файла. |
| `EMPTY_FILE_PATH` | Путь к PDF не передан. | `success: false`, код `EMPTY_FILE_PATH`. | Передать путь к PDF. |
| `FILE_PATH_IS_NOT_FILE` | Передана папка или не файл. | `success: false`, код `FILE_PATH_IS_NOT_FILE`. | Указать путь к PDF-файлу. |
| `INVALID_FILE_TYPE` | Файл не `.pdf`. | `success: false`, код `INVALID_FILE_TYPE`. | Использовать PDF. |
| `FILE_TOO_LARGE` | PDF больше лимита клиента. | `success: false`, код `FILE_TOO_LARGE`. | Сжать или разделить PDF. |
| `EMPTY_TOKEN` | Не передан токен. | `success: false`, код `EMPTY_TOKEN`. | Передать `TOKEN` как параметр. |
| `EMPTY_FOLDER_ID` | Не передан ID каталога. | `success: false`, код `EMPTY_FOLDER_ID`. | Передать `FOLDER_ID`. |
| `YANDEX_AUTH_ERROR` | Нет доступа или токен неверный. | `success: false`, код `YANDEX_AUTH_ERROR`. | Проверить токен и права. |
| `YANDEX_FOLDER_NOT_FOUND` | Каталог недоступен. | `success: false`, код `YANDEX_FOLDER_NOT_FOUND`. | Проверить `FOLDER_ID` и роли. |
| `YANDEX_QUOTA_ERROR` | Превышена квота. | `success: false`, код `YANDEX_QUOTA_ERROR`. | Проверить лимиты Yandex Cloud. |
| `YANDEX_TIMEOUT` | API не ответил вовремя. | `success: false`, код `YANDEX_TIMEOUT`. | Повторить позже, проверить сеть и размер PDF. |
| `YANDEX_INVALID_JSON` | Ответ API не JSON. | `success: false`, код `YANDEX_INVALID_JSON`. | Проверить ответ API и повторить запрос. |
| `YANDEX_CONNECTION_ERROR` | Нет соединения с Yandex Vision. | `success: false`, код `YANDEX_CONNECTION_ERROR`. | Проверить интернет, proxy/firewall. |
| `YANDEX_REQUEST_ERROR` | Ошибка HTTP-запроса. | `success: false`, код `YANDEX_REQUEST_ERROR`. | Проверить сеть и параметры запроса. |
| `YANDEX_SERVER_ERROR` | Ошибка 5xx на стороне API. | `success: false`, код `YANDEX_SERVER_ERROR`. | Повторить позже. |
| `YANDEX_API_ERROR` | Другая ошибка API. | `success: false`, код `YANDEX_API_ERROR`. | Смотреть `details`. |
| `NETWORK_ERROR` | Сетевая ошибка entrypoint. | `success: false`, код `NETWORK_ERROR`. | Проверить сеть и доступ к API. |
| `FILE_PERMISSION_ERROR` | Нет прав на чтение PDF. | `success: false`, код `FILE_PERMISSION_ERROR`. | Выдать права или переместить файл. |
| `FILE_READ_ERROR` | OS-ошибка чтения файла. | `success: false`, код `FILE_READ_ERROR`. | Проверить диск, блокировку и путь. |
| `MISSING_DEPENDENCY` | Не установлена зависимость. | `success: false`, код `MISSING_DEPENDENCY`. | Установить `requirements.txt`. |

## Блок не появился в Puzzle RPA

1. Проверить, что импортируется папка `PDFYandexVisionBlock/`.
2. Проверить наличие `block.json`, `values.xml`, `meta.json`, `code.value.py`, `typeToName.json`.
3. Перезапустить Puzzle RPA Studio.
4. Проверить категорию `Обработка документов -> OCR`.

## Root tools не запускаются

Запускать из корня проекта:

```powershell
python -X utf8 tools\smoke_test.py
python -X utf8 tools\validate_output.py examples\expected_output.json
```

Если ошибка импорта, проверить, что текущая директория - корень репозитория и папка `PDFYandexVisionBlock/` на месте.

## Старые команды из PDFYandexVisionBlock не запускаются

Запускать их именно из папки `PDFYandexVisionBlock/`:

```powershell
python -B -m unittest discover -s tests
python -X utf8 tools\run_parser_demo.py
python -X utf8 tools\validate_output.py examples\demo_result.json
```

## validate_output не находит файл

Проверить путь:

- root validator: `examples\expected_output.json`;
- старый строгий validator: `examples\demo_result.json` из папки `PDFYandexVisionBlock/`.

## Отсутствует test_input.pdf

Это нормально для репозитория. Реальный PDF добавляется локально перед live demo и не коммитится, если содержит приватные данные.

## Отсутствует TOKEN/FOLDER_ID

Offline-проверки должны работать без секретов. Live OCR требует реальные `TOKEN`, `FOLDER_ID`, `FILE_PATH` и интернет.

## Зависимости не установлены

```powershell
cd PDFYandexVisionBlock
python -m pip install -r requirements.txt
```

Устанавливать зависимости нужно в то Python-окружение, которое использует Puzzle RPA Studio.

## Как не допустить утечки секретов

- Не записывать реальные секреты в README, docs, examples, screenshots и видео.
- Не коммитить `.env`, `secrets.json`, файлы с token/credentials в названии.
- Перед сдачей выполнить:

```powershell
rg -n -i -uu --glob "!.git/**" "y0_|bearer [a-z0-9_\-\.]+|oauth_token|real_token|secret|\.env" .
```

Совпадения с `.gitignore` и документацией допустимы. Реальные секреты недопустимы.
