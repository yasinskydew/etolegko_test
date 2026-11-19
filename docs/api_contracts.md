# API-контракты

Бэкенд — единственный клиент Keitaro. Фронт ходит только сюда. Контракт отдаёт OpenAPI FastAPI; этот файл фиксирует поведение для плана реализации.

Базовый URL — origin бэкенда. CORS только на `CORS_ORIGIN`.

## Общие правила

Авторизация: `Authorization: Bearer <jwt>` на всех методах, кроме `POST /auth/login` и `GET /health`.

Тело ошибки:

```json
{ "error": "name_taken", "message": "This name is already used." }
```

| HTTP | `error` | Когда |
|---|---|---|
| 401 | `unauthorized` | нет или протух JWT |
| 404 | `not_found` | нет компании или поток не её |
| 409 | `version_conflict` | `expected_version` не равен `company.version` |
| 409 | `name_taken` | имя уже есть в базе или в Keitaro |
| 409 | `idempotency_conflict` | тот же `Idempotency-Key`, другое тело |
| 409 | `fetch_blocked` | Fetch при `update mode` |
| 409 | `campaign_missing` | в трекере нет кампании, мутация невозможна |
| 422 | `validation_error` | тело не прошло проверки |
| 422 | `unknown_geo` | код не из `geo`, в том числе пришедший из Keitaro на Fetch |
| 502 | `keitaro_bad_gateway` | трекер ответил ошибкой |
| 504 | `keitaro_timeout` | таймаут трекера |

`validation_error` может добавить `fields`: `{ "name": "Already exists. Pick another name." }`.

Имена офферов в ответах берутся из кэша каталога. Если имени нет, `name` равен `null`, `offer_id` всё равно есть.

## Объекты

### OfferRow

```json
{
  "offer_id": 3749,
  "name": "Miaflow BEAUTY",
  "percent": 60,
  "pinned": true,
  "removed": false,
  "position": 1
}
```

Для `removed = true` UI показывает 0%. В `percent` лежит последнее сохранённое число.

### Stream

```json
{
  "id": 10,
  "type": "offers",
  "position": 2,
  "sync": "synced",
  "offers": []
}
```

`type`: `google` | `offers` | `plain`. `sync`: `synced` | `update_mode` | `null`. У `google` и `plain` список `offers` пустой и `sync` равен `null`. Редирект и фильтр в объект не входят.

### Company

```json
{
  "id": 1,
  "name": "mx_beauty",
  "lifecycle": "ready",
  "version": 7,
  "traffic_status": "active",
  "geo_codes": ["MX", "AU", "RO"],
  "sync": "synced",
  "streams": [],
  "drift": {
    "campaign_missing": false,
    "offers": false,
    "geo": false,
    "traffic": false,
    "streams": false
  },
  "reconcile_unavailable": false
}
```

`sync` — статус потока `offers`. `drift` считается на чтении карточки и не пишется в базу. Серый архив, которого нет в трекере, в `drift.offers` не входит. При `reconcile_unavailable = true` поле `drift` равно `null`.

Карточка компании рисует у потока `offers` только `name`. Редактор использует те же поля целиком.

## `GET /health`

Без JWT. `200`: `{ "status": "ok" }`.

## `POST /auth/login`

```json
{ "username": "admin", "password": "secret" }
```

`200`: `{ "access_token": "<jwt>", "token_type": "bearer" }`.

`401` при неверной паре. Refresh-токена нет.

## `GET /offers?q=`

Каталог Keitaro, только чтение.

`200`:

```json
{ "items": [{ "offer_id": 3749, "name": "Miaflow BEAUTY" }] }
```

`q` необязателен. Создание, изменение и удаление оффера этим API нет.

## `GET /companies`

Список только из своей базы.

Query: `q` (подстрока имени, без учёта регистра), `page` (с 1), `page_size` (по умолчанию 20, максимум 100).

`200`:

