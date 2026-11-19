# etolegko_test

## Запуск

```bash
cp .env.example .env
docker compose up -d --build
```

- Postgres: `:5432`
- Backend: `http://localhost:8000/health`
- Frontend: `http://localhost:3000`

Локально без Docker для фронта:

```bash
cd fe && cp .env.example .env.local && npm install && npm run dev
```

`CORS_ORIGIN` в `.env` должен указывать на origin фронта (`http://localhost:3000`).
