import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.api.endpoints import router as api_router

# Lifespan startup: initialize database schema with pure SQL and ensure storage dir exists
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Execute SQL CREATE TABLE statements
    init_db()
    # Ensure storage folder exists
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    yield

app = FastAPI(
    title="Bulk Certificate Generator API",
    description="Asynchronous backend service for automated batch certificate generation, progress tracking, and batch export.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import RedirectResponse

app.include_router(api_router)


@app.get("/", tags=["Health"])
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "Bulk Certificate Generator API",
        "docs_url": "/docs"
    }
