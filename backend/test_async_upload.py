import asyncio
import sys
import os
os.environ['PYTHONUTF8'] = '1'

async def main():
    import databases
    db = databases.Database('postgresql://yomanit:secret@localhost:5432/yomanit')
    await db.connect()
    
    # Test lookup
    row = await db.fetch_one(
        "SELECT id FROM templates WHERE name = 'bezeq'"
    )
    print("Template:", row)
    
    await db.disconnect()
    print("All OK!")

asyncio.run(main())
