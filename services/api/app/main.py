from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import APP_NAME, APP_TAGLINE, APP_VERSION, CORS_ORIGINS
from .core.database import Base, SessionLocal, engine
from .core.seeder import seed_demo_database
from .routers import (
    engagement,
    enrichment,
    customer_mvp,
    governance,
    sessions,
    rm,
    poi,
    auth,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from .core.config import ENVIRONMENT, DATABASE_URL_EXPLICIT
    if ENVIRONMENT == 'production' and not DATABASE_URL_EXPLICIT:
        raise RuntimeError('Production requires an explicit DATABASE_URL')
    # Schema management and synthetic seeding are explicit CLI operations.
    yield

app = FastAPI(
    title=f"{APP_NAME} API",
    description=f"{APP_TAGLINE} - REST API",
    version=APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(engagement.router)
app.include_router(enrichment.router)
app.include_router(customer_mvp.router)
app.include_router(governance.router)
app.include_router(sessions.router)
app.include_router(rm.router)
app.include_router(poi.router)
app.include_router(auth.router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "message": f"{APP_NAME} backend service is operating normally."
    }
