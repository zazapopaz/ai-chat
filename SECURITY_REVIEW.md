# Security & Quality Review

Date: 2026-03-13
Scope: `backend/`, `frontend/`, `docker-compose.yml`

## Executive summary

Обнаружены несколько важных проблем в безопасности и эксплуатации:

- **High**: риск кражи JWT через XSS из-за хранения токенов в `localStorage`.
- **High**: небезопасные CORS-паттерны (wildcard + credentials, отражение Origin в widget OPTIONS).
- **Medium**: перечисление пользователей (user enumeration) в auth-flow по различным кодам/текстам ошибок.
- **Medium**: отсутствие явной проверки admin-claim при доступе в админ API.
- **Medium**: утечка чувствительных данных в browser console (логируется пароль на клиенте).
- **Medium**: небезопасный DSN в compose (`user:password` в `DATABASE_URL`).

---

## Findings

### 1) JWT хранится в `localStorage` (High)

**Почему это проблема:** при любой XSS на фронтенде злоумышленник может прочитать `localStorage` и украсть access token.

**Подтверждение:**
- User token читается/пишется в `localStorage` (`token`).
- Admin token и admin profile также пишутся в `localStorage`.

**Рекомендация:**
- Перейти на `HttpOnly + Secure + SameSite` cookies для access/refresh токенов.
- Минимизировать lifetime access token (например 10–15 минут) и использовать refresh rotation.

### 2) CORS конфигурация слишком широкая (High)

**Почему это проблема:**
- В debug-режиме добавляется `"*"`, одновременно включены `allow_credentials=True`.
- Для widget OPTIONS используется отражение `Origin` из входящего запроса без whitelist-проверки.

**Рекомендация:**
- Никогда не использовать `*` вместе с credentialed requests.
- Везде использовать строгий whitelist доменов.
- Для widget preflight возвращать `Access-Control-Allow-Origin` только для валидированных Origin.

### 3) User enumeration в auth endpoints (Medium)

**Почему это проблема:** различимые ответы (`Пользователь не найден`, `Email уже подтвержден`, `Пользователь с таким email уже существует`) позволяют перебирать существующие аккаунты.

**Рекомендация:**
- Возвращать унифицированный ответ на публичных auth endpoints.
- Детальные причины логировать только на сервере.

### 4) Валидация админ-доступа без проверки claim `is_admin` (Medium)

**Почему это проблема:** в `get_current_admin` проверяется только `sub`, но не тип/claim токена. При компрометации секрета это упрощает злоупотребление токенами разных типов.

**Рекомендация:**
- Проверять `type == "access"` и `is_admin == True` для админ endpoints.
- Разделить секреты/issuer/audience для user/admin токенов.

### 5) Логирование пароля в browser console (Medium)

**Почему это проблема:** пароль пользователя напрямую выводится в консоль браузера и может попасть в журналы/скриншоты/поддержку.

**Рекомендация:**
- Удалить все console.log с credential-полями.
- Добавить линтер-правило/проверку на запрет логирования секретов.

### 6) Hardcoded password в `DATABASE_URL` в compose (Medium)

**Почему это проблема:** в `DATABASE_URL` зашит `user:password`, что провоцирует небезопасные деплои и рассинхрон с `POSTGRES_PASSWORD=${DB_PASSWORD}`.

**Рекомендация:**
- Полностью собрать DSN из env-переменных (`${DB_USER}`, `${DB_PASSWORD}`, `${DB_HOST}`, `${DB_NAME}`).
- Добавить preflight-check при запуске (падать, если секреты дефолтные/пустые).

---

## Priority plan

1. **Срочно (P1):** убрать токены из `localStorage`, перевести auth на HttpOnly cookies.
2. **Срочно (P1):** привести CORS/widget preflight к строгому whitelist.
3. **Ближайший релиз (P2):** убрать user enumeration и унифицировать ответы auth.
4. **Ближайший релиз (P2):** ужесточить проверку admin JWT claims.
5. **Ближайший релиз (P2):** удалить все console-логи с чувствительными полями.
6. **Параллельно (P2):** исправить compose-конфиг БД и проверку секретов на старте.

