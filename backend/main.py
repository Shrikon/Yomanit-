# main.py – יומנית Backend
# FastAPI + PostgreSQL + pandas
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import db
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
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
    title="יומנית API",
    description="מערכת ניהול פקודות יומן לרשויות מקומיות",
    version="0.1.0",
    lifespan=lifespan,
)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    logging.error(f"UNHANDLED ERROR: {tb}")
    return JSONResponse(status_code=500, content={"detail": str(exc), "traceback": tb[-1000:]})
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
