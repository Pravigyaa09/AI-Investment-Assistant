# backend/app/main.py
from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth
from app.core.config import settings
from app.logger import get_logger
from app.middleware.request_logger import RequestLoggerMiddleware
from app.tasks.scheduler import start_scheduler, shutdown_scheduler
from contextlib import asynccontextmanager
import logging
# MongoDB connection management
from app.db import connect_to_mongo, close_mongo_connection

# Routers
from app.routers import (
    health, news, sentiment, signal,
    price, chart, debug_providers,
    analysis as analysis_router,
    recommender as ml_router,
    auth,
    whatsapp_test,

    # MongoDB routers
    mongo_users, mongo_debug,
    mongo_portfolio_v2,
)

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle with async context manager"""
    # ========== STARTUP ==========
    log.info("Starting AI Investment Assistant...")
    
    # Connect to MongoDB
    try:
        await connect_to_mongo()
        log.info("MongoDB connected successfully")
    except Exception as e:
        log.error(f"Failed to connect to MongoDB: {e}")
        raise
    
    # Enhanced FinBERT check
    try:
        from app.nlp.finbert import FinBERT
        is_available = FinBERT.is_available()
        log.info("FinBERT available? %s", "yes" if is_available else "no")
        if is_available:
            cache_stats = FinBERT.get_cache_stats()
            log.info("FinBERT cache initialized: %s", cache_stats)
    except Exception as e:
        log.warning("FinBERT check skipped: %s", e)
    
    # WhatsApp session check
    try:
        from app.services.whatsapp import get_session_status
        session_status = get_session_status()
        log.info("WhatsApp session status: %s", session_status)
        if session_status.get("needs_renewal", False):
            log.warning("WhatsApp session needs renewal! Send 'join coal-deal' to sandbox")
    except Exception as e:
        log.warning("WhatsApp status check skipped: %s", e)
    
    # Start scheduler
    try:
        scheduler = start_scheduler()
        if scheduler:
            jobs = [job.id for job in scheduler.get_jobs()]
            log.info("Scheduler started with jobs: %s", jobs)
    except Exception as e:
        log.exception("Failed to start scheduler: %s", e)
    
    log.info("Application startup complete!")
    
    yield  # Application runs here
    
    # ========== SHUTDOWN ==========
    log.info("Shutting down AI Investment Assistant...")
    
    # Stop scheduler
    try:
        shutdown_scheduler()
        log.info("Scheduler shutdown completed")
    except Exception as e:
        log.exception("Failed to stop scheduler: %s", e)
    
    # Close MongoDB connection
    try:
        await close_mongo_connection()
        log.info("MongoDB disconnected")
    except Exception as e:
        log.error(f"Error closing MongoDB connection: {e}")
    
    log.info("Application shutdown complete!")


# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Investment Assistant",
    version="2.0.0",
    lifespan=lifespan
)
# Middlewares
# Correct order - CORS MUST BE FIRST
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:4000",  
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4000",
        "http://127.0.0.1:5173",
        "*"  # Add this for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ========== ROUTERS ==========
# Authentication
app.include_router(auth.router, prefix=settings.API_PREFIX)

# Core functionality routers
app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(news.router, prefix=settings.API_PREFIX)
app.include_router(sentiment.router, prefix=settings.API_PREFIX)
app.include_router(signal.router, prefix=settings.API_PREFIX)
app.include_router(price.router, prefix=settings.API_PREFIX)
app.include_router(chart.router, prefix=settings.API_PREFIX)
app.include_router(analysis_router.router, prefix=settings.API_PREFIX)
app.include_router(ml_router.router, prefix=settings.API_PREFIX)

# MongoDB routers
app.include_router(mongo_users.router, prefix=settings.API_PREFIX)
app.include_router(mongo_portfolio_v2.router, prefix=settings.API_PREFIX)
app.include_router(mongo_debug.router, prefix=settings.API_PREFIX)

# WhatsApp testing router
app.include_router(whatsapp_test.router, prefix=settings.API_PREFIX)

# Debug routers
app.include_router(debug_providers.router, prefix=settings.API_PREFIX)

# ========== ROOT ENDPOINTS ==========
@app.get("/")
async def root():
    """Root endpoint with comprehensive system status"""
    try:
        from app.nlp.finbert import FinBERT
        from app.services.whatsapp import get_session_status
        from app.tasks.scheduler import get_scheduler_status
        from app.db import get_db
        
        # Check MongoDB connection
        try:
            db = get_db()
            await db.command("ping")
            mongodb_status = "connected"
        except:
            mongodb_status = "disconnected"
        
        return {
            "message": "AI Investment Assistant - MongoDB Architecture",
            "version": "2.0.0",
            "status": "running",
            "database": {
                "type": "MongoDB",
                "status": mongodb_status
            },
            "features": {
                "finbert_sentiment": FinBERT.is_available(),
                "whatsapp_alerts": bool(settings.TWILIO_ACCOUNT_SID and settings.WHATSAPP_TO),
                "scheduled_analysis": True,
                "real_time_market_data": True,
                "ai_recommendations": True
            },
            "api_endpoints": {
                "auth": f"{settings.API_PREFIX}/auth/*",
                "users": f"{settings.API_PREFIX}/users/*",
                "portfolio": f"{settings.API_PREFIX}/portfolio/*",
                "analysis": f"{settings.API_PREFIX}/analysis/*",
                "sentiment": f"{settings.API_PREFIX}/sentiment/*",
                "ml": f"{settings.API_PREFIX}/ml/*",
                "market_data": f"{settings.API_PREFIX}/price, /history, /chart/*",
                "debug": f"{settings.API_PREFIX}/_debug/*"
            }
        }
    except Exception as e:
        return {
            "message": "AI Investment Assistant",
            "status": "running with errors",
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    from app.db import get_db
    
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "scheduler": "unknown"
    }
    
    # Check MongoDB
    try:
        db = get_db()
        await db.command("ping")
        health_status["database"] = "healthy"
    except:
        health_status["database"] = "unhealthy"
        health_status["status"] = "degraded"
    
    # Check scheduler
    try:
        from app.tasks.scheduler import get_scheduler_status
        scheduler_status = get_scheduler_status()
        health_status["scheduler"] = "healthy" if scheduler_status.get("running") else "stopped"
    except:
        health_status["scheduler"] = "error"
    
    return health_status


@app.get(f"{settings.API_PREFIX}/info")
async def api_info():
    """Get API configuration and status information"""
    return {
        "api_version": "2.0.0",
        "api_prefix": settings.API_PREFIX,
        "cors_origins": settings.CORS_ORIGINS,
        "environment": settings.ENV,
        "features_enabled": {
            "mongodb": True,
            "sentiment_analysis": True,
            "ai_recommendations": True,
            "real_time_data": True,
            "notifications": bool(settings.TWILIO_ACCOUNT_SID)
        }
    }