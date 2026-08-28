import os
import socket
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from backend.config import settings
from backend.models import Base

def _is_pg_available() -> bool:
    try:
        s = socket.create_connection(("localhost", 5432), timeout=1.0)
        s.close()
        return True
    except Exception:
        return False

def _resolve_database_urls():
    """
    Resolve async and sync database URLs.
    Supports Supabase PostgreSQL, AWS RDS, local PostgreSQL, and SQLite fallback.
    """
    raw_url = settings.DATABASE_URL or ""

    # If Supabase or remote PostgreSQL URL is configured in .env
    if "supabase.co" in raw_url or (raw_url.startswith("postgresql") and not "localhost" in raw_url and not "127.0.0.1" in raw_url):
        # Format for asyncpg
        async_url = raw_url.replace("postgresql://", "postgresql+asyncpg://").replace("postgres://", "postgresql+asyncpg://")
        sync_url = raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace("postgres://", "postgresql+psycopg2://")
        print(f"[database] Connecting to Supabase / Remote PostgreSQL database")
        return async_url, sync_url

    # Check local PostgreSQL
    if _is_pg_available():
        print("[database] Connected to local PostgreSQL on localhost:5432")
        return settings.DATABASE_URL, settings.DATABASE_URL_SYNC

    # Fallback to local SQLite
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "paypulse.db"))
    print(f"[database] Using local SQLite database at {db_path}")
    return f"sqlite+aiosqlite:///{db_path}", f"sqlite:///{db_path}"


db_async_url, db_sync_url = _resolve_database_urls()

async_engine = create_async_engine(
    db_async_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in db_async_url else {}
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_engine = create_engine(
    db_sync_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in db_sync_url else {}
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
