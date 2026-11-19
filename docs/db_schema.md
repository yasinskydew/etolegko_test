# Схема Postgres

Источник поведения: `task/system-design.md`. Каталог офферов, stats и очередь экрана в базу не пишутся.

Имена таблиц и полей не переводятся. `"user"` в SQL всегда в кавычках: это зарезервированное слово.

## Типы

```sql
CREATE TYPE company_lifecycle AS ENUM ('creating', 'ready');
CREATE TYPE traffic_status AS ENUM ('active', 'disabled');
CREATE TYPE stream_type AS ENUM ('google', 'offers', 'plain');
```

`synced` / `update mode` колонкой не хранятся. Это равенство строк `stream_offer` и `stream_offer_snapshot` потока `offers` по `offer_id`, `percent`, `pinned`, `removed`, `position`.

## `"user"`

| Колонка | Тип | Ограничение |
|---|---|---|
| `id` | `bigint` | PK, identity |
| `username` | `text` | NOT NULL, UNIQUE |
| `password_hash` | `text` | NOT NULL |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |

Строки из seed / env. Саморегистрации нет.

## `geo`

| Колонка | Тип | Ограничение |
|---|---|---|
| `code` | `text` | PK |
| `name` | `text` | NOT NULL |

Seed в миграции Alembic. Стороннего справочника нет.

## `company`

| Колонка | Тип | Ограничение |
|---|---|---|
| `id` | `bigint` | PK, identity |
| `name` | `text` | NOT NULL |
| `keitaro_campaign_id` | `bigint` | NULL, пока кампания в трекере не создана |
| `traffic_status` | `traffic_status` | NOT NULL, default `active` |
| `lifecycle` | `company_lifecycle` | NOT NULL |
| `version` | `integer` | NOT NULL, default `1` |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` |

Имя после создания не меняется. Уникальность регистронезависимая:

```sql
CREATE UNIQUE INDEX company_name_lower_uidx ON company (lower(name));
CREATE UNIQUE INDEX company_keitaro_campaign_uidx
  ON company (keitaro_campaign_id)
  WHERE keitaro_campaign_id IS NOT NULL;
```

`lifecycle = creating` допустим и с уже записанным `keitaro_campaign_id`: это зависшая компенсация. Фонового reconcile нет, редактор для такой строки закрыт.

## `company_geo`

Список кодов компании. Порядок — порядок ввода.

| Колонка | Тип | Ограничение |
|---|---|---|
| `company_id` | `bigint` | PK, FK `company.id` ON DELETE CASCADE |
| `geo_code` | `text` | PK, FK `geo.code` |
| `position` | `integer` | NOT NULL, `>= 1` |

```sql
CREATE UNIQUE INDEX company_geo_position_uidx ON company_geo (company_id, position);
```

Пустой список у `ready`-компании запрещён на уровне сервиса. У `creating` список уже записан вместе с резервом.

## `idempotency_key`

| Колонка | Тип | Ограничение |
|---|---|---|
| `key` | `text` | PK |
| `payload_hash` | `text` | NOT NULL |
| `company_id` | `bigint` | NOT NULL, FK `company.id` |
| `created_at` | `timestamptz` | NOT NULL, default `now()` |

Один ключ хранит один hash тела `POST /companies`. Другой payload с тем же ключом — конфликт, строка не перезаписывается.

## `stream`

| Колонка | Тип | Ограничение |
|---|---|---|
| `id` | `bigint` | PK, identity |
| `company_id` | `bigint` | NOT NULL, FK `company.id` ON DELETE CASCADE |
| `type` | `stream_type` | NOT NULL |
| `keitaro_stream_id` | `bigint` | NULL только до ответа трекера |
| `position` | `integer` | NOT NULL, `>= 1` |

```sql
CREATE UNIQUE INDEX stream_keitaro_uidx
  ON stream (keitaro_stream_id)
  WHERE keitaro_stream_id IS NOT NULL;
CREATE UNIQUE INDEX stream_one_google_uidx
  ON stream (company_id) WHERE type = 'google';
CREATE UNIQUE INDEX stream_one_offers_uidx
  ON stream (company_id) WHERE type = 'offers';
CREATE UNIQUE INDEX stream_position_uidx ON stream (company_id, position);
```

Свои потоки: `google` на позиции 1, `offers` на позиции 2. `plain` — дополнительные потоки без офферов из Keitaro, позиций может быть больше. Поток без компании не существует.

`google` и `plain` не имеют строк в `stream_offer`. URL и фильтр `google` в Postgres не хранятся: фильтр стран выводится из `company_geo`, URL берётся из `GOOGLE_URL`.

## `stream_offer`

Рабочая копия только потока `offers`.

| Колонка | Тип | Ограничение |
|---|---|---|
| `id` | `bigint` | PK, identity |
| `stream_id` | `bigint` | NOT NULL, FK `stream.id` ON DELETE CASCADE |
| `offer_id` | `bigint` | NOT NULL, id оффера в Keitaro |
| `percent` | `smallint` | NOT NULL, `0..100` |
| `pinned` | `boolean` | NOT NULL, default `false` |
| `removed` | `boolean` | NOT NULL, default `false` |
| `position` | `integer` | NOT NULL, `>= 1` |

```sql
CREATE UNIQUE INDEX stream_offer_uidx ON stream_offer (stream_id, offer_id);
CREATE UNIQUE INDEX stream_offer_position_uidx ON stream_offer (stream_id, position);
```

`offer_id` не ссылается на локальную таблицу: каталог в базу не пишется.

Участник: `removed = false` и `percent` от 1 до 100. У архива `removed = true`; в UI доля 0%, в колонке остаётся последний `percent`. Редактор не пишет 0. Fetch может записать доли трекера как есть, в том числе если сумма участников не 100.

Сервис пишет строки только если `stream.type = 'offers'`.

## `stream_offer_snapshot`

Тот же состав, что рабочая копия, после последнего успешного Push, Fetch или создания.

| Колонка | Тип | Ограничение |
|---|---|---|
| `id` | `bigint` | PK, identity |
| `stream_id` | `bigint` | NOT NULL, FK `stream.id` ON DELETE CASCADE |
| `offer_id` | `bigint` | NOT NULL |
| `percent` | `smallint` | NOT NULL, `0..100` |
| `pinned` | `boolean` | NOT NULL |
| `removed` | `boolean` | NOT NULL |
| `position` | `integer` | NOT NULL, `>= 1` |

```sql
CREATE UNIQUE INDEX stream_offer_snapshot_uidx
  ON stream_offer_snapshot (stream_id, offer_id);
CREATE UNIQUE INDEX stream_offer_snapshot_position_uidx
  ON stream_offer_snapshot (stream_id, position);
```

Push и Fetch заменяют снимок всей рабочей копией, включая архив. Cancel снимок не меняет: он копируется обратно в `stream_offer`. Строки `removed` при Push не удаляются.

## Что не является таблицей

| Данные | Где |
|---|---|
| Каталог офферов, имена, поиск | Keitaro, кэш процесса |
| clicks, uniques, bots | Keitaro, на чтении |
| Очередь `add` / `remove` / `restore` / `pin` / `unpin` / `set_percent` | `localStorage`, ключ `company:{id}:tab:{tabId}` |
| id домена, группы, источника | кэш процесса после резолва env при старте |

## Запись

Мутация компании и её потоков берёт `SELECT … FOR UPDATE` по `company` и сверяет `version`. Чужая версия — отказ, строка не меняется. Успешная мутация увеличивает `version`.
