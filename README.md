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
  - **Сеть и сокеты:** пропускная способность сети (Rx/Tx KB/s), счетчики пакетов, распределение состояний сокетов (`ESTABLISHED`, `TIME_WAIT`, `LISTEN`, `SYN_SENT`), интерактивная таблица **открытых и активных listening-портов** с именами процессов и PID.
- **🎨 Дизайн-система `ui-ux-pro-max`:**
  - Тёмная стеклянная тема (`#0F172A` / `#1B2336`), неоновые акценты подсистем (Cyan, Purple, Amber, Emerald).
  - Шрифты *Plus Jakarta Sans* и *JetBrains Mono*.
  - Векторные SVG-иконки Phosphor/Lucide (никаких эмодзи в качестве системных иконок).
  - Пауза/возобновление стриминга, переключение временного окна графиков (1м / 5м / 15м), индикатор задержки сети (Round-Trip Latency).

---

## 🐳 Быстрый запуск в Docker (Рекомендуемый способ)

Сервис сконфигурирован для прямого доступа к хост-метрикам Linux через режимы `network_mode: host` и `pid: host`:

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

*(Для изменения порта отредактируйте `PORT` в файле `.env`).*

---

## ⚙️ Настройки окружения (`.env`)

Все параметры конфигурируются через переменные окружения:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `PORT` | `8080` | Порт веб-сервера |
| `HOST` | `0.0.0.0` | Сетевой интерфейс прослушивания |
| `UPDATE_INTERVAL` | `1.0` | Интервал сбора телеметрии и стриминга (в секундах) |
| `HISTORY_POINTS` | `900` | Размер кольцевого буфера в RAM (900 точек = 15 мин при 1s) |
| `HOST_PROC` | `/host/proc` (в Docker) или `/proc` | Путь к виртуальной ФС `/proc` хоста |
| `HOST_SYS` | `/host/sys` (в Docker) или `/sys` | Путь к виртуальной ФС `/sys` хоста |
| `LOG_LEVEL` | `info` | Уровень логирования (`debug`, `info`, `warning`) |
| `AUTH_ENABLED` | `false` | Включить авторизацию (HTTP Basic Auth + Cookie) |
| `AUTH_USERNAME` | `admin` | Логин администратора |
| `AUTH_PASSWORD` | `""` | Пароль администратора |
| `SECRET_KEY` | `...` | Секретный ключ для подписи сессий |

---

## 🔒 Безопасность и авторизация

При открытом в интернет порту рекомендуется включить авторизацию:
1. Задайте в `.env`:
   ```env
   AUTH_ENABLED=true
   AUTH_USERNAME=admin
   AUTH_PASSWORD=ваш_надежный_пароль
   SECRET_KEY=произвольная_длинная_строка
   ```
2. **Как это работает:**
   - При открытии сайта браузер показывает **встроенное диалоговое окно входа** (HTTP Basic Auth).
   - После успешного входа выставляется сессионная `HttpOnly, SameSite=Lax` cookie с HMAC-подписью, которая автоматически и безопасно авторизует WebSocket (`/ws/metrics`).
   - Имеется встроенная **защита от брутфорса**: после 5 неверных попыток ввода IP-адрес блокируется на 60 секунд (HTTP 429).
   - Сравнение учетных данных выполняется через `secrets.compare_digest` (защита от атак по времени).

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
Host Linux (/proc, /sys, host net/pid)
          │ (ro mounts)
          ▼
┌──────────────────────────────────────────────┐
│            ResMon Web Container              │
│                                              │
│  FastAPI Collector Loop (asyncio 1.0s)       │
│  ├── psutil (Non-blocking CPU/Net/Disk)      │
│  ├── /proc/pressure/{cpu,memory,io} (PSI)    │
│  ├── /proc/vmstat (Page Faults delta)        │
│  └── /proc/net/* (Active ports & sockets)    │
│                     │                        │
│                     ▼                        │
│         In-Memory Ring Buffer                │
│         (collections.deque 900 points)       │
│          /                  \                │
│         ▼                    ▼               │
│  WebSocket (/ws/metrics)   REST (/api/history)│
│                     │                        │
│                     ▼                        │
│  React 18 + Tailwind + Chart.js (dist)       │
└──────────────────────────────────────────────┘
```

## 📄 Лицензия
MIT
