# etolegko_test

Админка компаний и потоков офферов. Фронт ходит только в API бэкенда; кампании и потоки синхронизируются с Keitaro.

## Запуск

Скопируйте окружение и поднимите стек:

```bash
cp .env.example .env
docker compose up -d --build
```

Обязательно добавьте в `.env` ключ `KEITARO_API_KEY`. Без него синхронизация с Keitaro не работает. Также укажите `KEITARO_URL` и смените `JWT_SECRET` и `ADMIN_PASSWORD`. `CORS_ORIGIN` должен совпадать с origin фронта (`http://localhost:3000`).

- Postgres: `localhost:5432`
- Backend: http://localhost:8000/health
- Документация API: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Вход: `ADMIN_USERNAME` / `ADMIN_PASSWORD` из `.env`
