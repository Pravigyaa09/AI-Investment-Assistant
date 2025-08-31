# backend/app/tasks/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from typing import Dict, List, Any
from app.core.config import settings
from app.services.finnhub_client import fetch_company_news
from app.services.signal_engine import rule_based_signal
from app.logger import get_logger

# WhatsApp integration
from app.services.whatsapp import (
    scheduled_session_check, 
    send_daily_digest, 
    send_sentiment_alert,
    WhatsAppDigestService
)

# Use enhanced FinBERT if available; fallback to keywords
try:
    from app.nlp.finbert import FinBERT
    def predict_sentiment(text: str):
        try:
            if FinBERT.is_available():
                return FinBERT.predict(text)
        except Exception:
            pass
        # Enhanced fallback
        t = (text or "").lower()
        for w in ["surge","jumps","beats","rises","gain","bull","profit","record","soar"]:
            if w in t: return {"label":"positive","score":0.66}
        for w in ["falls","misses","slump","drop","bear","loss","down","plunge","cut"]:
            if w in t: return {"label":"negative","score":0.66}
        return {"label":"neutral","score":0.5}
except Exception:
    def predict_sentiment(text: str):
        t = (text or "").lower()
        for w in ["surge","jumps","beats","rises","gain","bull","profit","record","soar"]:
            if w in t: return {"label":"positive","score":0.66}
        for w in ["falls","misses","slump","drop","bear","loss","down","plunge","cut"]:
            if w in t: return {"label":"negative","score":0.66}
        return {"label":"neutral","score":0.5}

log = get_logger(__name__)
_scheduler: BackgroundScheduler | None = None

# Store previous results to detect significant changes
_previous_results: Dict[str, Dict] = {}

def _score_one_ticker(ticker: str) -> Dict[str, Any]:
    """Enhanced ticker scoring with detailed sentiment analysis"""
    try:
        news = fetch_company_news(ticker, count=30)
        news_texts = [n.get("title", "") for n in news if n.get("title")]
        
        if not news_texts:
            log.warning(f"No news found for {ticker}")
            return {"ticker": ticker, "error": "No news found"}
        
        # Enhanced sentiment analysis
        if FinBERT.is_available():
            sentiments = FinBERT.predict_batch(news_texts)
            # Get detailed distribution
            distribution = FinBERT.get_sentiment_distribution(news_texts)
        else:
            sentiments = [predict_sentiment(text) for text in news_texts]
            # Calculate distribution manually
            counts = {"positive": 0, "neutral": 0, "negative": 0}
            for s in sentiments:
                counts[s["label"]] += 1
            distribution = {
                "distribution": {k: v/len(sentiments) for k, v in counts.items()},
                "average_score": sum(1 if s["label"]=="positive" else -1 if s["label"]=="negative" else 0 for s in sentiments) / len(sentiments),
                "total_count": len(sentiments)
            }
        
        # Generate signal
        counts = {"positive": 0, "neutral": 0, "negative": 0}
        for s in sentiments:
            counts[s["label"]] += 1
        
        action, conf = rule_based_signal(counts)
        
        result = {
            "ticker": ticker,
            "action": action,
            "confidence": conf,
            "sentiment_counts": counts,
            "sentiment_distribution": distribution,
            "news_analyzed": len(sentiments),
            "timestamp": datetime.now(),
            "high_confidence_sentiment": len([s for s in sentiments if s.get("confidence") == "high"]) if FinBERT.is_available() else 0
        }
        
        log.info("[SCHEDULE] %s -> %s (conf=%.3f) sentiment_dist=%s items=%d",
                ticker, action, conf, distribution.get("distribution", counts), len(sentiments))
        
        return result
        
    except Exception as e:
        log.exception("[SCHEDULE] error scoring %s: %s", ticker, e)
        return {"ticker": ticker, "error": str(e)}

def _detect_significant_changes(current_results: List[Dict]) -> List[Dict]:
    """Detect significant sentiment changes since last run"""
    global _previous_results
    significant_changes = []
    
    for result in current_results:
        ticker = result.get("ticker")
        if not ticker or "error" in result:
            continue
            
        current_dist = result.get("sentiment_distribution", {}).get("distribution", {})
        previous_result = _previous_results.get(ticker)
        
        if previous_result:
            prev_dist = previous_result.get("sentiment_distribution", {}).get("distribution", {})
            
            # Check for significant sentiment shifts (>20% change in positive/negative)
            pos_change = abs(current_dist.get("positive", 0) - prev_dist.get("positive", 0))
            neg_change = abs(current_dist.get("negative", 0) - prev_dist.get("negative", 0))
            
            if pos_change > 0.2 or neg_change > 0.2:
                significant_changes.append({
                    "ticker": ticker,
                    "current": current_dist,
                    "previous": prev_dist,
                    "positive_change": current_dist.get("positive", 0) - prev_dist.get("positive", 0),
                    "negative_change": current_dist.get("negative", 0) - prev_dist.get("negative", 0),
                    "significance": "high" if (pos_change > 0.3 or neg_change > 0.3) else "medium"
                })
        
        # Update previous results
        _previous_results[ticker] = result
    
    return significant_changes

