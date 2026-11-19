# Прогресс реализации

Журнал по фазам из [implementation-plan.md](implementation-plan.md). После каждой фазы: статус, что сделано, комментарии.

| Фаза | Статус | Дата |
|------|--------|------|
| 1. Postgres | done | 2026-11-19 |
| 2. Заглушка backend | done | 2026-11-19 |
| 3. Доступ к базе | done | 2026-11-19 |
| 4. Alembic | done | 2026-11-19 |
| 5. Миграция | done | 2026-11-19 |
| 6. JWT | done | 2026-11-19 |
| 7. Домен | done | 2026-11-19 |
| 8. Пустой frontend | done | 2026-11-19 |
| 9. RTK Query | done | 2026-11-19 |
| 10. Базовые компоненты | done | 2026-11-19 |
| 11. Страницы | done | 2026-11-19 |
| 12. Тестирование | pending | — |

---

## Фаза 1. Postgres

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- `docker-compose.yml` — только Postgres 16, healthcheck (`pg_isready`), volume `postgres_data`, порт `5432`
- `.env.example` — переменные из system-design (Keitaro, `DATABASE_URL`, JWT, admin, CORS, `POSTGRES_*`); без `NAME_PREFIX`
- `README.md` — `cp .env.example .env` → `docker compose up -d`
- `.gitignore` — `.env` и типовой мусор
- Локально: контейнер `healthy`, `pg_isready` ok
- MCP Postgres: `@microsoft/postgres-mcp`, профиль `etolegko-local` (`app@localhost:5432/etolegko`)

### Комментарии

- Backend/frontend в compose намеренно не добавлялись (фаза 2 / 8)
- Credentials в compose берутся из `.env`; плейсхолдеры `changeme`
- MCP: пароль в Keychain, не в `mcp.json`

---

## Фаза 2. Заглушка backend

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- `backend/app/main.py` — FastAPI, CORS из `CORS_ORIGIN`, `GET /health` → `{"status":"ok"}`
- `backend/requirements.txt` — fastapi, uvicorn
- `backend/Dockerfile` — Python 3.12, uvicorn на `:8000`
- `docker-compose.yml` — сервис `backend`, `depends_on` Postgres (`service_healthy`)
- Проверка: `curl http://localhost:8000/health` → `{"status":"ok"}`

### Комментарии

- Доменной логики нет; JWT на `/health` не требуется
- CORS уже на middleware — пригодится фронту (фаза 8)

---

## Фаза 3. Доступ к базе

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- `sqlalchemy[asyncio]`, `asyncpg` в `requirements.txt`
- `backend/app/db/base.py` — `Base(DeclarativeBase)`
- `backend/app/db/session.py` — async engine, `async_sessionmaker`, `get_session` для Depends
- `backend/app/repositories/base.py` — пустой `Repository` Protocol
- `main.py` — lifespan с `engine.dispose()`
- Rebuild backend: `GET /health` ok, импорты с `DATABASE_URL` ok

### Комментарии

- Моделей таблиц и конкретных репозиториев нет — это фаза 5
- `DATABASE_URL` обязателен при старте приложения (из `.env`)

---

## Фаза 4. Alembic

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- `alembic` в `requirements.txt`
- `backend/alembic.ini`, `backend/alembic/env.py` — async, `Base.metadata` + `DATABASE_URL`
- `backend/alembic/versions/` — пусто (без ревизий)
- `alembic upgrade head` → exit 0 на пустой базе

### Комментарии

- Ревизии схемы — фаза 5
- `env.py` через `async_engine_from_config` + `run_sync`

---

## Фаза 5. Миграция

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- SQLAlchemy модели: `User` (`"user"`), `Geo`, `Company`, `CompanyGeo`, `IdempotencyKey`, `Stream`, `StreamOffer`, `StreamOfferSnapshot` + enums
- Alembic ревизия `20261119185515_initial_schema`: enums, таблицы, частичные UNIQUE индексы
- Seed: 50 geo (MX,AU,RO,US,GB,…); admin из `ADMIN_USERNAME`/`ADMIN_PASSWORD` (bcrypt)
- CRUD-репозитории через конструктор DI
- Dockerfile: `alembic/` + `alembic.ini`, `entrypoint.sh` → `alembic upgrade head` затем uvicorn
- compose: `DATABASE_URL` override на host `postgres`

### Комментарии

