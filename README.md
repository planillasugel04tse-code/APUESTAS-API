# Betano Live Analyzer

Analizador local de fútbol orientado a comparar pronósticos, cuotas y probabilidades.

## Objetivo inicial
- Registrar partidos, tipsters, pronósticos y cuotas.
- Guardar el pronóstico original y cualquier versión conservadora por separado.
- Comparar consenso entre fuentes y detectar oportunidades futuras cuando existen datos suficientes.
- Registrar las apuestas reales del usuario y su liquidación para construir histórico y backtesting.
- Calcular probabilidad implícita, edge, ROI, hit rate y rendimiento por periodo.
- Preparar una arquitectura extensible para incorporar múltiples fuentes de cuotas y pronósticos.
- No realiza apuestas ni inicia sesión en casas de apuestas.

## Radar
`GET /api/v1/opportunities?limit=20` genera un radar de próximos partidos programados. Usa únicamente picks que tengan confianza y cuota disponibles, busca la mejor cuota registrada entre las casas cargadas y agrupa el consenso por mercado/selección. El rating es un filtro inicial, no una garantía de rentabilidad.

El sistema no inventa una probabilidad de modelo cuando falta una confianza explícita. La siguiente etapa será alimentar esa confianza con modelos estadísticos y fuentes externas y después calibrarla con resultados históricos.

## Datos que se pueden cargar
- `POST /api/v1/matches`
- `POST /api/v1/tipsters`
- `POST /api/v1/picks`
- `POST /api/v1/odds`
- `POST /api/v1/bets`
- `PATCH /api/v1/bets/{bet_id}/settle`
- `GET /api/v1/bets/summary?period=hoy|lunes-viernes|sabado-domingo|mes|3-meses|6-meses|todos`

## Desarrollo
Python + FastAPI + SQLite en la primera etapa. FastAPI proporciona documentación interactiva y `TestClient` permite probar la API sin levantar un servidor HTTP real. SQLite se usa inicialmente porque es una base de datos de un solo archivo y luego puede sustituirse por PostgreSQL si el proyecto crece.

## Próxima capa
1. Conectores de cuotas externas.
2. Importador de picks de tipsters/fuentes autorizadas.
3. Normalización de mercados y equipos.
4. Historial de resultados por tipster, liga y mercado.
5. Modelos de probabilidad y calibración.
6. Backtesting: pick original vs versión conservadora vs apuesta real.
7. Radar final con prioridad por seguridad, edge y estabilidad; sin forzar 10 picks si no existen 10 candidatos de calidad.
