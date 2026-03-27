import asyncio
import sys
sys.path.insert(0, r'C:\yomanit\backend')
import os
os.environ['PYTHONUTF8'] = '1'

# Simulate what happens during upload
import databases

DATABASE_URL = "postgresql://yomanit:secret@localhost:5432/yomanit"
db = databases.Database(DATABASE_URL)

async def test_lookup():
    await db.connect()
    print("Connected!")
    
    # Test the exact query from upload.py
    result = await db.fetch_one(
        """SELECT i.account_code, i.connection_name
           FROM   indexes i
           JOIN   templates t ON t.id = i.template_id
           WHERE  i.municipality_id = :muni
             AND  t.name            = :tmpl
             AND  i.key_value       = :key
             AND  i.active          = TRUE""",
        values={"muni": "6e6312e8-fe5d-40f5-854c-3e8feb9f8764", 
                "tmpl": "bezeq", 
                "key": "08-6103877"}
    )
    print("Lookup result:", result)
    await db.disconnect()
    print("Done!")

asyncio.run(test_lookup())
