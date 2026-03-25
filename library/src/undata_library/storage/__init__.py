"""Storage abstraction layer for undata-library.

Provides a StorageBackend protocol and implementations for
persisting entities to different backends (files, databases, etc.).
"""

from .file_backend import FileBackend
from .mock_backend import MockBackend
from .protocol import EntityStore, FlagStore, RunStore, StorageBackend

__all__ = [
    "EntityStore",
    "FileBackend",
    "FlagStore",
    "MockBackend",
    "RunStore",
    "StorageBackend",
]
