# ResMon Web 🚀

**ResMon Web** — высокопроизводительный сервис телеметрии и мониторинга для Linux-систем с минимальным влиянием на ресурсы хоста и задержки, оформленный в современном тёмном Glassmorphism-дизайне.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-cyan.svg)

---

## 🌟 Ключевые возможности

- **⚡ Нулевое влияние на производительность (Zero-Overhead):**
  - Такт сбора метрик занимает **< 2 мс**.
  - Прямой неблокирующий опрос системных счетчиков без создания подпроцессов (`no fork/exec`).
  - **In-Memory Ring Buffer** (хранение 15 минут истории в RAM, ~5–10 МБ): нулевой износ диска и отсутствие дисковых задержек.
  - Отрисовка графиков на HTML5 Canvas (GPU браузера клиента), авто-пауза при неактивной вкладке.
- **📊 Глубокие Linux-метрики:**
  - **ЦП:** общая загрузка (%), загрузка каждого отдельного ядра в реальном времени, задержка/давление на процессор **Linux PSI (Pressure Stall Information)** (`/proc/pressure/cpu`), системный Load Average (1m, 5m, 15m).
  - **ОЗУ и Свап:** объем используемой, буферизованной, кэшированной и свободной памяти, процент подкачки Swap, динамика обращений к памяти — **Page Faults** (minor и major page faults/sec из `/proc/vmstat`), Memory PSI Pressure.
  - **Дисковая подсистема:** скорость чтения и записи (MB/s), операции ввода-вывода (Read/Write IOPS), I/O Stall Pressure, список физических смонтированных разделов с процентом заполнения.
  - **Сеть и сокеты:** пропускная способность сети (Rx/Tx KB/s), счетчики пакетов, распределение состояний сокетов (`ESTABLISHED`, `TIME_WAIT`, `LISTEN`, `SYN_SENT`), интерактивная таблица **открытых и активных listening-портов хоста** с именами процессов и PID.
  - **UFW:** read-only список разрешённых портов из `/etc/ufw/user.rules` и `user6.rules` (без запуска `ufw` и без привилегий).
- **🎨 Дизайн-система `ui-ux-pro-max`:**
  - Тёмная стеклянная тема (`#0F172A` / `#1B2336`), неоновые акценты подсистем (Cyan, Purple, Amber, Emerald).
  - Шрифты *Plus Jakarta Sans* и *JetBrains Mono*.
  - Векторные SVG-иконки Phosphor/Lucide (никаких эмодзи в качестве системных иконок).
  - Пауза/возобновление стриминга, переключение временного окна графиков (1м / 5м / 15м), индикатор задержки сети (Round-Trip Latency).

---

## 🐳 Быстрый запуск в Docker (Рекомендуемый способ)

Сервис читает хост-метрики через read-only mount `/proc`, `/sys`, `/etc/ufw` и journal; host PID namespace ему не нужен:

1. Склонируйте репозиторий и создайте `.env`:
   ```bash
   cp .env.example .env
   ```

2. Запустите через Docker Compose:
   ```bash
   docker compose up -d --build
   ```

3. Откройте в браузере:
   ```
   http://localhost:8080
   ```

По умолчанию контейнер слушает только `127.0.0.1` (`BIND_ADDR=127.0.0.1`). Публичный доступ — через существующий Caddy reverse proxy, см. раздел «Caddy».

*(Для изменения порта отредактируйте `PORT` в файле `.env`).*

---

## ⚙️ Настройки окружения (`.env`)

Все параметры конфигурируются через переменные окружения:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `PORT` | `8080` | Порт веб-сервера |
| `BIND_ADDR` | `127.0.0.1` | Адрес на хосте, куда Docker публикует порт. Наружу не открывайте |
| `HOST` | `0.0.0.0` | Интерфейс внутри контейнера |
| `UPDATE_INTERVAL` | `1.0` | Интервал сбора телеметрии и стриминга (в секундах) |
| `HISTORY_POINTS` | `900` | Размер кольцевого буфера в RAM (900 точек = 15 мин при 1s) |
| `HOST_PROC` | `/host/proc` (в Docker) или `/proc` | Путь к виртуальной ФС `/proc` хоста |
| `HOST_SYS` | `/host/sys` (в Docker) или `/sys` | Путь к виртуальной ФС `/sys` хоста |
| `HOST_UFW` | `/host/etc/ufw` | Каталог с конфигурацией UFW (read-only) |
| `HOST_JOURNAL_DIR` | `/host/var/log/journal` | Постоянный журнал systemd хоста (read-only) |
| `HOST_RUN_JOURNAL_DIR` | `/host/run/log/journal` | Volatile-журнал systemd хоста (read-only) |
| `LOG_LEVEL` | `info` | Уровень логирования (`debug`, `info`, `warning`) |
| `AUTH_ENABLED` | `true` | Включить авторизацию (HTTP Basic Auth + Cookie) |
| `AUTH_USERNAME` | `admin` | Логин администратора |
| `AUTH_PASSWORD` | обязателен | Пароль администратора; пустой и известные placeholder'ы не принимаются |
| `SECRET_KEY` | обязателен | Секретный ключ для подписи сессий (`openssl rand -hex 32`) |
| `COOKIE_SECURE` | `false` | `true`, если сервис стоит за HTTPS-прокси |
| `MAX_WS_CLIENTS` | `100` | Максимум одновременных WebSocket-клиентов |
| `MCP_ENABLED` | `false` | Включить read-only MCP-сервер на `/mcp` |
| `MCP_API_KEY` | `""` | Ключ доступа к MCP (обязателен при `MCP_ENABLED=true`) |

