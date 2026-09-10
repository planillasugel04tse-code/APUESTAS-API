from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class BookmakerOdds(BaseModel):
    """Bookmaker information and market odds"""
    name: str
    country: Optional[str] = "Global"
    odds: Dict[str, float]

class Event(BaseModel):
    """Internal standardized Event Data Model"""
    event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    market: str
    timestamp: str
    bookmakers: List[BookmakerOdds]

class SurebetLeg(BaseModel):
    """Individual leg of a Surebet opportunity"""
    selection: str
    bookmaker: str
    odds: float
    stake_percentage: float
    stake_amount: float
    payout: float
    profit: float

class Opportunity(BaseModel):
    """Detected Betting Opportunity"""
    opportunity_id: str
    type: str  # 'surebet', 'valuebet', 'range'
    event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    market: str
    roi: float
    timestamp: str
    details: Dict[str, Any]

class CalculationRequest(BaseModel):
    """Stake and ROI calculation request"""
    bankroll: float = Field(gt=0, default=100.0)
    odds: List[float] = Field(min_length=1)
    type: str = "surebet"  # surebet, valuebet

class HistoricalMatch(BaseModel):
    """Historical match data for statistical modeling"""
    event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_corners: int
    away_corners: int
    home_yellow_cards: int
    away_yellow_cards: int
    date: str
