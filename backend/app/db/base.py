from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# Motorn stödjer SQLite (aiosqlite) och Postgres (asyncpg) via DATABASE_URL
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI-dependency som ger en databasession per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Skapa alla tabeller om de inte finns. Ersätts av Alembic-migrationer senare."""
    async with engine.begin() as conn:
        from app.db.models import meeting, transcript, segment, speaker_profile  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
