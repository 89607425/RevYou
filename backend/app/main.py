"""FastAPI entry point."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import review, tapd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize storage backend on startup
    from .storage import session_store
    logging.getLogger(__name__).info(
        "Storage backend ready: %s", type(session_store).__name__
    )
    yield
    # Close pool on shutdown
    session_store.close()


app = FastAPI(
    title="RevYou",
    version="1.0.0",
    description="Autonomous three-agent requirement document review system",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(review.router)
app.include_router(tapd.router)


@app.get("/")
async def root():
    return {
        "name": "RevYou",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}