- Локально `alembic upgrade head` на `localhost` Postgres — ok
- Enum create_type=False, чтобы не дублировать CREATE TYPE

---

## Фаза 6. JWT

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- `POST /auth/login` → `{access_token, token_type}`; пароль только bcrypt-hash
- Bearer JWT на всех маршрутах кроме login и `/health`
- 401 `{error:"unauthorized", message}` при неверной паре / без токена
- PyJWT + bcrypt

### Комментарии

- Logout сервером не хранится

---

## Фаза 7. Домен

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- 7.1 `WeightUtil` + pytest (11 tests): хвост 34/33/33, pin, restore снимает pin, пустой поток, запрет set_percent последнего свободного
- 7.2 `KeitaroClient` (Protocol/ABC, httpx): таймауты; ретраи на чтение и повторный Push; resolve domain/group/source при старте
- 7.3–7.6 Companies CRUD/actions/Push/Cancel/Fetch/geo/enable/disable/stats/`GET /offers`/drift
- Optimistic lock `version` + `SELECT … FOR UPDATE`; ошибки `{error, message}`

### Комментарии

- **Keitaro noop mode:** если `KEITARO_URL` пуст — `NoopKeitaroClient`, resolve не падает (для локальной разработки без credentials). При непустом URL отсутствие domain/group/source → падение на старте (как в system-design).
- Реальный Keitaro не проверялся (URL/ключ пустые в `.env`).
- Фоновый reconcile `creating` не реализован (не требовался явно в 7.x).

---

## Фаза 8. Пустой frontend

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- `fe/` — Next.js 15 App Router, TypeScript, client render
- `ChakraProvider` + `ColorModeScript` (светлая тема по умолчанию через next-themes)
- Минимальная homepage-shell; API-страниц нет
- `fe/Dockerfile` (standalone), сервис `frontend` в `docker-compose.yml` на `:3000`
- `CORS_ORIGIN` / `NEXT_PUBLIC_API_URL` в `.env.example`
- Зависимости: next, react, `@chakra-ui/react` v3, `@reduxjs/toolkit`, `react-redux`

### Комментарии

- Без `NAME_PREFIX` / `GET /config`
- Backend не менялся

---

## Фаза 9. RTK Query

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- Один API slice `fe/src/store/api.ts` → `NEXT_PUBLIC_API_URL`
- JWT в `localStorage` (`etolegko:jwt`), отдельно от очереди
- Очередь `company:{id}:tab:{tabId}` в `fe/src/lib/actionQueue.ts` — вне RTK
- Теги: `companies`, `company`, `offers`, `stats`; инвалидация после мутаций

### Комментарии

- `tabId` в `sessionStorage`, чтобы вкладки не пересекались

---

## Фаза 10. Базовые компоненты

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- Тема `fe/src/theme/index.ts`: семантические токены `bg.subtle` / `bg` / `gray.fg` / blue / cyan
- `AppShell` (sidebar Companies/Offers; streams только из карточки), Drawer на `base`, `md` 200px, `lg` 240px
- `TrafficToggle`, `CreateCompanyModal`, `OfferCombobox`, `DriftAlert`, `StatusBadge`, `PagePagination`

### Комментарии

- Свои hex/CSS не писались; UI на Chakra v3

---

## Фаза 11. Страницы

**Статус:** done  
**Дата:** 2026-11-19

### Результат

- `/login` — бренд + форма
- `/companies` — search, pagination, Enable/Disable
- Create company modal + ошибка имени (`name_taken`)
- `/companies/[id]` — traffic toggle, имена офферов, View details, drift alert без Fetch, geo patch
- `/offers` — read-only каталог
- `/companies/[id]/streams` — shares, pin/unpin, Remove, Bring back, Add, Push, Cancel, Fetch
- localStorage queue; Fetch disabled при `update_mode` или непустой очереди
- Доли берутся из ответа API (без клиентского WeightUtil как истины)
- Клиентский запрет pin/`set_percent` последнего свободного до запроса

### Комментарии

- Push/Fetch/Cancel только в редакторе; traffic на карточке (+ Enable/Disable в списке по фазе 11)
- Нет `GET /geo` в API — гео как comma-separated поле
- UI English; состав экранов по Figma, не пиксель-пёрфект
- Колонки Stats/Trends из макета редактора не подключены (нет данных в actions API)

---

## Фаза 12. Тестирование

**Статус:** pending

### Результат

—

### Комментарии

—
