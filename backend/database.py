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
    Uses a 5-second timeout so startup isn't blocked too long.
    """
    try:
        parsed = urlparse(raw_url)
        host = parsed.hostname
        port = parsed.port or 5432
        # Force IPv4 resolution to avoid IPv6 issues on some Windows machines
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if not infos:
            return False
        ip, p = infos[0][4]
        s = socket.create_connection((ip, p), timeout=5.0)
        s.close()
        return True
    except Exception as e:
        print(f"[database] Remote host probe failed: {e}")
        return False


def _sqlite_fallback() -> tuple[str, str]:
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "paypulse.db"))
    print(f"[database] [WARN] Falling back to local SQLite database at {db_path}")
    return f"sqlite+aiosqlite:///{db_path}", f"sqlite:///{db_path}"


def _resolve_database_urls() -> tuple[str, str]:
    """
    Resolve async and sync database URLs with real connectivity probing.

    Priority:
      1. Supabase / remote PostgreSQL (if URL configured AND reachable via IPv4 TCP)
      2. Local PostgreSQL on localhost:5432
      3. SQLite fallback (paypulse.db)
    """
    raw_url = settings.DATABASE_URL or ""

    # ── Remote / Supabase PostgreSQL ──────────────────────────────────────────
    is_remote = (
        "supabase.co" in raw_url
        or "supabase.com" in raw_url
        or (
            raw_url.startswith("postgresql")
            and "localhost" not in raw_url
            and "127.0.0.1" not in raw_url
        )
    )

    if is_remote:
        print("[database] Remote PostgreSQL URL detected -- probing connectivity...")
        if _is_remote_pg_reachable(raw_url):
            async_url = (
                raw_url
                .replace("postgresql://", "postgresql+asyncpg://")
                .replace("postgres://", "postgresql+asyncpg://")
            )
            sync_url = (
                raw_url
                .replace("postgresql+asyncpg://", "postgresql://")
                .replace("postgres://", "postgresql://")
            )
            print("[database] [OK] Supabase / Remote PostgreSQL is reachable")
            return async_url, sync_url
        else:
            print("[database] [FAIL] Supabase / Remote PostgreSQL is NOT reachable (DNS/network issue)")
            print("[database]    Tip: Check your DATABASE_URL in backend/.env and ensure the host is reachable.")

    # ── Local PostgreSQL ───────────────────────────────────────────────────────
    if _is_pg_available():
        print("[database] [OK] Connected to local PostgreSQL on localhost:5432")
        return settings.DATABASE_URL, settings.DATABASE_URL_SYNC

    # ── SQLite fallback ────────────────────────────────────────────────────────
    return _sqlite_fallback()


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
