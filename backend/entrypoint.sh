#!/bin/sh
set -e

echo "Creating database tables..."
python -c "
import asyncio
from src.db.session import engine, Base
from src.db import models  # noqa: F401

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

asyncio.run(init())
"

echo "Checking if seed data needed..."
python -c "
import asyncio
import os
from pathlib import Path
from src.db.session import engine, AsyncSessionLocal
from src.db.models import Element
from sqlalchemy import select, func

SEED_DIR = Path(os.environ.get('UNDATA_SEED_DIR', '/app/backend/seed'))

async def check_and_seed():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count()).select_from(Element))
        count = result.scalar()
        if count == 0 and SEED_DIR.exists() and any(SEED_DIR.iterdir()):
            print('Database empty — importing seed data...')
            from src.services.import_service import import_registry
            stats = await import_registry(session, SEED_DIR, clear_existing=False)
            await session.commit()
            print(f'Seeded: {stats}')
        elif count == 0:
            print('Database empty — no seed data found (seed/ dir empty or missing)')
        else:
            print(f'Database has {count} elements — skipping seed')
    await engine.dispose()

asyncio.run(check_and_seed())
"

echo "Starting backend..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8002 --reload
