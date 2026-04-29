"""Shared fixtures for admin tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
import sqlite3

import pytest
from sqlalchemy.orm import Mapped, mapped_column

from pylar_admin.config import AdminConfig
from pylar_admin.registry import AdminRegistry
from pylar.database import ConnectionManager, DatabaseConfig, Model, use_session


class Article(Model):
    __tablename__ = "admin_test_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    body: Mapped[str]
    published: Mapped[bool] = mapped_column(default=False)


class Tag(Model):
    __tablename__ = "admin_test_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


@pytest.fixture
def admin_config() -> AdminConfig:
    return AdminConfig(prefix="/admin", per_page=10, require_auth=False)


@pytest.fixture
def registry() -> AdminRegistry:
    return AdminRegistry()


@pytest.fixture
async def db_manager(tmp_path: Path) -> ConnectionManager:
    db_path = tmp_path / "admin-tests.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE admin_test_articles (
                id INTEGER PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                body TEXT NOT NULL,
                published BOOLEAN NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE admin_test_tags (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE
            )
            """
        )
        conn.commit()
    config = DatabaseConfig(url=f"sqlite+aiosqlite:///{db_path}", echo=False)
    mgr = ConnectionManager(config)
    await mgr.initialize()
    return mgr


@pytest.fixture
async def db_session(db_manager: ConnectionManager) -> AsyncIterator[None]:
    async with use_session(db_manager) as sess:
        sess.add_all([
            Article(title="First Post", body="Hello world", published=True),
            Article(title="Draft", body="Not ready", published=False),
            Tag(name="python"),
            Tag(name="async"),
        ])
        await sess.commit()
        yield
