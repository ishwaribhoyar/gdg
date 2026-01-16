"""
Smart Approval AI - FastAPI Backend
Minimal, official architecture - SQLite temporary storage only
"""

# Load .env from project root FIRST (before any imports that use env vars)
# This ensures .env values override system environment variables
from dotenv import load_dotenv
from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from routers import (
    batches,
    documents,
    processing,
    dashboard,
    reports,
    chatbot,
    compare,
    approval,
    unified_report,
    analytics,
    auth,
    gov_documents,
    users,
)
from routers import kpi_details
from routers import nba

from config.database import init_db
from middleware.auth_middleware import verify_token_middleware

# Initialize SQLite database
init_db()

# CORS configuration (force permissive for local dev to avoid blocked requests)
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = ["*"]
ALLOW_ALL_ORIGINS = True

app = FastAPI(
    title="Smart Approval AI",
    description="AI-Based Document Analysis, Performance Indicators & Reporting System for Accreditation Reviewers (AICTE, NBA, NAAC, NIRF)",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # keep '*' compatible responses
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression for faster response times
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB


# Firebase Authentication middleware (optional - endpoints can enforce auth individually)
# app.middleware("http")(verify_token_middleware)  # Uncomment to enable global auth


@app.middleware("http")
async def add_fallback_cors_headers(request, call_next):
    """
    Ensure CORS headers are present even on error responses (e.g., 404/500),
    which some browsers otherwise flag as missing and surface as CORS failures.
    """
    response = await call_next(request)
    origin = request.headers.get("origin")

    if ALLOW_ALL_ORIGINS:
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
    elif origin and origin in ALLOWED_ORIGINS:
        response.headers.setdefault("Access-Control-Allow-Origin", origin)

    if "Access-Control-Allow-Origin" in response.headers:
        response.headers.setdefault("Access-Control-Allow-Credentials", "false")
        response.headers.setdefault(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, Accept, Origin, X-Requested-With, *",
        )
        response.headers.setdefault(
            "Access-Control-Allow-Methods",
            "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        )

    return response

# Mount static directories
os.makedirs("storage/uploads", exist_ok=True)
os.makedirs("storage/reports", exist_ok=True)
os.makedirs("storage/db", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="storage/uploads"), name="uploads")
app.mount("/reports", StaticFiles(directory="storage/reports"), name="reports")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(batches.router, prefix="/api/batches", tags=["Batches"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(processing.router, prefix="/api/processing", tags=["Processing"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(chatbot.router, prefix="/api/chatbot", tags=["Chatbot"])
app.include_router(gov_documents.router, prefix="/api/gov-documents", tags=["Gov Documents"])
app.include_router(compare.router, prefix="/api", tags=["Comparison"])
app.include_router(approval.router, prefix="/api", tags=["Approval"])
app.include_router(unified_report.router, prefix="/api", tags=["Unified Report"])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"])
app.include_router(kpi_details.router, prefix="/api/kpi", tags=["KPI Details"])
app.include_router(nba.router, prefix="/api/nba", tags=["NBA Accreditation"])


@app.get("/")
def root():
    return {
        "message": "Smart Approval AI API",
        "version": "2.0.0",
        "status": "operational",
        "architecture": "Information Block Architecture - SQLite Temporary Storage"
    }

@app.get("/health")
def root_health_check():
    """Root health check for Railway deployment"""
    return {"status": "healthy"}

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
