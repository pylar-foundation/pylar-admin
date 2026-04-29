"""Tests for admin auth password storage and lookup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pylar.auth.hashing import Pbkdf2PasswordHasher


@pytest.fixture
def hasher() -> Pbkdf2PasswordHasher:
    return Pbkdf2PasswordHasher()


@pytest.fixture
def auth_db(tmp_path: Path, hasher: Pbkdf2PasswordHasher) -> Path:
    db_path = tmp_path / "admin-auth-tests.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE test_users (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT 0,
                email_verified_at DATETIME NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO test_users (name, email, password_hash, is_admin)
            VALUES (?, ?, ?, ?)
            """,
            (
                "Admin",
                "admin@example.com",
                hasher.hash("admin@example.com"),
                True,
            ),
        )
        conn.commit()
    return db_path


class TestLoginFlow:
    def test_hash_verify_roundtrip(self, hasher: Pbkdf2PasswordHasher) -> None:
        hashed = hasher.hash("admin@example.com")
        assert hasher.verify("admin@example.com", hashed)
        assert not hasher.verify("wrong", hashed)

    def test_user_query_by_email(self, auth_db: Path) -> None:
        with sqlite3.connect(auth_db) as conn:
            row = conn.execute(
                "SELECT email FROM test_users WHERE email = ?",
                ("admin@example.com",),
            ).fetchone()
        assert row is not None
        assert row[0] == "admin@example.com"

    def test_password_matches_after_db_roundtrip(
        self,
        auth_db: Path,
        hasher: Pbkdf2PasswordHasher,
    ) -> None:
        with sqlite3.connect(auth_db) as conn:
            row = conn.execute(
                "SELECT password_hash FROM test_users WHERE email = ?",
                ("admin@example.com",),
            ).fetchone()
        assert row is not None
        assert hasher.verify("admin@example.com", row[0])
