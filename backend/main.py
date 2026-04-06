# main.py – יומנית Backend
# FastAPI + PostgreSQL + pandas
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import db
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    # Verify critical dependencies at startup
    try:
        import xlrd
        print(f"[STARTUP] xlrd={xlrd.__version__}", flush=True)
    except ImportError as e:
        print(f"[STARTUP] WARNING: xlrd not installed: {e}", flush=True)
    yield
    await db.disconnect()
# backwards compat
class _DB:
    async def fetch_one(self, q, values=None): return await db.fetch_one(q, values)
    async def fetch_all(self, q, values=None): return await db.fetch_all(q, values)
    async def execute(self, q, values=None): return await db.execute(q, values)
    def transaction(self): return db.transaction()
database = _DB()
import logging
logging.basicConfig(level=logging.DEBUG)
from fastapi import Request
from fastapi.responses import JSONResponse
app = FastAPI(
    title="יומנית API",  # v2
    description="מערכת ניהול פקודות יומן לרשויות מקומיות",
    version="0.1.0",
    lifespan=lifespan,
)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    logging.error(f"UNHANDLED ERROR: {tb}")
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "traceback": tb[-1000:]},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yomanit.vercel.app",
        "https://www.yomanit.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
        "*",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- Routers ---
from routers import auth, municipalities, indexes, upload, journal, electricity, import_batches, export_events, index_exceptions, template_rules, welfare, celcom
app.include_router(auth.router,           prefix="/auth",           tags=["auth"])
app.include_router(municipalities.router, prefix="/municipalities",  tags=["municipalities"])
app.include_router(indexes.router,        prefix="/indexes",         tags=["indexes"])
app.include_router(upload.router,         prefix="/upload",          tags=["upload"])
app.include_router(journal.router,        prefix="/journal-entries", tags=["journal"])
app.include_router(electricity.router,    prefix="/upload/electricity", tags=["electricity"])
app.include_router(import_batches.router,    prefix="/import-batches",      tags=["import-batches"])
app.include_router(export_events.router,     prefix="/export-events",       tags=["export-events"])
app.include_router(index_exceptions.router,  prefix="/index-exceptions",    tags=["index-exceptions"])
app.include_router(template_rules.router,    prefix="/template-rules",      tags=["template-rules"])
app.include_router(welfare.router,           prefix="/upload/welfare",       tags=["welfare"])
app.include_router(celcom.router,            prefix="/celcom",               tags=["celcom"])
@app.get("/health")
async def health():
    return {"status": "ok", "service": "yomanit-api"}

