import time
import logging
import sys
import json
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.db.session import db_manager, Base
from app.db.redis import redis_client
from app.db.chroma import chroma_manager
from app.api.endpoints import analyze, auth, users
from app.services import nlp_preprocessor, sentiment_analyzer, gemini_analyzer, embedding_service

# Register models for Base.metadata.create_all discovery
from app.models.user import User
from app.models.analysis import Analysis
from app.models.article import Article

# Configure Structured JSON Logging
class JSONLogFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "time": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage()
        }
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

handler = logging.StreamHandler(sys.stdout)
file_handler = logging.FileHandler("backend.log")
handler.setFormatter(JSONLogFormatter())
file_handler.setFormatter(JSONLogFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler, file_handler])
logger = logging.getLogger("truelens")

from app.core.rate_limit import limiter

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Set CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup and Shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("Initializing application startup sequence...")
    
    # 1. Initialize DB Connection
    db_manager.initialize()
    
    # Test connection and fall back to SQLite if needed
    is_connected = await db_manager.test_connection()
    if not is_connected:
        logger.warning("Could not establish connection to PostgreSQL database. Falling back to local SQLite.")
        db_manager.fallback_to_sqlite()
        
    # Create tables automatically
    try:
        async with db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLAlchemy database tables initialized successfully.")
    except Exception as e:
        logger.critical(f"Database table initialization failed: {e}")

    # 2. Connect Redis (falls back automatically to in-memory mock client if offline)
    redis_client.connect()
    await redis_client.is_healthy()
    
    # 3. Connect Chroma (falls back automatically to in-memory local client if offline)
    chroma_manager.connect()
    
    # 4. Initialize AI Models (DISABLED ON STARTUP FOR FREE TIER)
    # Loading Spacy and Torch on startup causes Render 512MB RAM limit OOMs
    # By commenting this out, the models will lazy-load ONLY when an analysis request is made.
    # nlp_preprocessor._ensure_models_loaded()
    # embedding_service._ensure_initialized()
    
    # Configure PyTorch to use less memory (if available)
    try:
        import torch
        torch.set_num_threads(1)
        logger.info("Configured PyTorch to use 1 thread to save memory on free tier.")
    except ImportError:
        pass

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Running application shutdown sequence...")
    await redis_client.disconnect()

# Timing & Logging Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"{request.method} {request.url.path} completed in {process_time:.4f}s - Status: {response.status_code}")
    return response

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception occurred during request {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )

# Routers
app.include_router(analyze.router, prefix=f"{settings.API_V1_STR}/analyze", tags=["analyze"])
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])


# Health Check API
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    db_healthy = await db_manager.test_connection()
    redis_healthy = await redis_client.is_healthy()
    chroma_healthy = chroma_manager.is_healthy()

    overall_healthy = db_healthy and redis_healthy and chroma_healthy
    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if overall_healthy else "unhealthy",
            "services": {
                "database": "healthy" if db_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unhealthy",
                "chromadb": "healthy" if chroma_healthy else "unhealthy"
            },
            "environment": {
                "using_sqlite": db_manager.is_sqlite,
                "using_redis_mock": redis_client.is_mock
            }
        }
    )
