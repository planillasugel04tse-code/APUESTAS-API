import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class Config:
    """Application Configuration Settings"""
    BASE_DIR: Path = BASE_DIR
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "1") == "1"
    PORT: int = int(os.getenv("PORT", 5000))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "betting-analyzer-secret-key")
    
    # Mode: DEMO or API
    PROVIDER_MODE: str = os.getenv("PROVIDER_MODE", "DEMO").upper()
    
    # SQLite Database
    DATABASE_PATH: str = str(BASE_DIR / os.getenv("DATABASE_PATH", "betting_analyzer.db"))
    
    # Sample data paths
    SAMPLE_ODDS_PATH: Path = BASE_DIR / "data" / "sample_odds.json"
    HISTORICAL_MATCHES_PATH: Path = BASE_DIR / "data" / "historical_matches.json"
    
    # External API Settings (Isolated)
    EXTERNAL_API_KEY: str = os.getenv("EXTERNAL_API_KEY", "")
    EXTERNAL_API_URL: str = os.getenv("EXTERNAL_API_URL", "https://api.oddspapi.io/v4")

    # OddsPapi Settings
    ODDSPAPI_SPORT_ID: int = int(os.getenv("ODDSPAPI_SPORT_ID", "10"))
    ODDSPAPI_LANGUAGE: str = os.getenv("ODDSPAPI_LANGUAGE", "es")
    ODDSPAPI_ODDS_FORMAT: str = os.getenv("ODDSPAPI_ODDS_FORMAT", "decimal")
    ODDSPAPI_BOOKMAKERS: str = os.getenv(
        "ODDSPAPI_BOOKMAKERS",
        "apuestatotal,betano.pe,inkabet,pinnacle"
    )
    ODDSPAPI_USE_TOURNAMENTS: bool = os.getenv("ODDSPAPI_USE_TOURNAMENTS", "0") == "1"
    ODDSPAPI_TOURNAMENT_IDS: str = os.getenv("ODDSPAPI_TOURNAMENT_IDS", "")
    ODDSPAPI_FIXTURE_DAYS: int = int(os.getenv("ODDSPAPI_FIXTURE_DAYS", "2"))
    ODDSPAPI_MAX_FIXTURES: int = int(os.getenv("ODDSPAPI_MAX_FIXTURES", "3"))

config = Config()
