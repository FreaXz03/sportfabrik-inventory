import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Container settings; URL.create preserves special password characters.
if os.getenv("DB_HOST"):
    if not os.getenv("DB_PASSWORD"):
        raise RuntimeError("DB_PASSWORD fehlt für die Serverdatenbank.")
    DATABASE_URL = URL.create(
        "postgresql+psycopg",
        username=os.getenv("DB_USER", "inventory"),
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "inventory_db"),
    )

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL wurde nicht gefunden.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass
