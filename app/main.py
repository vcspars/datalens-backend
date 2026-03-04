"""FastAPI application main file"""
import asyncio
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.routes import auth, datasets
from app.routes import chat as chat_routes
from app.routes import dashboard as dashboard_routes
from app.services.langchain_agent import _get_sql_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    await connect_to_mongo()
    # Warm up LangChain SQLDatabase cache (read-only) so first query is fast
    try:
        print("[Main] Warming up SQLDatabase cache (read-only)...")
        await asyncio.to_thread(_get_sql_db)
        print("[Main] SQLDatabase cache ready")
    except Exception as e:
        # Do not block app startup if SQL Server is temporarily unavailable
        print(f"[Main] SQLDatabase warm-up failed: {e}")
    yield
    # Shutdown
    await close_mongo_connection()


app = FastAPI(
    title="DataLens API",
    description="Backend API for DataLens application",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - must be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": str(exc) if str(exc) else "Internal server error",
            "type": type(exc).__name__
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Validation exception handler"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(chat_routes.router, prefix="/api")
app.include_router(dashboard_routes.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "DataLens API is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/debug/cors")
async def debug_cors():
    """Debug endpoint to check CORS configuration"""
    return {
        "cors_origins": settings.CORS_ORIGINS,
        "cors_origins_type": str(type(settings.CORS_ORIGINS))
    }

