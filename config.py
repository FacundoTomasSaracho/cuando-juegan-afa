"""Configuración central de PromiScraper."""
import os
from dataclasses import dataclass, field
from pathlib import Path

import pytz
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"

ARGENTINA_TZ = pytz.timezone("America/Argentina/Buenos_Aires")

LIGA_PROFESIONAL_ID = "hc"
LIGA_PROFESIONAL_NAME = "Liga Profesional Argentina"

PROMIEDOS_URL = "https://www.promiedos.com.ar"

DAILY_TWEET_HOUR = 12
DAILY_TWEET_MINUTE = 0
PRE_MATCH_MINUTES_BEFORE = 10

TWEET_MAX_CHARS = 280

STOPWORDS_HASHTAG = {"de", "del", "la", "los", "las", "y", "el", "a", "e"}


@dataclass
class Config:
    # Twitter credentials (OAuth 1.0a — los 4 son obligatorios para publicar)
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_secret: str = ""

    # Behaviour
    dry_run: bool = True
    log_dir: Path = field(default_factory=lambda: LOG_DIR)

    @classmethod
    def from_env(cls) -> "Config":
        api_key = os.getenv("TWITTER_API_KEY", "")
        api_secret = os.getenv("TWITTER_API_SECRET", "")
        access_token = os.getenv("TWITTER_ACCESS_TOKEN", "")
        access_secret = os.getenv("TWITTER_ACCESS_SECRET", "")

        # Dry-run si falta cualquiera de los 4 campos
        dry_run = not all([api_key, api_secret, access_token, access_secret])

        return cls(
            api_key=api_key,
            api_secret=api_secret,
            access_token=access_token,
            access_secret=access_secret,
            dry_run=dry_run,
        )
