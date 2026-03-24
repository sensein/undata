"""Shared pytest fixtures for the undata backend tests."""

import os

import pytest

# Use test database URL
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://undata:undata@localhost:5432/undata_test",
)
