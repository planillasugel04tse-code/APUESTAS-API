import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class ParsedTelegramPick:
    home_team: str
    away_team: str
    competition: str
    market: str
    selection: str
    odds: float
    stake: float
    confidence: float
    tipster: str
    channel: str
    raw_text: str
    is_valid: bool = True
    error_reason: Optional[str] = None

def _clean_team_name(name: str) -> str:
    """Clean noise words, emojis, and prefixes from team names."""
    cleaned = re.sub(r'[𐀀-􏿿☀-➿⌀-⏿🌀-🧿]', ' ', name)
    cleaned = re.sub(r'^(?:uefa|champions|league|liga|copa|libertadores|sudamericana|partido|match|reto|stake\s*\d+)?\s*', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+(?:cuota|odds|momio|stake|gana|over|under|ambos|entrada|de|oro|@).*$', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def parse_telegram_message(
    text: str,
    channel: str = '@TeleBetChannel',
    tipster: Optional[str] = None
) -> ParsedTelegramPick:
    """Parse raw Telegram message text to extract structured pick data."""
    raw = text.strip()
    if not raw:
        return ParsedTelegramPick(
            home_team='', away_team='', competition='', market='', selection='',
            odds=0.0, stake=0.0, confidence=0.0, tipster=tipster or channel,
            channel=channel, raw_text=raw, is_valid=False, error_reason='Mensaje vacío'
        )

    # 1. Match teams
    match_patterns = [
        r'([A-Za-z0-9\xc1\xc9\xcd\xd3\xda\xd1\xe1\xe9\xed\xf3\xfa\xf1\s\.-]+)\s+(?:vs\.?|versus|-|contra)\s+([A-Za-z0-9\xc1\xc9\xcd\xd3\xda\xd1\xe1\xe9\xed\xf3\xfa\xf1\s\.-]+)',
        r'(?:partido|match)\s*:\s*([A-Za-z0-9\xc1\xc9\xcd\xd3\xda\xd1\xe1\xe9\xed\xf3\xfa\xf1\s\.-]+)\s*-\s*([A-Za-z0-9\xc1\xc9\xcd\xd3\xda\xd1\xe1\xe9\xed\xf3\xfa\xf1\s\.-]+)',
    ]

    home_team, away_team = '', ''
    for pattern in match_patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            h = match.group(1).strip()
            a = match.group(2).strip()
            home_team = _clean_team_name(h.split(chr(10))[-1])
            away_team = _clean_team_name(a.split(chr(10))[0])
            if home_team and away_team:
                break

    if not home_team or not away_team:
        lines = [line.strip() for line in raw.split(chr(10)) if line.strip()]
        for line in lines:
            parts = re.split(r'\s+(?:vs\.?|versus|-|contra)\s+', line, flags=re.IGNORECASE)
            if len(parts) == 2:
                home_team = _clean_team_name(parts[0])
                away_team = _clean_team_name(parts[1])
                if home_team and away_team:
                    break

    if not home_team or not away_team:
        return ParsedTelegramPick(
            home_team='', away_team='', competition='', market='', selection='',
            odds=0.0, stake=0.0, confidence=0.0, tipster=tipster or channel,
            channel=channel, raw_text=raw, is_valid=False,
            error_reason='No se pudieron identificar los equipos en el mensaje'
        )

    # 2. Extract Competition
    comp_match = re.search(r'(?:liga|league|torneo|copa|competicion|competición)\s*:\s*([^\n]+)', raw, re.IGNORECASE)
    competition = comp_match.group(1).strip() if comp_match else 'Liga 1 Peru'

    # 3. Extract Odds (supports @1.85, 💰1.62, 📈1.60, 💵1.62, cuota: 1.95, odds 2.05, or standalone float)
    odds_match = re.search(r'(?:cuota|odds|momio|@|💰|📈|💵)\s*:?\s*(\d+(?:\.\d+)?)', raw, re.IGNORECASE)
    if not odds_match:
        odds_match = re.search(r'@\s*(\d+(?:\.\d+)?)', raw)
    if not odds_match:
        for m in re.finditer(r'\b(\d+\.\d{1,2})\b', raw):
            try:
                val = float(m.group(1))
                if 1.01 <= val <= 100.0:
                    odds_match = m
                    break
            except ValueError:
                pass

    odds = 0.0
    if odds_match:
        try:
            odds = float(odds_match.group(1))
        except ValueError:
            odds = 0.0

    if odds <= 1.0:
        return ParsedTelegramPick(
            home_team=home_team, away_team=away_team, competition=competition, market='', selection='',
            odds=0.0, stake=0.0, confidence=0.0, tipster=tipster or channel,
            channel=channel, raw_text=raw, is_valid=False,
            error_reason='Cuota inválida o no encontrada en el mensaje'
        )

    # 4. Extract Stake & Confidence
    stake = 1.0
    confidence = 0.70

    stake_match = re.search(r'(?:stake|unidades|stk)\s*:?\s*(\d+(?:\.\d+)?)(?:/10)?', raw, re.IGNORECASE)
    if stake_match:
        try:
            stake = float(stake_match.group(1))
            confidence = min(1.0, max(0.1, stake / 10.0))
        except ValueError:
            stake = 1.0

    # 5. Extract Market & Selection
    market = '1x2'
    selection = '1'
    raw_lower = raw.lower()

    if 'ambos anotan' in raw_lower or 'ambos marcan' in raw_lower or 'btts' in raw_lower:
        market = 'btts'
        if re.search(r'\b(no|falso)\b', raw_lower):
            selection = 'No'
        else:
            selection = 'Yes'

    elif any(k in raw_lower for k in ['goles', 'total goals', 'over', 'under', 'más de', 'mas de', 'menos de']):
        market = 'goals'
        line_match = re.search(r'(\d+(?:\.5|\.0)?)', raw)
        line_val = line_match.group(1) if line_match else '2.5'
        if 'under' in raw_lower or 'menos de' in raw_lower:
            selection = f'Under {line_val}'
        else:
            selection = f'Over {line_val}'

    elif any(k in raw_lower for k in ['corner', 'córner', 'corners']):
        market = 'corners'
        line_match = re.search(r'(\d+(?:\.5|\.0)?)', raw)
        line_val = line_match.group(1) if line_match else '9.5'
        if 'under' in raw_lower or 'menos de' in raw_lower:
            selection = f'Under {line_val}'
        else:
            selection = f'Over {line_val}'

    elif any(k in raw_lower for k in ['tarjeta', 'tarjetas', 'card', 'cards']):
        market = 'cards'
        line_match = re.search(r'(\d+(?:\.5|\.0)?)', raw)
        line_val = line_match.group(1) if line_match else '4.5'
        if 'under' in raw_lower or 'menos de' in raw_lower:
            selection = f'Under {line_val}'
        else:
            selection = f'Over {line_val}'

    elif any(k in raw_lower for k in ['doble opcion', 'doble opción', 'doble oportunidad', '1x', 'x2', '12']):
        market = 'double_chance'
        if '1x' in raw_lower:
            selection = '1X'
        elif 'x2' in raw_lower:
            selection = 'X2'
        else:
            selection = '12'

    else:
        market = '1x2'
        if 'empate' in raw_lower or 'draw' in raw_lower:
            selection = 'X'
        elif 'visitante' in raw_lower or 'away' in raw_lower or 'gana visitante' in raw_lower:
            selection = '2'
        else:
            selection = '1'

    return ParsedTelegramPick(
        home_team=home_team,
        away_team=away_team,
        competition=competition,
        market=market,
        selection=selection,
        odds=odds,
        stake=stake,
        confidence=confidence,
        tipster=tipster or channel,
        channel=channel,
        raw_text=raw,
        is_valid=True,
        error_reason=None
    )
