# backend/app.py
from fastapi import FastAPI, Request
from logger import get_logger

# Routers
from routes import sentiment, portfolio, news
from routes.signal import router as signal_router  # <-- new

logger = get_logger(__name__)
app = FastAPI()

# Include routers with prefixes
app.include_router(sentiment.router, prefix="/api/sentiment")
app.include_router(portfolio.router, prefix="/api/portfolio")
app.include_router(news.router, prefix="/api")
app.include_router(signal_router, prefix="/api")   # <-- /api/signal

@app.get("/")
async def read_root(request: Request):
    logger.info("GET request to root '/' from %s", request.client.host)
    try:
        logger.debug("Responding to root health check")
        return {"message": "Backend is working!"}
    except Exception:
        logger.exception("Error occurred in root route")
        return {"error": "Internal server error"}