@app.post("/run-setup/mitar-electricity")
async def run_setup_mitar_electricity():
    """One-time endpoint to load Mitar electricity indexes and rename municipality."""
    import uuid
    MITAR_ID = "bdb31b8e-8790-45ad-acdd-8c918876cbad"
    INDEXES = [
        ("342636355","1743000431","דרך מיתר 83"),("342582213","1727000431","שד עומרים מרכז מסחרי_ תחנ"),
        ("342477992","1743000431","עין מור ע\"י מס 47 מאור רח"),("342527628","1723000431","שקמה 36"),
        ("342584600","1743000431","דרך הבשור ליד 25 מאור רחו"),("342474982","1743000431","דרך מיתר ליד 90 מאור רחוב"),
        ("342583200","1723000431","ניצנה ע\"י מס 8 מקלט צ9 מק"),("342582341","1723000431","עופרים ע\"י מס 2 מקלט צ5 מ"),
        ("342506778","1723000431","שקמה ע\"י מס 12 מקלט מקלט"),("342378377","1743000431","קדש ברנע ליד מס 1 מאור רח"),
        ("342581927","1828200820","שד המייסדים עמ 242 מועדון"),("342623729","1743000431","בשמת 2"),
        ("342481761","1723000431","ממשית 30"),("342505446","1723000431","עופרים ליד 36 מקלט"),
        ("342478360","1743000431","מרגנית ע\"י מס 12 מאור רחו"),("342478823","1743000431","תמר ע\"י מס 7 מאור רחובות"),
        ("342585022","1723000431","גפן ע\"י מס 21 מקלט חניה 8"),("342476746","1743000431","דרך יתיר ע\"י מס 82 מאור ר"),
        ("342505848","1743000431","דרך מיתר ע\"י מרכז מסחרי ת"),("342606208","1723000431","עין מור 1א"),
        ("342233959","1841000431","בשמת 67"),("342584130","1743000431","שד עומרים עמ 231 סניף דאר"),
        ("342319799","1812300431","ניצנה 8"),("342521607","1723000431","תמנע 34א"),
        ("342574721","1743000431","_רימון אחרי 8 מאור רחובות"),("342663080","1844400431","זית 3"),
        ("342550454","1743000431","דרך הראל ע\"י 44 מאור רחוב"),("342583796","1723000431","כרכום ע\"י מס 6 מקלט מס 4"),
        ("342552410","1812300431","עין מור 1"),("342524099","1828200431","65/1136 BR שד המייסדים עמ"),
        ("342701645","1743000431","6*BR _דרך יתיר פינת חלמיש"),("342673440","1743000431","65/1136*R שד המייסדים עמ"),
        ("342685926","1743000431","R_שבטה ליד 32 מאור רחובות"),("342694802","1743000431","__צקלג אחרי 1 מאור רחובות"),
        ("342617478","1613000431","מחסני המועצ 86/1136 BR עמ"),("342711449","1812300431","גאון הירדן 43"),
        ("342609001","1743000431","R_שובל מול 73 מאור רחובות"),("342652917","1812300431","תמנע 11א"),
        ("342408757","1743000431","מ 22/1136 BR דרך הבשור עמ"),("342696381","1743000431","בית העלמין 89/1136 BR עמ"),
        ("342581113","1743000431","דרך יתיר פינת שבטה מאור ר"),("342815190","1743000431","דרך מיתר מול 79 פארק רבין"),
        ("342463079","1743000431","שדרות השלום ע\"י 94 מאור ר"),("342824195","1743000431","דרך הבשור פינת מורג מאור"),
        ("341733549","1743000431","אלון ליד 6 מאור רחובות_פי"),("341808296","1613000431","גאון הירדן פינת דרך הראל"),
        ("341826205","1743000431","_כלנית ליד 32 מאור רחובות"),("341734806","1743000431","דרך מיתר אמפיתאטרון פינת"),
        ("341724416","1812300431","חצב 42"),("341699116","1828200820","שד עומרים מרכז פעילות לצע"),
        ("342121567","1743000431","_חסידה ע\"י 11 מאור רחובות"),("341991197","1743000431","שד חברון פינת גאון הירדן"),
        ("342507185","1723000431","צאלים ע\"י מס 3 מקלט מקלט"),("342097094","1812300431","גאון הירדן 22"),
        ("342474564","1743000431","צניפים 36"),("342218419","1743001431","דרורית ליד 60 מאור רחובות"),
        ("342149412","1743001431","צבי ליד 84 מאור רחובות__ת"),("342115788","1812301431","דרורית 42 כרמית - ב.כנסת+מעון יום"),
        ("342193008","1743001431","קורא ליד 35 מאור רחובות_ת"),("342431291","1723000431","קטורה ע\"י 10 מקלט 8 מקלט"),
        ("342077002","1743001431","שד' הזמיר 1 בית כנסת בכלניות"),("342237411","1812301431","דרורית 1 - גן ילדים בכרמית"),
        ("346775530","6000218000","A651 דרך הראל בית ספר מיתרים"),("346200288","1743000431","שד כרמית מול סלעית 133"),
        ("346473767","1829100431","דרך הראל 1"),("346717405","1743001431","דרורית ליד מס 90"),
        ("346337333","1743001431","שדרות כרמית פינת שלו 2"),("345466602","1743000431","קדש ברנע ליד 1 מועדון נוער"),
        ("346386381","1743001431","מרכזיה בכיכר בכביש הגישה לישוב"),("346540372","1812301431","דרורית 42א1"),
        ("346620062","1813207431","שדרות כרמית פינת שקנאי"),("342172752","1743000431","דוכיפת 34 , מיתר"),
        ("342257533","1743000431","BR 11/1132 שדרות הזמיר"),("345944468","1743000431","תאורת רחובות מיתר"),
        ("345807311","1812301431","גני ילדים כרמית"),("346056008","1829000431","מגרשי ספורט"),
        ("347096187","1812300431","גן ילדים"),("347632605","1723000431","מקלט צ9"),
        ("342460468","1824000431","אדומים סולאר בע\"מ שד המייסדים 65/1136 BR"),
        ("342408784","1613000431","אדומים סולאר בע\"מ שד עומרים תחנה פנימית"),
        ("342408725","1813203431","אדומים סולאר בע\"מ שד ההתישבות 61/1136 BR"),
        ("342408380","1813201431","אדומים סולאר בע\"מ שד עומרים 61/1136 BR"),
        ("342287098","1813202431","אדומים סולאר בע\"מ שד עומרים 65/1136 BR"),
        ("342379616","1829100431","אדומים סולאר בע\"מ שד המייסדים 222 אולם ספורט"),
        ("342585176","1723000431","בשמת ע\"י מס 65 מקלט 12 מקלט מיתר 8502500"),
        ("342584186","1723000431","אג מתיישבי נחל חברון"),("342380936","1723000431","אג מתיישבי נחל חברון"),
        ("347237432","1723100431","חוחית ליד מספר 3 מיתר 8502500"),("348437469","1613000431","מועצה מקומית מיתר"),
        ("348027825","1829001431","שד' כרמית מול מעון ראשית כרמית"),
        ("348601121","1743001431","2/1278BR כרמית"),
        ("349087325","1723000431","כובשים ע\"י מס 15 מקלט מס 37 מק מיתר 8502500"),
    ]
    async with db.transaction() as tx:
        conn = tx._conn
        # Update municipality name
        await conn.execute("UPDATE municipalities SET name = 'מ.א חבל מודיעין' WHERE id = $1", MITAR_ID)
        # Get electricity template
        tmpl = await conn.fetchrow("SELECT id FROM templates WHERE name = 'electricity'")
        if not tmpl:
            return {"error": "electricity template not found"}
        tmpl_id = str(tmpl["id"])
        # Load indexes
        created = 0
        for contract, account, name in INDEXES:
            await conn.execute("""
                INSERT INTO indexes (id, municipality_id, template_id, key_value,
                                     account_code, description, connection_name)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (municipality_id, template_id, key_value, account_code)
                DO UPDATE SET connection_name = EXCLUDED.connection_name, updated_at = NOW()
            """, str(uuid.uuid4()), MITAR_ID, tmpl_id, contract, account, "100", name)
            created += 1
    return {"status": "ok", "municipality": "מ.א חבל מודיעין", "indexes_loaded": created}
