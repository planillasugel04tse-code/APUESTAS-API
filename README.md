# Betano Live Analyzer

Analizador local de fútbol orientado a comparar pronósticos, cuotas, probabilidades, movimiento de mercado y resultados históricos.

## Qué hace
- Registra partidos, tipsters, picks, cuotas y apuestas reales.
- Conserva el pick original y su transformación conservadora como estrategias separadas.
- Compara cuotas entre casas y calcula probabilidad implícita, fair probability, edge y EV.
- Detecta oportunidades de arbitraje cuando la suma de probabilidades implícitas es menor que 1.
- Sigue movimiento de cuotas por partido, mercado, selección y línea.
- Registra CLV (Closing Line Value) por casa, mercado, selección y línea.
- Construye un Radar Maestro que combina valor, consenso, modelo disponible, movimiento, histórico, tipsters y CLV.
- Aplica un Selector Final que descarta candidatos débiles y no rellena cupos artificialmente.
- Backtestea por separado: **original vs conservador vs apuesta real**.
- Muestra rendimiento por periodo y por competición/mercado.
- Incluye dashboard web local en `/` y documentación OpenAPI automática.
- No realiza apuestas ni inicia sesión en casas de apuestas.

## Filosofía del sistema
La prioridad es **seguridad y calidad de señal antes que cuota**. Una cuota de alrededor de 1.50 puede ser preferible a una cuota 2.00 si la evidencia es claramente superior. Las transformaciones conservadoras buscan reducir riesgo (por ejemplo, local -> 1X y Over 2.5 -> Over 2).

El sistema no promete ganancias. Un `master_score` es un ranking de señales, no una probabilidad de acierto. CLV mide la calidad del precio conseguido frente al cierre y tampoco es una garantía de beneficio.

## Endpoints principales
### Datos
- `POST /api/v1/matches`
- `POST /api/v1/tipsters`
- `POST /api/v1/picks`
- `POST /api/v1/odds`
- `POST /api/v1/bets`
- `PATCH /api/v1/bets/{bet_id}/settle`
- `POST /api/v1/picks/{pick_id}/result?strategy=original|conservative`

### Análisis
- `GET /api/v1/opportunities?limit=20`
- `GET /api/v1/value-radar?limit=20`
- `GET /api/v1/master-radar?limit=20`
- `GET /api/v1/final-selection?limit=10`
- `GET /api/v1/arbitrage`
- `GET /api/v1/movements`
- `GET /api/v1/clv/summary?period=hoy`
- `POST /api/v1/clv`

### Histórico
- `GET /api/v1/backtest/report?period=todos`
- `GET /api/v1/bets/summary?period=todos`
- `GET /api/v1/tipsters/performance?period=todos`
- `GET /api/v1/performance/competition-market`

### Operación
- `GET /api/v1/providers`
- `POST /api/v1/sync/odds?bookmakers=Betano&include_live=false`
- `GET /health`
- `/` dashboard web local

## Backtest
El backtest nunca copia automáticamente el resultado de una estrategia a otra. Para cada pick se pueden registrar resultados independientes en `pick_strategy_results` para `original` y `conservative`. Las apuestas reales salen de la tabla `bets` y conservan su stake, cuota, resultado y cashout.

El reporte devuelve cobertura para saber cuántos picks tienen cada estrategia y cuántos están emparejados. Las muestras pequeñas deben considerarse insuficientes para sacar conclusiones.

## CLV
Para un snapshot se registra:
- casa de apuestas;
- mercado, selección y línea;
- cuota de entrada;
- cuota de cierre;
- CLV = `entry_odds / closing_odds - 1`.

El CLV es especialmente útil para evaluar si el sistema consigue mejores precios que el cierre. La línea se conserva para evitar comparar mercados asiáticos con líneas diferentes como si fueran el mismo mercado.

## Fuentes externas
Los proveedores de cuotas están preparados mediante adaptadores y configuración. Permanecen desactivados por defecto hasta disponer de credenciales/configuración autorizada. El sistema no utiliza credenciales de Betano ni intenta entrar en una cuenta de usuario.

## Desarrollo
Python 3.13 + FastAPI + SQLite. Los tests se ejecutan mediante GitHub Actions. La arquitectura separa API, dominio de análisis, persistencia, proveedores, ingestión, radar y backtesting para poder evolucionar hacia PostgreSQL y modelos estadísticos más avanzados sin rehacer el núcleo.

## Próxima evolución técnica
1. Alimentar el `probability` del pick con modelos estadísticos reproducibles.
2. Incorporar Dixon-Coles/Poisson + Elo + simulación Monte Carlo como baseline y calibrarlos con resultados históricos.
3. Normalizar equipos, ligas y mercados entre proveedores.
4. Añadir snapshots de cierre automáticos para CLV.
5. Integrar proveedores externos mediante sus APIs autorizadas.
6. Validar todo con backtesting fuera de muestra antes de usar dinero real.