---

## 🔒 Безопасность и авторизация

Сервис не публикует порт наружу: `BIND_ADDR=127.0.0.1`. Публичный доступ — через существующий Caddy по HTTPS. Так Basic-пароль и MCP-ключ не ходят по открытому HTTP.

1. Задайте в `.env`:
   ```env
   AUTH_ENABLED=true
   AUTH_USERNAME=admin
   AUTH_PASSWORD=<сгенерируйте: openssl rand -base64 24>
   SECRET_KEY=<сгенерируйте: openssl rand -hex 32>
   ```
   Приложение не стартует, если `AUTH_ENABLED=true`, а пароль/секрет пустые или равны известным placeholder'ам.
2. **Как это работает:**
   - При открытии сайта браузер показывает **встроенное диалоговое окно входа** (HTTP Basic Auth).
   - После успешного входа выставляется сессионная `HttpOnly, SameSite=Lax` cookie с HMAC-подписью; `Secure` включается автоматически при HTTPS или через `COOKIE_SECURE=true`.
   - **Защита от брутфорса**: 10 неверных попыток с одного IP за 60 секунд → HTTP 429. `X-Forwarded-For` от клиента не принимается.
   - Сравнение учётных данных — constant-time; не-ASCII пароли не вызывают 500.

### Caddy (HTTPS)

Контейнер resmon остаётся на `127.0.0.1:1488`. Если Caddy запущен на хосте — проксируйте на `127.0.0.1:1488`. Если Caddy тоже в Docker (bridge), добавьте resmon в сеть Caddy и проксируйте на `resmon_web:1488`.

```caddyfile
resmon.185.240.121.158.sslip.io {
    # Caddy на хосте: 127.0.0.1:1488
    # Caddy в Docker: resmon_web:1488
    reverse_proxy resmon_web:1488 {
        flush_interval -1
    }

    header {
        Strict-Transport-Security "max-age=31536000"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
    }
}
```

В `.env`:
```env
BIND_ADDR=127.0.0.1
COOKIE_SECURE=true
```

Проверка и graceful reload:
```bash
# Caddy в Docker: конфиг должен быть смонтирован в контейнер
docker exec shlyapgrader_caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker exec shlyapgrader_caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile

curl -I https://resmon.185.240.121.158.sslip.io/
```

Если Caddy в Docker и resmon ещё не в его сети:
```bash
docker network create caddy_shared 2>/dev/null || true
docker network connect caddy_shared shlyapgrader_caddy
docker network connect caddy_shared resmon_web
```
Сеть нужно прописать в обоих compose-файлах, иначе она пропадёт после пересоздания контейнеров.

Ожидаемый ответ — `401` (нет логина), а не `502`. Порт 1488 наружу не открывайте; если правило было, удалите:
```bash
sudo ufw delete allow 1488/tcp
```

Если Caddy запущен в Docker-контейнере без `network_mode: host`, `127.0.0.1` указывает на сам контейнер Caddy. В этом случае используйте `network_mode: host` у Caddy либо общую Docker-сеть и адрес `resmon:1488`.

---

## 🤖 MCP-сервер (read-only)

MCP встроен в тот же процесс FastAPI и доступен по HTTP (Streamable HTTP) на `/mcp`. Он выключен по умолчанию.

### Включение

1. Добавьте в `.env`:
   ```env
   MCP_ENABLED=true
   MCP_API_KEY=<openssl rand -hex 32>
   ```
2. Перезапустите контейнер:
   ```bash
   docker compose up -d --build
   ```
3. Проверьте, что endpoint отвечает без ключа `401`:
   ```bash
   curl -i https://resmon.185.240.121.158.sslip.io/mcp
   ```

