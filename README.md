# Betting Opportunity Analyzer

Una aplicación profesional en Python para analizar oportunidades deportivas mediante cuotas, estadísticas y modelos matemáticos.

> [!IMPORTANT]
> **NO REALIZA APUESTAS AUTOMÁTICAMENTE.**
> El sistema recopila datos, analiza cuotas, calcula probabilidades y detecta oportunidades únicamente para que el usuario tome decisiones manualmente.

---

## Características Principales

1. **Modo DEMO Offline**: Funciona completamente offline sin necesidad de APIs externas pagas utilizando `data/sample_odds.json` y `data/historical_matches.json`.
2. **Módulo 1: Surebet Analyzer**: Detección de arbitrajes matemáticos libres de riesgo directo (`inverse_sum < 1`), cálculo de ROI y distribución de stakes con precisión `Decimal`.
3. **Módulo 2: Value Betting Analyzer**: Modelo de probabilidad estimada (Poisson / Estadístico) vs cuotas de mercado para hallar ventajas (Edge %) y stake recomendado según Criterio de Kelly.
4. **Módulo 3: Range Strategy Analyzer**: Análisis de coberturas y líneas (Corners / Goles), detección de huecos (gaps) entre operadores, probabilidad Poisson de hueco y riesgo.
5. **Estadísticas Avanzadas**: Cálculo de media, mediana, desviación estándar y distribuciones Poisson para equipos.
6. **Dashboard Moderno**: Interfaz oscura glassmorphic en HTML5/CSS3/Vanilla JS con gráficos, calculadora interactiva de bankroll y filtros en tiempo real.
7. **Base de Datos SQLite**: Almacenamiento persistente de eventos, cuotas, oportunidades detectadas e historial de auditoría.

---

## Estructura del Proyecto

```text
betting_analyzer/
├── app.py                      # Punto de entrada Flask y Servidor Local
├── requirements.txt            # Dependencias Python
├── README.md                   # Documentación oficial
├── .env.example                # Variables de entorno de ejemplo
├── .env                        # Variables de entorno locales
├── .gitignore                  # Filtros de control de versiones
│
├── src/                        # Código fuente modular
│   ├── config.py               # Gestión de configuración y rutas
│   ├── database.py             # SQLite DDL y operaciones CRUD
│   ├── models.py               # Modelos Pydantic y Esquema Estándar de Eventos
│   ├── services.py             # Orquestador de proveedores y analizadores
│   │
│   ├── providers/              # Sistema de proveedores de cuotas
│   │   ├── base_provider.py    # Interfaz abstracta OddsProvider
│   │   ├── demo_provider.py    # Proveedor local DEMO (JSON)
│   │   └── api_provider.py     # Proveedor aislado para APIs externas
│   │
│   ├── odds/                   # Normalización y emparejamiento
│   │   ├── normalizer.py       # Conversor de formatos y remoción de margen
│   │   └── matcher.py          # Extracción de mejores cuotas por selección
│   │
│   ├── analyzers/              # Módulos principales de análisis
│   │   ├── surebet.py          # Módulo 1: Surebet Arbitrage
│   │   ├── value_betting.py    # Módulo 2: Value Betting (Edge %)
│   │   └── range_strategy.py   # Módulo 3: Range Strategy & Gap Detection
│   │
│   ├── calculators/            # Calculadoras matemáticas
│   │   ├── stakes.py           # Stake surebet (Decimal) & Kelly Criterion
│   │   ├── probability.py      # Probabilidad implícita y matriz Poisson
│   │   └── roi.py              # ROI y Expected Value (EV)
│   │
│   └── statistics/             # Análisis estadístico histórico
│       ├── goals.py            # Media, mediana y std dev de goles
│       ├── corners.py          # Estadísticas de corners
│       └── trends.py           # Rachas y estado de forma reciente
│
├── data/                       # Archivos de datos de muestra
│   ├── sample_odds.json        # Muestra de cuotas de casas de apuestas
│   └── historical_matches.json # Histórico de partidos para modelos
│
├── templates/                  # Vistas Jinja2 HTML
│   ├── base.html
│   ├── dashboard.html
│   ├── opportunities.html
│   ├── surebets.html
│   ├── valuebets.html
│   ├── range.html
│   ├── history.html
│   └── settings.html
│
├── static/                     # Archivos estáticos de interfaz
│   ├── css/style.css           # Estilos oscuros glassmorphic
│   └── js/app.js               # Interactividad Vanilla JS
│
└── tests/                      # Suite de pruebas unitarias con pytest
    ├── test_surebet.py
    ├── test_valuebet.py
    ├── test_range.py
    └── test_calculators.py
```

