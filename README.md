# ANALISYS BETSTOTAL

Plataforma de análisis deportivo orientada a cuotas, value bets, surebets/arbitraje, señales de Telegram, backtesting y seguimiento de resultados.

## Estado de implementación

- **Dashboard y panel web**: disponibles.
- **OddsPapi**: conexión configurable, comprobación de cuenta y scanner de capacidades/datos.
- **Surebet**: Perú / Mundial / Todo, Pre-match / Live, separación por liga y verificación.
- **LIVE Mundial**: descubre automáticamente bookmakers que exponen live odds y procesa fixtures en lotes internos; el límite técnico no se presenta como límite de producto.
- **Range Strategy / Gap Detection**: disponible para goals y corners.
- **Telegram**: parser, matching, almacenamiento, backtest y listener Telethon separado.
- **CI**: pruebas automáticas con Python 3.13.
- **Docker/Render**: archivos de despliegue preparados; la activación del hosting sigue requiriendo autorización en la plataforma externa.

## Prueba rápida

### GitHub Codespaces

El proyecto incluye `.devcontainer/devcontainer.json`. Abre un Codespace sobre `main`; el entorno instala Python 3.13, dependencias y expone el puerto 8000.

### Docker

```bash
copy .env.example .env
docker compose up --build
```

Panel: `/panel`  
API: `/docs`  
Salud: `/health`

## Telegram

El listener se ejecuta separado del servidor web:

```bash
betstotal-telegram
```

Variables requeridas para activarlo:

- `TELEGRAM_ENABLED=true`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_PHONE` (opcional si Telethon ya tiene sesión válida)
- `TELEGRAM_SESSION_NAME`
- `TELEGRAM_CHANNELS` (usuarios/IDs separados por comas o `*`)

El listener **solo lee mensajes y los entrega al pipeline de análisis**. No coloca apuestas ni modifica Telegram.

## OddsPapi

Variables:

- `ODDSPAPI_KEY`
- `ODDS_API_KEY` (proveedor opcional)

El scanner consulta las capacidades reales de la cuenta antes de intentar explorar deportes, torneos, fixtures, bookmakers y mercados. Las cuotas Live dependen de que el bookmaker y el mercado estén realmente expuestos por la cuenta del proveedor.

## Surebet

La interfaz separa:

```text
SUREBET
├── PERÚ
├── MUNDIAL
└── TODO
    ├── PRE-MATCH
    └── LIVE
        └── LIGA → OPORTUNIDAD → VERIFICAR
```

Las oportunidades se calculan únicamente con cuotas almacenadas/actualizadas por el proveedor. Una oportunidad Live debe volver a verificarse antes de considerarse confirmada.

## Range Strategy

Endpoint:

```text
GET /api/v1/range-strategy
```

Analiza huecos entre líneas de goals/corners y estima la probabilidad de que el resultado quede dentro del intervalo. Es análisis estadístico; no coloca apuestas.

## Telegram API

- `POST /api/v1/telegram/signals` — procesa una señal.
- `GET /api/v1/telegram/signals` — consulta señales almacenadas.
- `GET /api/v1/telegram/config` — estado seguro de configuración.
- `POST /api/v1/telegram/retry-pending` — reintenta matching de partidos aún no encontrados.
- `GET /api/v1/telegram/backtest` — backtest de picks Telegram liquidados.

## Variables sensibles

No subas `.env`, sesiones de Telegram ni claves reales al repositorio. `.env.example` contiene únicamente nombres y valores de ejemplo.

## Tests

```bash
python -m pytest -q
```

El ciclo de calidad es:

**código → tests → CI → corrección → nueva validación**.

## Despliegue

`Dockerfile` y `render.yaml` están preparados para un servicio web. GitHub mantiene el código; la URL pública persistente depende de activar un proveedor de hosting y configurar sus variables/secretos.

La base SQLite es apropiada para desarrollo/pruebas. Para producción con alta concurrencia o persistencia garantizada debe sustituirse por una base de datos gestionada.
