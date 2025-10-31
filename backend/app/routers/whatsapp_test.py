"""WhatsApp testing endpoints"""
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user_mongo
from app.tasks.daily_digest import send_morning_digest
from app.tasks.scheduler import trigger_daily_digest, trigger_sentiment_analysis
from app.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Testing"])


@router.post("/test-digest")
async def test_whatsapp_digest(current_user: dict = Depends(get_current_user_mongo)):
    """
    Manually trigger WhatsApp digest for current user's portfolio
    """
    try:
        user_email = current_user.get("email")
        log.info(f"Triggering WhatsApp digest for user: {user_email}")

        # Send morning digest with user's portfolio
        result = await send_morning_digest(user_email=user_email)

        return {
            "success": result.get("sent", False),
            "user_email": user_email,
            "result": result
        }
    except Exception as e:
        log.error(f"Failed to send test digest: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/test-scheduled-digest")
async def test_scheduled_digest():
    """
    Test the scheduled daily digest job (admin only)
    """
    try:
        log.info("Manually triggering scheduled daily digest")
        trigger_daily_digest()
        return {
            "success": True,
            "message": "Scheduled daily digest triggered"
        }
    except Exception as e:
        log.error(f"Failed to trigger scheduled digest: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/test-sentiment-alerts")
async def test_sentiment_alerts():
    """
    Test the sentiment analysis and alerts (admin only)
    """
    try:
        log.info("Manually triggering sentiment analysis")
        trigger_sentiment_analysis()
        return {
            "success": True,
            "message": "Sentiment analysis triggered"
        }
    except Exception as e:
        log.error(f"Failed to trigger sentiment analysis: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/my-portfolio-tickers")
async def get_my_portfolio_tickers(current_user: dict = Depends(get_current_user_mongo)):
    """
    Get the tickers in current user's portfolio that will be used for WhatsApp alerts
    """
    try:
        portfolio = current_user.get("portfolio", {})
        holdings = portfolio.get("holdings", [])
        tickers = [h["ticker"] for h in holdings if h.get("ticker")]

        return {
            "user_email": current_user.get("email"),
            "tickers": tickers,
            "count": len(tickers),
            "message": "These tickers will be included in your WhatsApp alerts"
        }
    except Exception as e:
        log.error(f"Failed to fetch portfolio tickers: {e}")
        return {
            "error": str(e)
        }