---

## Primera Ejecución Desde Un IDE

Estas instrucciones asumen que abrirás la carpeta del proyecto en un IDE como VS Code, PyCharm, Cursor o similar.

### 1. Abrir la carpeta correcta

Abre esta carpeta como proyecto:

```text
betting-analyzer
```

El archivo principal debe quedar visible en la raíz:

```text
app.py
```

### 2. Abrir la terminal integrada del IDE

En la terminal integrada, confirma que estás dentro de la carpeta del proyecto. Debes ver archivos como `app.py`, `requirements.txt`, `src`, `templates` y `data`.

### 3. Crear el entorno virtual

Windows PowerShell:

```powershell
python -m venv venv
```

### 4. Activar el entorno virtual

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación, ejecuta una sola vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Luego vuelve a activar:

```powershell
.\venv\Scripts\Activate.ps1
```

Cuando esté activo, la terminal normalmente mostrará algo como:

```text
(venv)
```

### 5. Instalar dependencias

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 6. Ejecutar el proyecto

```powershell
python app.py
```

Si todo está correcto, la terminal mostrará que Flask está corriendo localmente.

### 7. Abrir la aplicación

Abre esta URL en tu navegador:

```text
http://127.0.0.1:5000
```

El sistema inicia en `MODO DEMO`, por lo que no necesitas configurar APIs externas para usarlo por primera vez.

### 8. Detener el servidor

En la terminal donde está corriendo Flask, presiona:

```text
Ctrl + C
```

## Ejecución Rápida Después De La Primera Vez

Cada vez que vuelvas a abrir el proyecto en tu IDE:

```powershell
.\venv\Scripts\Activate.ps1
python app.py
```

Luego abre:

```text
http://127.0.0.1:5000
```

## Problemas Comunes

Si aparece `python no se reconoce`, instala Python y marca la opción `Add Python to PATH`.

Si aparece `No module named flask`, activa el entorno virtual e instala dependencias con `python -m pip install -r requirements.txt`.

Si el puerto `5000` está ocupado, cambia `PORT=5000` en `.env` por otro puerto, por ejemplo `PORT=5001`, y abre `http://127.0.0.1:5001`.

---

## Modo Real Con OddsPapi

El proyecto puede usar cuotas reales desde OddsPapi. No pegues tu API key en el frontend, en chats ni en capturas. La clave va solamente en `.env`.

### 1. Configurar `.env`

Para usar datos reales, cambia o agrega estos valores:

```env
PROVIDER_MODE=API
EXTERNAL_API_KEY=TU_API_KEY_DE_ODDSPAPI
EXTERNAL_API_URL=https://api.oddspapi.io/v4

ODDSPAPI_SPORT_ID=10
ODDSPAPI_LANGUAGE=es
ODDSPAPI_ODDS_FORMAT=decimal
ODDSPAPI_BOOKMAKERS=apuestatotal,betano.pe,inkabet,pinnacle
ODDSPAPI_USE_TOURNAMENTS=0
ODDSPAPI_TOURNAMENT_IDS=
ODDSPAPI_FIXTURE_DAYS=2
ODDSPAPI_MAX_FIXTURES=3
```

