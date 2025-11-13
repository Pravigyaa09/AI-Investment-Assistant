# backend/app/routers/webhook.py
from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.logger import get_logger
from app.services.market_data import update_cache_from_webhook

log = get_logger(__name__)
router = APIRouter(tags=["webhook"])


@router.post("/finnhub-webhook")
async def finnhub_webhook(
    request: Request,
    x_finnhub_secret: Optional[str] = Header(None, alias="X-Finnhub-Secret")
):
    """
    Webhook endpoint for Finnhub real-time price updates.

    Finnhub sends trade data in this format:
    {
        "data": [
            {"s": "AAPL", "p": 150.25, "t": 1234567890, "v": 100},
            ...
        ],
        "type": "trade"
    }
    """
    # Verify webhook secret
    if not settings.FINNHUB_WEBHOOK_SECRET:
        log.warning("FINNHUB_WEBHOOK_SECRET not configured, rejecting webhook")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    if x_finnhub_secret != settings.FINNHUB_WEBHOOK_SECRET:
        log.warning(f"Invalid webhook secret received: {x_finnhub_secret}")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        # Parse webhook payload
        payload = await request.json()
        log.info(f"Received webhook: {payload}")

        # Process trade data
        if payload.get("type") == "trade" and "data" in payload:
            trades: List[Dict[str, Any]] = payload["data"]

            for trade in trades:
                symbol = trade.get("s")  # Ticker symbol
                price = trade.get("p")   # Price
                timestamp = trade.get("t")  # Unix timestamp in milliseconds
                volume = trade.get("v")  # Volume

                if symbol and price:
                    # Update the cache with new price
                    update_cache_from_webhook(symbol, float(price), timestamp)
                    log.info(f"Updated {symbol} price to ${price} from webhook")

        # Always return 200 to acknowledge receipt
        return {"status": "success", "message": "Webhook received"}

    except Exception as e:
        log.error(f"Error processing webhook: {e}", exc_info=True)
        # Still return 200 to acknowledge (we handle error internally)
        return {"status": "error", "message": str(e)}
