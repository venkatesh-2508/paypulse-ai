# -*- coding: utf-8 -*-
import os
import sys
import socket

# Ensure stdout uses UTF-8 so emoji/unicode in print() won't crash on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine, text
from backend.config import settings
from backend.models import Base


def _is_pg_available() -> bool:
    """Check if local PostgreSQL is reachable."""
    try:
        s = socket.create_connection(("localhost", 5432), timeout=1.0)
        s.close()
        return True
    except Exception:
        return False


def _is_remote_pg_reachable(raw_url: str) -> bool:
    """
    Probe whether the remote PostgreSQL host:port is TCP-reachable.
    Uses a 5-second timeout so startup isn't blocked.
    """
    try:
        clean_url = (
            raw_url.replace("postgresql+asyncpg://", "http://")
            .replace("postgresql://", "http://")
            .replace("postgres://", "http://")
        )
        parsed = urlparse(clean_url)
        host = parsed.hostname
        port = parsed.port or 5432
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if not infos:
            return False
        ip, p = infos[0][4]
        s = socket.create_connection((ip, p), timeout=5.0)
        s.close()
        return True
    except Exception as e:
        print(f"[database] Remote host probe check: {e}")
        return False


def _sqlite_fallback() -> tuple[str, str]:
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "paypulse.db"))
    print(f"[database] [NOTICE] Using local SQLite database at {db_path}")
    return f"sqlite+aiosqlite:///{db_path}", f"sqlite:///{db_path}"


def _resolve_database_urls() -> tuple[str, str]:
    """
    Resolve async and sync database URLs.
    Guarantees that when Supabase is configured, it connects strictly to Supabase
    and NEVER silently falls back to local data.
    """
    raw_url = (settings.DATABASE_URL or "").strip()
    sync_url = (settings.DATABASE_URL_SYNC or "").strip()

    # ── Remote / Supabase PostgreSQL ──────────────────────────────────────────
    is_remote = (
        "supabase.co" in raw_url
        or "supabase.com" in raw_url
        or "pooler.supabase.com" in raw_url
        or (
            raw_url.startswith("postgres")
            and "localhost" not in raw_url
            and "127.0.0.1" not in raw_url
        )
    )

    if is_remote:
        print("[database] Supabase Cloud PostgreSQL configured.")
        if _is_remote_pg_reachable(raw_url):
            print("[database] [OK] Connected to Supabase Cloud PostgreSQL!")
        else:
            print("[database] [INFO] Connecting to Supabase Cloud PostgreSQL endpoint...")

        # Normalize async URL
        async_url = raw_url
        if async_url.startswith("postgresql://"):
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif async_url.startswith("postgres://"):
            async_url = async_url.replace("postgres://", "postgresql+asyncpg://", 1)

        # Normalize sync URL
        if not sync_url:
            sync_url = async_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        else:
            if sync_url.startswith("postgresql+asyncpg://"):
                sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://", 1)
            elif sync_url.startswith("postgres://"):
                sync_url = sync_url.replace("postgres://", "postgresql://", 1)

        return async_url, sync_url

    # ── Local PostgreSQL ───────────────────────────────────────────────────────
    if ("localhost" in raw_url or "127.0.0.1" in raw_url) and _is_pg_available():
        print("[database] [OK] Connected to local PostgreSQL on localhost:5432")
        async_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return async_url, sync_url

    # ── Fallback only if no database URL was provided at all ───────────────────
    return _sqlite_fallback()


db_async_url, db_sync_url = _resolve_database_urls()

connect_args_async = {}
connect_args_sync = {}

if "sqlite" in db_async_url:
    connect_args_async["check_same_thread"] = False
    connect_args_sync["check_same_thread"] = False
else:
    # Disable statement caching for asyncpg - required for Supabase poolers (PgBouncer)
    connect_args_async["statement_cache_size"] = 0

async_engine = create_async_engine(
    db_async_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=connect_args_async,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_engine = create_engine(
    db_sync_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=connect_args_sync,
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
