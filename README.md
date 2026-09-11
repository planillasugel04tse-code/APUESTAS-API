# Betano Live Analyzer

Analizador local de fútbol que integra señales de Telegram con cuotas de Betano, detecta value bets y surebets, y las backtestea contra resultados históricos.

## Índice

- [Instalación](#instalación)
- [Configuración](#configuración)
- [Variables de entorno](#variables-de-entorno)
- [Ejecución](#ejecución)
- [Arquitectura](#arquitectura)
- [Flujo completo](#flujo-completo)
- [Telegram](#telegram)
- [Endpoints](#endpoints)
- [Analyzer](#analyzer)
- [Surebet / Arbitraje](#surebet--arbitraje)
- [Live vs Pre-Match](#live-vs-pre-match)
- [Tests](#tests)
- [Seguridad](#seguridad)

---

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -e .
pip install -e ".[dev]"       # incluye pytest
```

**Requiere Python ≥ 3.13.**

---

## Configuración

Copia y ajusta el archivo de entorno:

```bash
cp .env.example .env
```

Si no existe `.env.example`, crea un `.env` con las variables listadas abajo.

---

## Variables de entorno

| Variable | Descripción | Defecto |
|---|---|---|
| `DB_PATH` | Ruta absoluta del archivo SQLite | `betano_analyzer.sqlite3` (CWD) |
| `TELEGRAM_API_ID` | API ID de Telegram (my.telegram.org) | — |
| `TELEGRAM_API_HASH` | API Hash de Telegram | — |
| `TELEGRAM_PHONE` | Teléfono de la cuenta Telegram (`+51...`) | — |
| `TELEGRAM_SESSION_NAME` | Nombre del archivo `.session` | `telebet_session` |
| `TELEGRAM_CHANNELS` | Canales a escuchar (coma) o `*` para todos | `*` (todos) |
| `TELEGRAM_ENABLED` | Activar listener (`true`/`false`) | `true` |
| `LIVE_STALE_MINUTES` | Minutos máximos de antigüedad para cuotas Live | `15` |
| `ODDSPAPI_KEY` | API key de OddsPapi | — |
| `ODDS_API_KEY` | API key de The Odds API | — |

> **NUNCA subas `.env`, `*.session`, `*.db` ni claves a Git.**

---

## Ejecución

### Servidor API local

```bash
uvicorn betano_analyzer.main:app --reload
```

La API queda disponible en `http://localhost:8000`.  
Documentación interactiva en `http://localhost:8000/docs`.

### Listener Telegram (proceso separado)

```bash
python -c "from betano_analyzer.telegram import start_telegram_listener; start_telegram_listener()"
```

El listener conecta con Telethon, escucha los canales configurados y procesa cada mensaje automáticamente.

---

## Arquitectura

```
src/betano_analyzer/
├── main.py                  # FastAPI app + lifespan
├── api.py                   # Router CRUD + analítico principal
├── db.py                    # SQLite + schema + migrations
│
├── telegram/                # Adaptador de entrada Telegram
│   ├── parser.py            # Extracción conservadora desde texto libre
│   ├── service.py           # Orquestación: parser → matching → análisis → DB
│   ├── collector.py         # Listener Telethon (tiempo real)
│   ├── config.py            # Carga env vars de Telegram
│   └── backtest.py          # Backtest de señales Telegram via core engine
│
├── matching.py              # Matching conservador de equipos (0.90 threshold)
├── ingest.py                # Normalización mercados/selecciones/competiciones
├── ingestion_service.py     # Persistencia de partidos y cuotas normalizadas
│
├── arbitrage.py             # Motor Surebet Pre-Match + Live (con freshness)
├── arbitrage_api.py         # Endpoints /arbitrage/pre-match, /live, /verify
│
├── value_engine.py          # devig, fair_market, value_signal
├── radar_value.py           # Value Radar (consenso multi-casa)
├── radar.py                 # Radar base (tipsters + historial)
├── master_radar.py          # Master Radar (fusión de todas las señales)
├── final_selector.py        # Final Selector (con razón de descarte)
│
├── probability_fusion.py    # Fusión modelo + mercado
├── opportunities.py         # Scoring de oportunidades
├── conservative_engine.py   # Transformaciones conservadoras
│
├── calibration.py           # Brier score, log loss, calibration error
├── calibration_gate.py      # Gate de calibración sobre confianza del modelo
│
├── backtest.py              # Motor core de backtest (evaluate, compare)
├── backtest_report.py       # Informe completo por período/competición/mercado
│
├── stake.py                 # Distribución matemática de stake (arbitraje)
├── clv.py                   # Closing Line Value
├── market_movement.py       # Movimiento de cuotas
├── sync_service.py          # Sync desde OddsAPI y OddsPapi
│
└── analysis/                # Módulos auxiliares de análisis
    ├── markets.py
    └── value.py
```

### Base de datos

SQLite. Tablas principales:

| Tabla | Descripción |
|---|---|
| `matches` | Partidos (external_id, competition, kickoff, status) |
| `tipsters` | Tipsters registrados |
| `picks` | Picks con estrategia original y conservadora |
| `odds` | Snapshots de cuotas por bookmaker/mercado/selección/timestamp |
| `bets` | Apuestas reales registradas |
| `pick_results` | Resultados liquidados por pick |
| `pick_strategy_results` | Resultados por estrategia (original/conservadora) |
| `clv_snapshots` | Closing Line Value |
| `telegram_signals` | Señales procesadas de Telegram |
| `telegram_messages` | Mensajes crudos de Telegram |

---

## Flujo completo

```
TELEGRAM mensaje
  └─ parser.py         → ParsedTelegramPick
       └─ matching.py  → evento DB (conservador: 0.90 threshold + gap 0.05)
           ├── [NO MATCH] → pending_match (reintento con retry_pending_matches)
           └── [MATCH]
                ├── normalize_market() → canonical market/selection
                ├── _latest_betano_quote() → betano_current_odds (SEPARADO de tipster_odds)
                ├── _ensure_tipster_and_pick() → pick_id
                ├── build_value_radar() → value_item
                ├── build_master_radar() → master_item
                ├── build_final_selection() → final_item
                ├── find_arbitrage() → surebets
                └── DB: telegram_signals + telegram_messages
```

---

## Telegram

### Formatos de mensaje soportados

```
# Básico
Manchester United vs Chelsea cuota 1.95

# Con competición
🏆 UEFA Champions League ⚽ Barcelona vs PSG cuota 2.10 stake 3

# Con market
Liverpool vs Arsenal Over 2.5 goles cuota 1.85

# Con handicap
Real Madrid vs Villarreal handicap -1.5 cuota 2.20

# BTTS
Bayern Munich vs Borussia Dortmund BTTS Sí cuota 1.70

# Con fecha/hora
Juventus vs Napoli 2026-09-15 20:45 UTC cuota 1.80
```

### Mercados detectados

| Mercado | Keywords |
|---|---|
| `1x2` | (defecto) |
| `goals` | over, under, más de, menos de, goles |
| `btts` | ambos, btts |
| `corners` | corner, córner, corners |
| `cards` | tarjeta, tarjetas, cards |
| `asian_handicap` | handicap, hándicap, asian handicap, ah, spread |
| `double_chance` | 1x, x2, 12, doble oportunidad |

### Separación de precios

**Garantía fundamental:** `tipster_odds` (precio del Telegram) y `betano_current_odds` (último snapshot Betano en DB) **nunca se mezclan**. Cada uno conserva su origen y timestamp.

### Pending match + retry

Cuando una señal llega antes de que el partido exista en la DB:
1. Se persiste como `match_status='pending_match'`.
2. Tras un sync de datos, llama `POST /api/v1/telegram/retry-pending` para resolverlas.

---

## Endpoints

### Análisis

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/opportunities` | Radar base de oportunidades |
| GET | `/api/v1/value-radar` | Value Radar (consenso multi-casa vs Betano) |
| GET | `/api/v1/master-radar` | Master Radar (fusión de todas las señales) |
| GET | `/api/v1/final-selection` | Final Selector (top 10 con razón de descarte) |
| GET | `/api/v1/backtest/report` | Informe de backtest por período |

### Arbitraje / Surebet

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/arbitrage/pre-match` | Surebets Pre-Match (cuotas almacenadas) |
| POST | `/api/v1/arbitrage/live` | Surebets Live (refresh on-demand) |
| POST | `/api/v1/arbitrage/verify/{match_id}` | Verifica surebet en un partido específico |

### Telegram

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/telegram/signals` | Procesa un mensaje de Telegram manualmente |
| GET | `/api/v1/telegram/signals` | Lista señales procesadas |
| POST | `/api/v1/telegram/retry-pending` | Reintenta matching de señales pendientes |
| GET | `/api/v1/telegram/backtest` | Backtest de señales Telegram liquidadas |

### CRUD

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/matches` | Crea un partido |
| POST | `/api/v1/tipsters` | Registra un tipster |
| POST | `/api/v1/odds` | Ingresa una cuota |
| POST | `/api/v1/picks` | Registra un pick |
| POST | `/api/v1/picks/{id}/result` | Liquida un pick |
| POST | `/api/v1/bets` | Registra una apuesta real |
| PATCH | `/api/v1/bets/{id}/settle` | Liquida una apuesta |

### Otros

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/movements` | Movimiento de cuotas |
| GET | `/api/v1/clv/summary` | Resumen CLV |
| POST | `/api/v1/sync/odds` | Sync desde proveedor |
| GET | `/api/v1/providers` | Estado de proveedores |
| GET | `/health` | Healthcheck |
| GET | `/` | Dashboard web |

---

## Analyzer

### Value Radar

Compara las cuotas de Betano contra el consenso de-vigado de otras casas. Solo reporta cuando el edge supera 3%.

### Master Radar

Fusiona: value radar + radar base + movimiento de cuotas + tipster signal + CLV + calibración de probabilidades. Genera `master_score` (0-100) con rating: `fuerte` ≥ 80, `interesante` ≥ 68, `vigilar` ≥ 55.

### Final Selector

Filtra del Master Radar solo las oportunidades que cumplen TODOS los criterios:
- `master_score ≥ 68`
- `edge ≥ 0.03`
- `ev ≥ 0.03`
- `fused_probability ≥ 0.50` (cuando está disponible)
- `bookmakers ≥ 2`
- `positive_signals ≥ 2`

Cada oportunidad rechazada incluye `rejection_reason` con el criterio que falló.

---

## Surebet / Arbitraje

### Pre-Match

- Usa cuotas almacenadas (no hace llamadas externas).
- Solo usa el snapshot más reciente por bookmaker/outcome (las cuotas antiguas no crean phantom surebets).
- Requiere todos los outcomes del mercado para calcular el arbitraje.

### Live

- Hace un refresh on-demand vía OddsPapi al pulsar el botón.
- **Cuotas Live con más de `LIVE_STALE_MINUTES` minutos de antigüedad son RECHAZADAS.**
- Un partido no puede generar surebet Live si tiene `status='scheduled'`.

### Stake allocation

```python
from betano_analyzer.stake import allocate_stakes

result = allocate_stakes({"home": 2.20, "draw": 4.20, "away": 4.20}, total_stake=100)
# result.guaranteed_profit ≈ X
# result.stakes = {"home": ..., "draw": ..., "away": ...}
```

---

## Live vs Pre-Match

La clasificación se basa en `matches.status` (campo de la DB), no solo en el kickoff:

| Status en DB | `_is_live()` | Aparece en Live | Aparece en Pre-Match |
|---|---|---|---|
| `live`, `in_play` | `True` | ✅ | ❌ |
| `scheduled`, `pre_match` | `False` | ❌ | ✅ |
| `finished`, `cancelled` | `False` | ❌ | ❌ |
| (vacío / desconocido) | Por kickoff | según tiempo | según tiempo |

---

## Tests

```bash
# Ejecutar toda la suite
python -m pytest tests/ -v

# Solo tests de Telegram
python -m pytest tests/test_telegram_core.py -v

# Solo tests E2E
python -m pytest tests/test_integration_e2e.py -v

# Solo tests de arbitraje (incluye freshness)
python -m pytest tests/test_arbitrage.py -v
```

**117 tests, 0 failures** en el estado actual.

Cobertura de tests:
- Parser: 9 tests (mercados, datetime, stake, casos inválidos)
- Matching: 7 tests (aliases, acentos, gap mínimo, score bajo)
- Arbitraje: 9 tests (pre-match, live, stale, freshness, is_live)
- Final Selector: 9 tests (rejection_reason, APOSTAR/VIGILAR, rejected[])
- Backtest: 6 tests (ROI, look-ahead bias, push, compare_strategies)
- E2E: 7 tests (happy path, idempotencia, pending+retry, stale live, separación de precios)

---

## Seguridad

- `.env` está en `.gitignore` — nunca se sube.
- `*.session` (Telethon) está en `.gitignore` — nunca se sube.
- `*.db` / `*.sqlite3` están en `.gitignore`.
- El sistema no realiza apuestas ni inicia sesión en cuentas de casas de apuestas.
- No almacena credenciales de usuarios de Betano.

---

## Desarrollo

**Stack:** Python 3.13+ · FastAPI · SQLite · Telethon · Pydantic v2

**Principios:** SOLID · Clean Architecture · DRY · Conservative matching · No look-ahead bias
