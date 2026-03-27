# db.py - Direct asyncpg connection pool
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://yomanit:secret@localhost:5432/yomanit")
_pool = None

async def connect():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    print("DB pool created!", flush=True)

async def disconnect():
    global _pool
    if _pool:
        await _pool.close()

async def fetch_one(query: str, values: dict = None):
    async with _pool.acquire() as conn:
        # Convert :param style to $1 style
        q, args = _convert_query(query, values)
        row = await conn.fetchrow(q, *args)
        return dict(row) if row else None

async def fetch_all(query: str, values: dict = None):
    async with _pool.acquire() as conn:
        q, args = _convert_query(query, values)
        rows = await conn.fetch(q, *args)
        return [dict(r) for r in rows]

async def execute(query: str, values: dict = None):
    async with _pool.acquire() as conn:
        q, args = _convert_query(query, values)
        return await conn.execute(q, *args)

class Transaction:
    def __init__(self):
        self._conn = None
        self._tr = None

    async def __aenter__(self):
        self._conn = await _pool.acquire()
        self._tr = self._conn.transaction()
        await self._tr.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            await self._tr.rollback()
        else:
            await self._tr.commit()
        await _pool.release(self._conn)

def transaction():
    return Transaction()

def _convert_query(query: str, values: dict = None):
    if not values:
        return query, []
    args = []
    result = query
    i = 1
    for key, val in values.items():
        result = result.replace(f":{key}", f"${i}")
        args.append(val)
        i += 1
    return result, args