`MCP_API_KEY` обязателен: при `MCP_ENABLED=true` и пустом ключе MCP остаётся выключенным. Ключ передаётся в заголовке `Authorization: Bearer <ключ>` или `X-API-Key: <ключ>`. Авторизация веб-интерфейса (`AUTH_ENABLED`) на MCP не распространяется — у него отдельный ключ.

### Инструменты

| Инструмент | Параметры | Что возвращает |
|---|---|---|
| `get_metrics` | `start`, `end` (обязательны, ISO 8601 или Unix seconds) | Снимки метрик за указанный интервал. Доступно не более 5 минут назад; ответ прореживается до 60 точек. В каждом снимке те же данные, что в веб-интерфейсе: CPU, память, swap, load average, диски, сеть, порты и UFW. |
| `get_logs` | `source`: `system`, `systemd`, `docker`; `unit` (для `systemd`); `lines` (1–1000, по умолчанию 100) | Системный журнал (`journalctl`), журнал конкретного systemd-юнита или журнал `docker.service`. |

Примеры запросов к агенту:

- «Покажи метрики за последние 2 минуты»
- «Покажи последние 200 строк журнала nginx.service»
- «Покажи последние 100 строк системного журнала»
- «Покажи последние 100 строк журнала docker.service»

Ограничения:

- `get_metrics` не отдаёт данные старше 5 минут и требует явно указать `start` и `end`.
- Логи читаются из смонтированных journal-файлов хоста (`/var/log/journal` и `/run/log/journal`). Если на хосте не включён persistent journal, системные логи могут быть пустыми.
- `source=docker` — это журнал демона `docker.service`. Логи stdout/stderr контейнеров **недоступны**: для них нужен `/var/run/docker.sock`, который намеренно не монтируется.
- Если `get_logs` пустой, в ответе смотрите `journal_dirs` и `journal_files`. Если каталоги пустые, контейнер не видит журнал хоста: пересоздайте его через `docker compose up -d --force-recreate` (обычный `docker restart` не применяет новые volume-mounts).
- UFW показывается по конфигурации `/etc/ufw/user.rules` и `user6.rules` (только разрешающие правила), а не по live-состоянию ядра. Изменения файлов подхватываются в течение 5 секунд, перезапуск контейнера не нужен.

### Подключение к OpenCode

Добавьте сервер в `~/.config/opencode/opencode.json` (или в `opencode.json` проекта):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "resmon": {
        "type": "remote",
        "url": "https://resmon.185.240.121.158.sslip.io/mcp",
        "headers": {
          "Authorization": "Bearer {env:RESMON_MCP_KEY}"
        }
      }
    }
  }
}
```

Задайте ключ в окружении, из которого запускается OpenCode:

```bash
export RESMON_MCP_KEY='тот_же_ключ_что_в_MCP_API_KEY'
opencode mcp list
```

После этого инструменты `resmon_get_metrics` и `resmon_get_logs` появятся у агента. OpenCode ходит на публичный HTTPS-URL через Caddy; отдельный туннель не нужен.

---

## 🛠 Локальный запуск для разработки

### 1. Бэкенд (Python 3.11+)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

### 2. Фронтенд (Node.js 20+)
```bash
cd frontend
npm install
npm run dev
```
Фронтенд запустится на `http://localhost:3000` и будет автоматически проксировать запросы `/api` и `/ws` на `http://localhost:8080`.

### 3. Запуск тестов
```bash
PYTHONPATH=. .venv/bin/pytest -v --timeout=5
```

---

## 🏛 Архитектура решения

```
Host Linux (/proc, /sys, /etc/ufw, journal)
          │ (ro mounts)
          ▼
┌──────────────────────────────────────────────┐
│            ResMon Web Container              │
│                                              │
│  FastAPI Collector Loop (asyncio 1.0s)       │
│  ├── psutil (Non-blocking CPU/Net/Disk)      │
│  ├── /proc/pressure/{cpu,memory,io} (PSI)    │
│  ├── /proc/vmstat (Page Faults delta)        │
│  ├── /proc/1/net/* (host ports & sockets)    │
│  └── /etc/ufw/user*.rules (allowed ports)    │
│                     │                        │
│                     ▼                        │
│         In-Memory Ring Buffer                │
│         (collections.deque 900 points)       │
│          /        │             \            │
│         ▼         ▼             ▼            │
│  WebSocket   REST /api/history  MCP /mcp     │
│  /ws/metrics        │          (optional)    │
│                     ▼                        │
│  React 18 + Tailwind + Chart.js (dist)       │
└──────────────────────────────────────────────┘
```

## 📄 Лицензия
MIT
