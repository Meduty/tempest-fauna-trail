"""Root conftest — loads .env before any test session so OPENWEATHER_API_KEY
and other local secrets are available without being exported in the shell."""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
