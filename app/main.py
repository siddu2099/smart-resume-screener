"""Smart Resume Screener API Application.

Main entry point for the FastAPI backend service.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Smart Resume Screener API",
    description="Automated resume screening, candidate ranking, and semantic evaluation.",
    version="0.1.0",
)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}
