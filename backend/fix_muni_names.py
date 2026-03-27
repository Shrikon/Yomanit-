import asyncio, asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://yomanit:secret@localhost:5432/yomanit")
    # Update all municipality names to proper Hebrew
    updates = [
        ("MIT", "מ.מ מיתר"),
        ("TLV", "עיריית תל אביב"),
        ("GAL", "מועצה אזורית גליל"),
        ("HFA", "עיריית חיפה"),
        ("YOK", "מועצה מקומית יוקנעם"),
        ("BEV", "עיריית באר שבע"),
        ("NET", "עיריית נתניה"),
    ]
    for code, name in updates:
        await conn.execute("UPDATE municipalities SET name=$1 WHERE code=$2", name, code)
        print(f"Updated {code} -> {name}")
    await conn.close()

asyncio.run(main())
