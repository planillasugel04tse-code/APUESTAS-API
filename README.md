# ANALISYS BETSTOTAL

Plataforma de análisis deportivo orientada a cuotas, value bets, surebets/arbitraje, señales de Telegram, backtesting y seguimiento de resultados.

## Entorno de prueba

El repositorio incluye un entorno reproducible para probar la aplicación sin modificar tu instalación principal:

### Opción 1 — GitHub Codespaces

El proyecto incluye `.devcontainer/devcontainer.json`. Al abrir un Codespace sobre `main`, el entorno instala Python 3.13 y las dependencias, inicia automáticamente el servidor y reenvía el puerto 8000 al navegador.

### Opción 2 — Docker en Windows

```bash
copy .env.example .env
docker compose up --build
```

Después abre `http://localhost:8000/panel`.

### Opción 3 — Python local

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -e ".[dev]"
python -m uvicorn --app-dir src betano_analyzer.main:app --reload
```

Panel: `http://127.0.0.1:8000/panel`  
API: `http://127.0.0.1:8000/docs`  
Salud: `http://127.0.0.1:8000/health`

## Estado

- Producto: **ANALISYS BETSTOTAL**
- API: FastAPI
- Python: >= 3.13
- Base de datos: SQLite para desarrollo y pruebas
- Proveedores: integración preparada para OddsPapi y otros proveedores configurados
- Telegram: listener separado mediante Telethon
- Web: panel visual en `/panel`
- Gestión de proveedores: `/provider-accounts`
- Gestión de bookmakers: `/bookmakers`
- Documentación API: `/docs`
- Salud: `/health` y `/api/v1/health`

## Variables sensibles

Las claves y sesiones deben mantenerse fuera de Git. Usa `.env`/variables de entorno para credenciales de proveedores y Telegram.

Variables principales:

- `ODDSPAPI_KEY`
- `ODDS_API_KEY`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_PHONE`
- `TELEGRAM_SESSION_NAME`
- `TELEGRAM_CHANNELS`
- `TELEGRAM_ENABLED`
- `DB_PATH`

Para la prueba inicial, Telegram y los proveedores externos permanecen desactivados hasta introducir credenciales válidas.

## Arquitectura

```text
src/betano_analyzer/
├── main.py
├── api.py
├── db.py
├── bookmakers.py
├── bookmakers_api.py
├── provider_accounts.py
├── provider_accounts_api.py
├── oddspapi_scanner.py
├── oddspapi_scan_api.py
├── arbitrage.py
├── arbitrage_api.py
├── value_engine.py
├── radar.py
├── radar_value.py
├── master_radar.py
├── final_selector.py
├── conservative_engine.py
└── telegram/
```

## Funciones principales

### Analyzer

Calcula probabilidades implícitas, margen de mercado, probabilidades normalizadas y señales de valor a partir de las cuotas y estimaciones disponibles.

### Surebet / Arbitraje

Analiza oportunidades de arbitraje con las cuotas realmente disponibles. No inventa casas ni cuotas que no estén presentes en los datos.

### Perú

El modo Perú identifica las casas que el proveedor configurado realmente expone para la cuenta y separa disponibilidad del proveedor de la posibilidad real de operar con una casa.

### OddsPapi

El scanner consulta primero la cuenta y sus capacidades y puede explorar deportes, torneos, fixtures, bookmakers y mercados dentro del presupuesto de solicitudes configurado.

### Telegram

La integración está diseñada para ejecutarse como proceso separado del servidor web, evitando iniciar automáticamente una sesión de Telegram en un despliegue web.

## Tests

```bash
python -m pytest -q
```

El objetivo del repositorio es mantener un ciclo cerrado: **código → tests → CI → corrección → nueva validación**.

## Despliegue web

El repositorio contiene `Dockerfile` y `render.yaml` preparados para un servicio web. La creación de la cuenta/servicio externo y la autorización de despliegue son pasos de la plataforma de hosting; GitHub por sí solo no crea una URL pública persistente.