`ODDSPAPI_SPORT_ID=10` corresponde a fútbol según la documentación de OddsPapi.

Casas iniciales recomendadas para Perú:

```text
apuestatotal,betano.pe,inkabet,pinnacle
```

`pinnacle` se incluye como referencia sharp para comparar precios contra casas locales.

### 2. Ejecutar la app

```powershell
.\venv\Scripts\Activate.ps1
python app.py
```

Abre:

```text
http://127.0.0.1:5000
```

En `MODO API`, el dashboard no descarga cuotas automáticamente para no gastar tu cuota mensual. Usa el botón `Actualizar Cuotas Reales`.

### Flujo recomendado para Perú

Primero busca el ID del torneo peruano:

```text
http://127.0.0.1:5000/api/tournaments?q=peru
```

También puedes buscar por nombre:

```text
http://127.0.0.1:5000/api/tournaments?q=liga
```

Cuando encuentres el `tournamentId` correcto, configura `.env` así:

```env
ODDSPAPI_USE_TOURNAMENTS=1
ODDSPAPI_TOURNAMENT_IDS=ID_DEL_TORNEO
```

Después reinicia Flask y usa `Actualizar Cuotas Reales`.

Este flujo usa `/v4/odds-by-tournaments`, que es mejor para tu plan gratis porque trae cuotas por torneo en menos llamadas.

### Fallback sin torneos

Si `ODDSPAPI_USE_TOURNAMENTS=0`, la app usa el flujo documentado:

```text
/v4/fixtures -> /v4/odds?fixtureId=...
```

Ese modo puede consumir más requests porque cada fixture consultado para cuotas usa una llamada adicional. Controla el límite con:

```env
ODDSPAPI_FIXTURE_DAYS=2
ODDSPAPI_MAX_FIXTURES=3
```

### 3. Verificar cuenta y cuota

Este endpoint consulta tu cuenta sin mostrar la API key:

```text
http://127.0.0.1:5000/api/account
```

### 4. Actualizar cuotas reales

Desde el dashboard usa el botón `Actualizar Cuotas Reales`, o ejecuta una petición POST a:

```text
http://127.0.0.1:5000/api/refresh
```

Cada actualización consume requests de OddsPapi. Con plan gratis, evita refrescar muchas veces.

### 5. Ver resultados

Después de actualizar:

```text
http://127.0.0.1:5000/api/events
http://127.0.0.1:5000/api/opportunities
http://127.0.0.1:5000/api/surebets
```

También puedes abrir la vista HTML de cuotas recibidas:

```text
http://127.0.0.1:5000/odds
```

Esta página muestra los eventos y bookmakers guardados aunque todavía no exista una surebet. Es la primera página que debes revisar después de usar `Actualizar Cuotas Reales`.

### 6. Diagnóstico si consume requests pero no ves eventos

Si OddsPapi descuenta requests pero el dashboard no cambia, revisa:

```text
http://127.0.0.1:5000/api/provider/status
```

Campos útiles:

```text
raw_fixtures_received    cantidad de fixtures recibidos desde OddsPapi
normalized_events        cantidad de eventos convertidos al formato interno
discard_reasons          motivos por los que se descartaron mercados
sample_markets           muestra de mercados y etiquetas recibidas
```

En modo API, si una actualización no normaliza eventos, la app limpia el snapshot anterior para que no sigas viendo datos demo viejos.

La aplicación solo analiza y muestra oportunidades. No realiza apuestas automáticamente.

---

## Ejecución de Pruebas Unitarias

Para ejecutar toda la suite de pruebas automatizadas con `pytest`:

```bash
pytest -q
```

---

## Exención de Responsabilidad

*Los cálculos son estimaciones matemáticas. Las cuotas pueden cambiar, existir límites de apuesta y variar las reglas de liquidación de cada operador.*
