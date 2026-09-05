"""Async SQLAlchemy database setup and session management."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import uuid6
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base with naming convention for constraints.

    This naming convention ensures Alembic autogenerate produces stable,
    greppable constraint names (e.g., idx_table_col instead of ix_table_col_1).
    """

    naming_convention = {
        "ix": "idx_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


class TimestampMixin:
    """Mixin for models that need created_at and updated_at timestamps.

    Provides server-side defaults and automatic updates.
    """

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class UUIDPrimaryKey:
    """Mixin for models using UUIDv7 as primary key."""

    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=lambda: str(uuid6.uuid7()),
        nullable=False,
    )


def get_engine() -> AsyncEngine:
    """Create async SQLAlchemy engine from settings.

    Returns:
        Async engine instance.
    """
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.environment == "local",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    The session is committed on clean exit and rolled back on exception.
    Always closes after the request.

    Yields:
        An AsyncSession instance.

    Raises:
        Any database exception that occurs during the request.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=settings.environment == "local",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            await engine.dispose()


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Returns:
        Configured async_sessionmaker for creating sessions.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=settings.environment == "local",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
