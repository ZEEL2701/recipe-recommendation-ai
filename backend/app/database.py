from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Render (and other deploys) often provide env vars differently than local `.env`.
    # Fall back to a local SQLite DB so the API can still boot.
    _SQLITE_PATH = Path(__file__).resolve().parents[1] / "data" / "recipes.db"
    DATABASE_URL = f"sqlite:///{_SQLITE_PATH.as_posix()}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit = False,
    autoflush = False,
    bind = engine
)