#!/usr/bin/env python3
"""Initialize database tables and optionally import a registry.

Usage:
    python scripts/init_db.py                          # Just create tables
    python scripts/init_db.py /tmp/undata-027-final    # Create + import registry
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from src.db.session import Base, engine
    from src.models.db import (  # noqa: F401 — import to register models
        Contribution,
        CurationFlag,
        Element,
        RunSummary,
        Schema,
        UserProfile,
        Value,
        ValueSet,
    )

    # Drop and recreate all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created.")

    # Import registry if path provided
    if len(sys.argv) > 1:
        registry_dir = Path(sys.argv[1])
        if not registry_dir.exists():
            print(f"Registry not found: {registry_dir}")
            return

        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from src.services.import_service import import_registry

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            async with session.begin():
                stats = await import_registry(session, registry_dir)
                await session.commit()
        print(f"Import complete: {stats}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
