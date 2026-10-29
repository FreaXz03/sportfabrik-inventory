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


def engine_argumente(url) -> dict:
    """Pool und Zeitlimits für mehrere gleichzeitige Benutzer: eine hängende
    Anfrage soll nicht alle anderen blockieren. Grosse Importe brauchen bis zu
    einige zehn Sekunden, deshalb großzügige Limits (Millisekunden)."""
    argumente: dict = {"pool_pre_ping": True}
    if str(url).startswith("postgresql"):
        argumente.update(
            pool_size=10,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            connect_args={
                "options": "-c statement_timeout=120000"
                " -c lock_timeout=60000"
                " -c idle_in_transaction_session_timeout=300000"
            },
        )
    return argumente


engine = create_engine(DATABASE_URL, **engine_argumente(DATABASE_URL))

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_session():
    with SessionLocal() as session:
        yield session
