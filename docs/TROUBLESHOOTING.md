# TROUBLESHOOTING

Документ описывает типовые ошибки PDFYandexVisionBlock и действия перед защитой.

## Таблица ошибок

| Код | Причина | Что увидит пользователь | Как исправить |
| --- | --- | --- | --- |
| `FILE_NOT_FOUND` | PDF-файл не найден по указанному пути. | `success: false`, код `FILE_NOT_FOUND`, в `details` путь к файлу. | Проверить `FILE_PATH`, права доступа и наличие файла на машине робота. |
| `EMPTY_FILE_PATH` | Параметр `FILE_PATH` пустой. | `success: false`, код `EMPTY_FILE_PATH`. | Передать путь к PDF-файлу в блок. |
| `FILE_PATH_IS_NOT_FILE` | В `FILE_PATH` передана папка или не файл. | `success: false`, код `FILE_PATH_IS_NOT_FILE`. | Указать путь именно к PDF-файлу. |
| `INVALID_FILE_TYPE` | Файл не имеет расширение `.pdf`. | `success: false`, код `INVALID_FILE_TYPE`. | Выбрать PDF или предварительно конвертировать документ в PDF. |
| `FILE_TOO_LARGE` | PDF больше локального лимита клиента. | `success: false`, код `FILE_TOO_LARGE`, размер в `details`. | Сжать PDF, разделить документ или изменить лимит после согласования с командой. |
| `EMPTY_TOKEN` | Не передан токен доступа. | `success: false`, код `EMPTY_TOKEN`. | Передать `TOKEN` через параметры блока или безопасное окружение. |
| `EMPTY_FOLDER_ID` | Не передан ID каталога Yandex Cloud. | `success: false`, код `EMPTY_FOLDER_ID`. | Передать корректный `FOLDER_ID`. |
| `YANDEX_AUTH_ERROR` | Токен неверный, истек или нет прав на каталог. | `success: false`, код `YANDEX_AUTH_ERROR`, детали ответа API. | Обновить токен, проверить права аккаунта и доступ к Yandex Vision. |
| `YANDEX_FOLDER_NOT_FOUND` | Каталог не найден или недоступен. | `success: false`, код `YANDEX_FOLDER_NOT_FOUND`. | Проверить `FOLDER_ID` и права пользователя в Yandex Cloud. |
| `YANDEX_QUOTA_ERROR` | Превышена квота Yandex Vision. | `success: false`, код `YANDEX_QUOTA_ERROR`. | Подождать сброса квоты, уменьшить число запросов или проверить лимиты облака. |
| `YANDEX_TIMEOUT` | Yandex Vision не ответил за timeout. | `success: false`, код `YANDEX_TIMEOUT`. | Повторить позже, проверить сеть, уменьшить размер PDF или увеличить timeout в согласованной сборке. |
| `YANDEX_INVALID_JSON` | API вернул ответ, который не удалось прочитать как JSON. | `success: false`, код `YANDEX_INVALID_JSON`, фрагмент ответа в `details`. | Повторить запрос, проверить статус сервиса и корректность API-вызова. |
| `YANDEX_CONNECTION_ERROR` | Нет соединения с Yandex Vision или интернетом. | `success: false`, код `YANDEX_CONNECTION_ERROR`. | Проверить интернет, proxy/firewall и доступ к доменам Yandex Cloud. |
| `YANDEX_REQUEST_ERROR` | Ошибка HTTP-запроса к Yandex Vision. | `success: false`, код `YANDEX_REQUEST_ERROR`. | Проверить сеть, параметры запроса и зависимости `requests`. |
| `YANDEX_SERVER_ERROR` | Ошибка 5xx на стороне Yandex Vision. | `success: false`, код `YANDEX_SERVER_ERROR`. | Повторить позже или проверить статус Yandex Cloud. |
| `YANDEX_API_ERROR` | Другая HTTP-ошибка Yandex Vision. | `success: false`, код `YANDEX_API_ERROR`, HTTP-детали. | Посмотреть `details`, проверить параметры запроса и доступы. |
| `NETWORK_ERROR` | Сетевая ошибка на уровне Puzzle RPA entrypoint. | `success: false`, код `NETWORK_ERROR`. | Проверить сеть, proxy, DNS и доступность Yandex Vision. |
| `FILE_PERMISSION_ERROR` | Нет прав на чтение PDF. | `success: false`, код `FILE_PERMISSION_ERROR`. | Переместить файл в доступную папку или выдать права процессу робота. |
| `FILE_READ_ERROR` | Файл не удалось прочитать из-за OS-ошибки. | `success: false`, код `FILE_READ_ERROR`. | Проверить блокировку файла, диск и корректность пути. |
| `MISSING_DEPENDENCY` | Не установлена нужная Python-зависимость. | `success: false`, код `MISSING_DEPENDENCY`. | Установить зависимости из `PDFYandexVisionBlock/requirements.txt`. |

## Если блок не появился в Puzzle RPA

1. Проверить, что импортируется папка `PDFYandexVisionBlock/`, а не вложенная папка неправильного уровня.
2. Проверить наличие `block.json`, `values.xml`, `meta.json`, `code.value.py`, `typeToName.json`.
3. Перезапустить Puzzle RPA Studio или обновить список пользовательских блоков.
4. Проверить категорию `Обработка документов -> OCR`.
5. Убедиться, что файлы сохранены в UTF-8 и JSON/XML не повреждены.

## Если не установились зависимости

Запускать установку из окружения Python, которое использует Puzzle RPA:

```powershell
cd PDFYandexVisionBlock
python -m pip install -r requirements.txt
```

Если `requests` не найден, блок может вернуть `MISSING_DEPENDENCY`. Если установка запрещена политиками системы, установить зависимости в согласованное окружение Puzzle RPA Studio.

## Если нет доступа к Yandex Vision

1. Проверить, что токен актуален.
2. Проверить, что `FOLDER_ID` относится к нужному каталогу.
3. Проверить роли пользователя или сервисного аккаунта в Yandex Cloud.
4. Проверить квоты и включенность сервиса Yandex Vision.
5. Проверить сетевой доступ с машины, где запускается робот.

## Как проверить демо локально

Локальное demo не требует токена и не обращается в сеть:

```powershell
cd PDFYandexVisionBlock
python tools\run_parser_demo.py
python -X utf8 tools\validate_output.py examples\demo_result.json
```

Unit-тесты:

```powershell
cd PDFYandexVisionBlock
python -B -m unittest discover -s tests
```

## Как не допустить утечки токенов

- Не записывать реальные токены в README, docs, examples и screenshots.
- Не коммитить `.env`, `secrets.json`, файлы с token/credentials в названии.
- Перед сдачей выполнить поиск по проекту:

```powershell
rg -n -i -uu --glob "!.git/**" "y0_|bearer|oauth|folder_id|folderid|token|secret|\.env" .
```

Совпадения в документации и именах параметров допустимы. Реальные значения токенов, ключей и секретов недопустимы.
