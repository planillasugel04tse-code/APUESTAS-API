# Betano Live Analyzer

Analizador local de fútbol orientado a comparar pronósticos, cuotas, probabilidades, movimiento de mercado y resultados históricos.

## Surebet
- Detecta arbitrajes Pre-Match y Live a partir de cuotas almacenadas.
- Live se refresca bajo demanda para evitar consultas innecesarias.
- Permite verificar una sola coincidencia antes de tratar una surebet como confirmada.
- Calcula margen de arbitraje y distribución matemática del stake mediante `betano_analyzer.stake.allocate_stakes`.
- Rechaza cuotas inválidas y combinaciones que no constituyen arbitraje.

## Qué hace
- Registra partidos, tipsters, picks, cuotas y apuestas reales.
- Conserva el pick original y su transformación conservadora como estrategias separadas.
- Compara cuotas entre casas y calcula probabilidad implícita, fair probability, edge y EV.
- Sigue movimiento de cuotas y registra CLV.
- Construye Radar Maestro y Selector Final.
- Backtestea original vs conservador vs apuesta real.
- Incluye dashboard web local en `/` y documentación OpenAPI automática.
- No realiza apuestas ni inicia sesión en casas de apuestas.

## Endpoints principales
- `GET /api/v1/arbitrage/pre-match`
- `POST /api/v1/arbitrage/live`
- `POST /api/v1/arbitrage/verify/{match_id}`
- `GET /api/v1/opportunities?limit=20`
- `GET /api/v1/value-radar?limit=20`
- `GET /api/v1/master-radar?limit=20`
- `GET /api/v1/final-selection?limit=10`
- `GET /api/v1/movements`
- `GET /api/v1/clv/summary?period=hoy`
- `GET /api/v1/backtest/report?period=todos`
- `GET /api/v1/providers`
- `POST /api/v1/sync/odds?bookmakers=Betano&include_live=false`

## Fuentes externas
Los proveedores están preparados mediante adaptadores y configuración. Permanecen sujetos a credenciales/configuración autorizada. El sistema no utiliza credenciales de Betano ni intenta entrar en una cuenta de usuario.

## Desarrollo
Python 3.13 + FastAPI + SQLite. La arquitectura separa API, dominio, persistencia, proveedores, ingestión, radar y backtesting.
