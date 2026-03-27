import asyncio, db

async def run():
    await db.connect()
    print("Connected...")

    await db.execute("ALTER TABLE indexes DROP CONSTRAINT IF EXISTS indexes_municipality_id_template_id_key_value_key", {})
    print("Dropped constraint 1")

    await db.execute("ALTER TABLE indexes DROP CONSTRAINT IF EXISTS indexes_municipality_id_template_id_key_value_unique", {})
    print("Dropped constraint 2")

    await db.execute("ALTER TABLE indexes ADD CONSTRAINT indexes_unique_split UNIQUE (municipality_id, template_id, key_value, account_code)", {})
    print("Added new constraint!")

    await db.disconnect()
    print("Done!")

asyncio.run(run())
