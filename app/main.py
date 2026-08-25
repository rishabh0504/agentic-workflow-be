from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.routers import tools, agents, providers, agent_runs, guardrails, workflows, io_contracts
import app.models  # Ensure models are imported for create_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Auto-seed database if empty
    try:
        from app.seeds.seed_contracts_workflows import seed_production_contracts_and_workflows
        await seed_production_contracts_and_workflows()
    except Exception as e:
        print(f"[Lifespan Startup] Seeding notice: {e}")

    yield
    # Dispose connection pool on shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Asynchronous Business Rule Engine (BRE) REST API backend powered by FastAPI, PostgreSQL, and Supabase.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(tools.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(providers.router, prefix="/api/v1")
app.include_router(agent_runs.router, prefix="/api/v1")
app.include_router(guardrails.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(io_contracts.router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": "connected",
    }
