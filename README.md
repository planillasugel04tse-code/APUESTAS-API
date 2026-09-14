# ANALISYS BETSTOTAL

Plataforma de análisis deportivo orientada a cuotas, value bets, surebets/arbitraje, señales de Telegram, pronósticos de IA, tipsters públicos, Betmains, estadísticas y seguimiento de resultados.

## Arquitectura objetivo

```text
FUENTES
├── Tipsters públicos (web/RSS/Atom/HTML permitido)
├── Telegram (listener Telethon)
├── Pronósticos de IA
├── OddsPapi / cuotas de mercado
└── Betmains (integración autenticada si existe; foto como respaldo)
        ↓
NORMALIZACIÓN
        ↓
MATCHING DEL EVENTO + MERCADO + LÍNEA
        ↓
VALIDACIÓN ESTADÍSTICA
├── forma / histórico disponible
├── modelo Poisson/Elo/Monte Carlo existente
├── consenso entre fuentes
├── movimiento/cuota y probabilidad implícita
└── árbitro cuando una fuente de datos lo entregue
        ↓
VALUE ENGINE
        ↓
SAFER ENGINE
├── gana local → 1X
├── gana visitante → X2
├── Over 3 → Over 2 (cuando el mercado/línea lo permite)
└── solo transformaciones explícitas y auditables
        ↓
SELECTOR
├── cuota objetivo preferida: 1.40–2.10
├── límite duro: 2.50
├── máximo 3 selecciones
└── preferencia por 2 si 3 hacen subir demasiado la cuota
        ↓
SALIDAS SEPARADAS
├── MEJORES JUGADAS
├── COMBINADA SEGURA
├── SUREBET
├── TIPSTERS
├── IA
├── TELEGRAM
└── BETMAINS
```

## Estado de implementación

- **Dashboard y panel web**: disponibles.
- **OddsPapi**: conexión configurable, comprobación de cuenta y scanner de capacidades/datos.
- **Surebet**: Perú / Mundial / Todo, Pre-match / Live, separación por liga y verificación.
- **LIVE Mundial**: descubre automáticamente bookmakers que exponen live odds y procesa fixtures en lotes internos; el límite técnico no se presenta como límite de producto.
- **Range Strategy / Gap Detection**: disponible para goals y corners.
- **Telegram**: parser, matching, almacenamiento, backtest y listener Telethon separado.
- **Tipster Intelligence**: motor unificado para tipsters web, Telegram, IA y entradas Betmains.
- **Betmains**: no se presupone acceso a una cuenta privada. Se agregó carga de foto como respaldo y punto de entrada para extracción.
- **CI**: pruebas automáticas con Python 3.13.
- **Docker/Render**: archivos de despliegue preparados; la activación del hosting sigue requiriendo autorización en la plataforma externa.

## Tipsters automáticos

La pantalla `/tipsters` concentra la inteligencia de fuentes.

El colector web utiliza fuentes públicas registradas en `data/tipster_sources.json`. No intenta saltar logins, CAPTCHAs, paywalls ni controles de acceso. Telegram usa el listener existente y entrega sus señales al mismo motor.

La meta no es prometer "todos los tipsters de Internet" —eso no es técnicamente verificable— sino construir un **registro automático y ampliable de fuentes públicas** y procesarlas con una misma lógica.

## Motor de valor y seguridad

Cada pick se normaliza y se compara con:

1. cuota de mercado y probabilidad implícita;
2. probabilidad del modelo cuando hay datos suficientes;
3. forma/histórico cuando existe evidencia;
4. consenso entre fuentes;
5. árbitro cuando hay un dato verificable disponible;
6. completitud de datos.

Si faltan datos importantes, el motor reduce el nivel de confianza y puede devolver `WATCH` en vez de inventar una ventaja.

El sistema puede proponer una alternativa conservadora. Ejemplos: `local` → `1X`; `visitante` → `X2`; `Over 3` → `Over 2`. Estas son **alternativas de menor exigencia**, no garantías de ganar.

## Reglas de combinada

- cuota preferida por selección: **1.40–2.10**;
- límite duro por selección: **2.50**;
- máximo: **3 selecciones**;
- se priorizan 2 selecciones cuando la tercera hace que el total pierda el rango de seguridad definido;
- no se presenta una combinada si no hay valor estadístico suficiente.

## Betmains

No se afirma una conexión directa a una cuenta privada de Betmains sin una API/integración autorizada. En `/tipsters` existe un formulario para subir la foto de la jugada y conservarla como entrada de análisis. La arquitectura deja ese dato separado de las fuentes automáticas.

## Prueba rápida

### GitHub Codespaces

El proyecto incluye `.devcontainer/devcontainer.json`. Abre un Codespace sobre `main`; el entorno instala Python 3.13, dependencias y expone el puerto 8000.

### Docker

```bash
copy .env.example .env
docker compose up --build
```

Panel: `/panel`  
Tipsters/IA/Betmains: `/tipsters`  
Proveedores: `/provider-accounts`  
API: `/docs`  
Salud: `/health`

## Telegram

El listener se ejecuta separado del servidor web:

```bash
betstotal-telegram
```

Variables requeridas:

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

El scanner consulta las capacidades reales de la cuenta antes de explorar deportes, torneos, fixtures, bookmakers y mercados. OddsPapi documenta endpoints para deportes, torneos, fixtures, cuotas, histórico y resultados; la disponibilidad concreta depende de la cuenta y del proveedor. citeturn0search0turn2search7

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

## Tipster API

- `POST /api/v1/tipsters/analyze` — analiza un pick normalizado.
- `POST /api/v1/tipsters/ai` — normaliza y analiza un pronóstico de IA.
- `POST /api/v1/tipsters/collect-web` — actualiza las fuentes públicas registradas.
- `POST /api/v1/tipsters/combinada` — selecciona como máximo 3 legs según las reglas.
- `POST /api/v1/tipsters/betmains/photo` — recibe una foto de una jugada de Betmains.

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
