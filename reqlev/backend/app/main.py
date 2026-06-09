"""ReqLev – FastAPI Application Entry Point"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .config import settings
from .database import create_tables
from .routers import auth, users, projects, requirements, activities, sse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup; clean up on shutdown."""
    create_tables()
    print(f"✅  ReqLev API started – http://localhost:8000")
    print(f"📖  Swagger UI: http://localhost:8000/api/docs")
    yield
    # shutdown: nothing to clean up for now


app = FastAPI(
    title="ReqLev API",
    description=(
        "Project & Requirements Management Platform with real-time collaboration.\n\n"
        "**Auth**: All protected endpoints require `Authorization: Bearer <token>`.\n\n"
        "**SSE**: Real-time endpoints accept `?token=<token>` query parameter."
    ),
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ───────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(requirements.router)
app.include_router(activities.router)
app.include_router(sse.router)

# ── Frontend static files ─────────────────────────────────────────────────────
_frontend_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
)

if os.path.isdir(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str = ""):
        index = os.path.join(_frontend_dir, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return {"message": "Frontend not found – serve frontend/index.html separately."}
