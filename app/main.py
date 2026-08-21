"""Smart Resume Screener API Application.

Main entry point for the FastAPI backend service.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import jobs, matching, resumes
from app.database.database import init_db


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Lifespan context manager to initialize database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="Smart Resume Screener API",
    description="Automated resume screening, candidate ranking, and semantic evaluation.",
    version="0.1.0",
    lifespan=lifespan,
)

# Register API routers
app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(matching.router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}
