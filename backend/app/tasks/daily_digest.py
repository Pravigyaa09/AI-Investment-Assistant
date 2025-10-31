# backend/app/tasks/daily_digest.py
from __future__ import annotations

import json
from typing import List, Optional, Dict
from app.core.config import settings
from app.logger import get_logger

log = get_logger(__name__)


def _twilio_client():
    """Build a Twilio client if credentials + SDK are present."""
    try:
        from twilio.rest import Client
    except Exception as e:
        log.warning("Twilio SDK not installed: %s", e)
        return None

    sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    if not sid or not token:
        log.warning("Twilio credentials missing")
        return None
    try:
        return Client(sid, token)
    except Exception as e:
        log.exception("Failed to build Twilio client: %s", e)
        return None


def _send_plain(client, body: str, to: str, from_: str) -> dict:
    try:
        msg = client.messages.create(from_=from_, to=to, body=body[:1500])
        log.info("WA plain queued sid=%s status=%s", getattr(msg, "sid", "?"), getattr(msg, "status", "?"))
        return {"sent": True, "sid": getattr(msg, "sid", None), "status": getattr(msg, "status", None)}
    except Exception as e:
        log.exception("Twilio plain send failed: %s", e)
        return {"sent": False, "reason": str(e)}


def _send_template(client, content_sid: str, content_variables: Dict[str, str], to: str, from_: str) -> dict:
    try:
        msg = client.messages.create(
            from_=from_,
            to=to,
            content_sid=content_sid,
            content_variables=json.dumps(content_variables or {}),
        )
        log.info("WA template queued sid=%s status=%s", getattr(msg, "sid", "?"), getattr(msg, "status", "?"))
        return {"sent": True, "sid": getattr(msg, "sid", None), "status": getattr(msg, "status", None)}
    except Exception as e:
        # Return error so caller can fallback to plain text
        log.warning("Twilio template send failed: %s", e)
        return {"sent": False, "reason": str(e)}


def send_whatsapp(
    body: str | None = None,
    *,
    to: str | None = None,
    content_sid: str | None = None,
    content_variables: Dict[str, str] | None = None,
) -> dict:
    client = _twilio_client()
    if not client:
        return {"sent": False, "reason": "Twilio not configured or SDK missing"}

    to = to or getattr(settings, "WHATSAPP_TO", None)
    from_ = getattr(settings, "TWILIO_WHATSAPP_FROM", None)
    if not to or not from_:
        return {"sent": False, "reason": "FROM/TO WhatsApp numbers not set"}

    # Prefer template if provided; fallback to plain body if that fails
    if content_sid:
        res = _send_template(client, content_sid, content_variables or {}, to, from_)
        if res.get("sent"):
            return res
        # template failed -> fallback to plain text if body was provided
        if body:
            log.info("Falling back to plain text after template failure")
            return _send_plain(client, body, to, from_)
        return res

    if not body:
        return {"sent": False, "reason": "No body or content_sid provided"}
    return _send_plain(client, body, to, from_)


def _format_digest_line(ticker: str, px: float, change: float | None) -> str:
    chg = ""
    if change is not None:
        sign = "▲" if change >= 0 else "▼"
        chg = f" ({sign}{abs(change):.2f})"
    return f"{ticker}: {px:.2f}{chg}"


async def send_morning_digest(watch: Optional[List[str]] = None, user_email: Optional[str] = None) -> dict:
    """
    Build and send a morning digest via WhatsApp with:
      • latest price for each watch ticker (from user's portfolio)
      • quick news headlines with sentiment
    Prefers WhatsApp Content Template (TWILIO_CONTENT_SID), falls back to plain text on error.
    """
    # Local imports to avoid circular imports
    from app.services.market_data import get_quote, get_previous_close
    from app.services.finnhub_client import fetch_company_news
    from app.db import get_repository, UserRepository

    # Try FinBERT, fall back to simple keywords
    try:
        from app.nlp.finbert import FinBERT
        finbert_ready = getattr(FinBERT, "is_available", lambda: False)()
    except Exception:
        FinBERT = None  # type: ignore
        finbert_ready = False

    # Fetch user's portfolio holdings if email provided
    if user_email and not watch:
        try:
            user_repo = get_repository(UserRepository)
            user = await user_repo.find_by_email(user_email)
            if user and user.get("portfolio"):
                holdings = user["portfolio"].get("holdings", [])
                watch = [h["ticker"] for h in holdings if h.get("ticker")]
                log.info(f"Fetched {len(watch)} tickers from user {user_email}'s portfolio: {watch}")
        except Exception as e:
            log.warning(f"Failed to fetch user portfolio: {e}")
            watch = None

    # Fallback to config or defaults
    watch = watch or (settings.WATCH_TICKERS or ["AAPL", "MSFT"])

    # --- Prices block ---
    price_lines: list[str] = []
    for t in watch:
        px = get_quote(t)
        prev = get_previous_close(t)
        change = (px - prev) if (prev is not None) else None
        price_lines.append(_format_digest_line(t, px, change))
    prices_block = "🌅 Morning digest\n\n*Prices*\n" + "\n".join(price_lines)

    # --- Headlines block ---
    news_bits: list[str] = []
    for t in watch:
        items = fetch_company_news(t, count=2)
        for n in items:
            title = n.get("title") or n.get("headline") or ""
            if not title:
                continue
            label = "neutral"
            try:
                if finbert_ready and FinBERT:
                    pred = FinBERT.predict(title)
                    label = pred.get("label", "neutral")
                else:
                    low = title.lower()
                    if any(w in low for w in ["surge", "jumps", "beats", "rises", "gain", "profit"]):
                        label = "positive"
                    elif any(w in low for w in ["falls", "misses", "slump", "drop", "loss", "cuts"]):
                        label = "negative"
            except Exception:
                pass
            news_bits.append(f"• {t}: [{label}] {title}")

    headlines_block = "*Headlines*\n" + ("\n".join(news_bits) if news_bits else "No major headlines.")
    body = prices_block + "\n\n" + headlines_block

    # --- Send (template first, then fallback) ---
    content_sid = getattr(settings, "TWILIO_CONTENT_SID", None)
    if content_sid:
        return {
            "prices_block": prices_block,
            "headlines_block": headlines_block,
            **send_whatsapp(
                body=body,  # used for fallback
                content_sid=content_sid,
                content_variables={"1": prices_block, "2": headlines_block},
            ),
        }

    return {
        "prices_block": prices_block,
        "headlines_block": headlines_block,
        **send_whatsapp(body=body),
    }
