import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://yomanit:secret@localhost:5432/yomanit")
    await conn.execute("UPDATE municipalities SET name = $1 WHERE code = 'DIM'", "עיריית דימונה")
    row = await conn.fetchrow("SELECT id, name FROM municipalities WHERE code = 'DIM'")
    print("ID:", row["id"])
    print("Name:", row["name"])
    await conn.close()

asyncio.run(main())