def job_fetch_and_score():
    """Enhanced job that includes WhatsApp alerting"""
    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("[SCHEDULE] running at %s for tickers=%s", when, settings.WATCH_TICKERS)
    
    current_results = []
    
    # Analyze each ticker
    for ticker in settings.WATCH_TICKERS:
        try:
            result = _score_one_ticker(ticker)
            current_results.append(result)
        except Exception as e:
            log.exception("[SCHEDULE] error scoring %s: %s", ticker, e)
            current_results.append({"ticker": ticker, "error": str(e)})
    
    # Detect significant changes
    significant_changes = _detect_significant_changes(current_results)
    
    # Send alerts for significant changes
    if significant_changes:
        try:
            # Create alert data
            alert_data = {
                "significant_changes": significant_changes,
                "timestamp": datetime.now(),
                "total_tickers": len(settings.WATCH_TICKERS)
            }
            
            # Create portfolio sentiment data for alerts
            portfolio_sentiment = {}
            for result in current_results:
                if "error" not in result:
                    ticker = result["ticker"]
                    portfolio_sentiment[ticker] = {
                        "sentiment": {
                            "label": result["action"],  # Using signal as sentiment
                            "score": result["confidence"],
                            "confidence": "high" if result["confidence"] > 0.7 else "medium"
                        }
                    }
            
            # Send alert asynchronously (don't block the scheduler)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # If event loop is running, schedule the task
                asyncio.create_task(send_sentiment_alert(alert_data, portfolio_sentiment))
            else:
                # If no event loop, run it
                loop.run_until_complete(send_sentiment_alert(alert_data, portfolio_sentiment))
                
            log.info("[SCHEDULE] Sent WhatsApp alert for %d significant changes", len(significant_changes))
            
        except Exception as e:
            log.error("[SCHEDULE] Failed to send WhatsApp alert: %s", e)

def job_daily_digest():
    """Send daily market digest via WhatsApp"""
    try:
        log.info("[SCHEDULE] Sending daily WhatsApp digest")
        
        # You can enhance this to include actual sentiment data
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            asyncio.create_task(send_daily_digest(settings.WATCH_TICKERS))
        else:
            loop.run_until_complete(send_daily_digest(settings.WATCH_TICKERS))
            
        log.info("[SCHEDULE] Daily digest sent")
        
    except Exception as e:
        log.error("[SCHEDULE] Failed to send daily digest: %s", e)

def start_scheduler():
    """Enhanced scheduler with WhatsApp integration"""
    global _scheduler
    if _scheduler:
        return _scheduler
    
    _scheduler = BackgroundScheduler()
    
    # Original sentiment scoring job
    _scheduler.add_job(
        job_fetch_and_score, 
        "interval", 
        minutes=settings.SCHEDULE_MINUTES, 
        id="score_job", 
        max_instances=1, 
        coalesce=True
    )
    
    # WhatsApp session check (every 4 hours)
    _scheduler.add_job(
        scheduled_session_check,
        "interval",
        hours=4,
        id="whatsapp_session_check",
        max_instances=1
    )
    
    # Daily digest (8 AM IST, as configured in your settings)
    daily_hour = getattr(settings, 'DAILY_ALERT_HOUR', 8)
    _scheduler.add_job(
        job_daily_digest,
        "cron",
        hour=daily_hour,
        minute=0,
        id="daily_whatsapp_digest",
        max_instances=1
    )
    
    _scheduler.start()
    log.info("[SCHEDULE] started: scoring every %d min, WhatsApp checks every 4h, daily digest at %d:00", 
             settings.SCHEDULE_MINUTES, daily_hour)
    return _scheduler

def shutdown_scheduler():
    """Shutdown scheduler"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        log.info("[SCHEDULE] stopped")
        _scheduler = None

# Manual trigger functions for testing
def trigger_sentiment_analysis():
    """Manually trigger sentiment analysis (for testing)"""
    job_fetch_and_score()

def trigger_daily_digest():
    """Manually trigger daily digest (for testing)"""
    job_daily_digest()

def get_scheduler_status():
    """Get current scheduler status and job info"""
    global _scheduler
    if not _scheduler:
        return {"running": False, "jobs": []}
    
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name or str(job.func),
            "next_run": job.next_run_time,
            "trigger": str(job.trigger)
        })
    
    return {
        "running": _scheduler.running,
        "jobs": jobs,
        "watch_tickers": settings.WATCH_TICKERS,
        "schedule_minutes": settings.SCHEDULE_MINUTES
    }