```json
{
  "items": [
    {
      "id": 1,
      "name": "mx_beauty",
      "lifecycle": "ready",
      "traffic_status": "active",
      "sync": "synced",
      "version": 7
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

Чужая кампания Keitaro в список не попадает. У `creating` поле `sync` равно `null`.

## `POST /companies`

Заголовок `Idempotency-Key` обязателен.

```json
{ "name": "test_yasinsky_company", "geo_codes": ["MX", "AU", "RO"], "offer_id": 3749 }
```

`percent` в теле нет: единственный оффер получает 100. Имя уходит в Keitaro как есть, без префикса.

Проверки: имя начинается с `test_yasinsky_company`, 1–64, `[a-zA-Z0-9_\- ]`, без крайних пробелов; `geo_codes` не пуст, коды уникальные, формат из двух букв и каждый есть в `geo`; в потоке `offers` хотя бы один `offer_id`, и он есть в каталоге.

`201` — компания создана, тело `Company`, `lifecycle = ready`.

`200` — повтор того же ключа и того же тела, возвращается уже созданная или ещё `creating` компания.

`409 name_taken` — другое имя-дубль или тот же ключ не при чём, имя занято. В `message` можно отличить `ready` и `creating`.

`409 idempotency_conflict` — тот же ключ, другое тело.

До вызова трекера резерв уже содержит `company` (`creating`), `company_geo`, локальные потоки `google` и `offers` и `Idempotency-Key`.

Ошибка трекера после резерва: бэкенд удаляет созданную кампанию и резерв вместе с ключом. Если компенсация не вышла, клиент получает `502` / `504`, строка остаётся `creating`. Фонового reconcile нет.

## `GET /companies/{id}`

`200`: объект `Company`, включая архив и вычисленный `drift`.

Редактор потоков для `lifecycle = creating` не открывается: `409`, `error = validation_error`.

## `GET /companies/{id}/stats`

`200`:

```json
{ "clicks": 1280, "uniques": 940, "bots": 12 }
```

Любое число может быть `null`. На Push и сохранение не влияет. В базу не пишется. Трекер недоступен — `502` / `504`, карточка из `GET /companies/{id}` при этом может открыться отдельно.

## `POST /companies/{id}/streams/{stream_id}/actions`

Только поток `type = offers`. Клиент шлёт действие, не итоговый состав.

```json
{
  "action": "add",
  "offer_id": 3801,
  "percent": 40,
  "expected_version": 7
}
```

`action`: `add` | `remove` | `restore` | `pin` | `unpin` | `set_percent`.

`percent` обязателен только для `set_percent`. Для остальных поле отсутствует.

| Действие | Эффект |
|---|---|
| `add` | новый участник в конец `position`. Если `offer_id` уже в архиве — это `restore` |
| `remove` | `removed = true`, остальные участники пересчитываются |
| `restore` | снимает `removed` и `pinned` у этой строки, затем утилита |
| `pin` | замораживает текущий `percent` |
| `unpin` | возвращает оффер в свободное деление |
| `set_percent` | ставит число 1–100 и `pinned = true` |

Пока остаётся хотя бы один участник, бэкенд заново считает доли и пишет свой результат. Фронтовое превью ответом заменяется. Сумма участников после действия — 100. Последний незакреплённый нельзя закрепить через `set_percent`, если сумма pinned после этого не 100. Незакреплённым должно остаться минимум по 1. Поток без участников допустим, утилита тогда не запускается.

`200`: `Company` с новым `version`. Очередь `localStorage` фронт чистит сам.

`409 version_conflict` — базу не меняет. `422` — действие не принято. Повторный `add` активного оффера — `422`.

## `POST /companies/{id}/sync`

Push участников потока `offers`. Гео и `traffic_status` не отправляет.

Тело пустое. Идемпотентен.

`200`: `Company`. Снимок заменён рабочей копией, архив на месте, `sync = synced`. Если в трекер слать нечего, снимок всё равно дописывается.

Отказ трекера: рабочая копия и `update mode` остаются, снимок не трогается, клиент получает `502` / `504`.

Активный у нас оффер, стёртый в трекере, этим методом в трекер возвращается. Чтобы увести его в архив, нужен Fetch.

## `POST /companies/{id}/cancel`

Тело пустое. Keitaro не вызывается.

`200`: рабочая копия равна снимку, `version` увеличен, `sync = synced`. Добавленные после последнего Push строки исчезают. Архив снимка остаётся.

Фронт сам стирает очередь `localStorage`. Гео и трафик Cancel не откатывает.

## `POST /companies/{id}/fetch`

Тело пустое. Push не вызывает.

Условие записи: компания `ready`, поток `offers` в `synced`. Иначе `409 fetch_blocked`, база не меняется. Непустую очередь браузера бэкенд не видит: фронт не шлёт Fetch, пока очередь не пуста.

`200`: одна транзакция, поток остаётся белым.

- участника нет в трекере — строка `removed`, из базы не удаляется
- оффер есть в трекере и не у нас — участник, `pinned = false`, `percent` из трекера
- серый оффер снова есть в трекере — снова участник, `pinned = false`, `percent` из трекера
- общий оффер — `percent` из трекера; `pinned` остаётся, только если процент не изменился
- сумма не нормализуется
- `geo_codes` берутся из фильтра потока `google`
- `traffic_status` берётся из статуса кампании
- неизвестный `plain` без офферов добавляется; пропавший `plain` удаляется
- неизвестный код гео — `422 unknown_geo`, транзакция целиком откатывается

## `PATCH /companies/{id}/geo`

Keitaro first, только фильтр потока `google`.

```json
{ "geo_codes": ["MX", "RO"], "expected_version": 7 }
```

`200`: `Company`. Имя не меняется. Ошибка трекера — база прежняя, `502` / `504`.

## `POST /companies/{id}/enable` и `POST /companies/{id}/disable`

Тело: `{ "expected_version": 7 }`.

Переключатель на карточке компании вызывает один из этих методов. Доли, потоки, снимок и очередь не меняются. Сначала трекер, потом `traffic_status` и `version`.

Повторный вызов в уже нужном статусе — `200` без записи в трекер.

Ошибка трекера оставляет прежний статус.

## Чего в API нет

| Нет | Почему |
|---|---|
| CRUD оффера | каталог только читается |
| Импорт чужой кампании | в систему попадают только свои компании |
| Состояние `localStorage` | его знает только браузер |
| `GET /config` и префикс имени | имя в форме и в Keitaro одно |
| Push гео или трафика | у них отдельные методы |
