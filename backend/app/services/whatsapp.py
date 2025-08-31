# backend/app/services/whatsapp.py
from __future__ import annotations
import os
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from app.logger import get_logger
from app.core.config import settings

log = get_logger(__name__)

try:
    from twilio.rest import Client  # type: ignore
    from twilio.base.exceptions import TwilioRestException
except Exception:
    Client = None
    TwilioRestException = Exception

# Session management for Twilio Sandbox
class WhatsAppSessionManager:
    """Manage WhatsApp Sandbox sessions and handle 24-hour expiry"""
    
    def __init__(self):
        self.last_successful_send = None
        self.session_expired = False
        self.sandbox_code = "join coal-deal"  # Your specific code
    
    def check_session_status(self) -> Dict[str, Any]:
        """Check if the WhatsApp session is likely expired"""
        if self.last_successful_send:
            time_since_last = datetime.now() - self.last_successful_send
            expires_in = timedelta(hours=24) - time_since_last
            
            return {
                "session_active": expires_in.total_seconds() > 0,
                "expires_in_hours": max(0, expires_in.total_seconds() / 3600),
                "last_successful_send": self.last_successful_send,
                "needs_renewal": expires_in.total_seconds() < 3600  # Warn 1 hour before
            }
        
        return {
            "session_active": False,
            "expires_in_hours": 0,
            "last_successful_send": None,
            "needs_renewal": True
        }
    
    def create_session_reminder(self) -> str:
        """Create a friendly reminder message about session renewal"""
        return f"""🔄 *WhatsApp Session Renewal Needed*

Your notification session will expire soon!

To keep receiving alerts:
📱 Send "{self.sandbox_code}" to this number

⏰ Sessions expire every 24 hours in sandbox mode
🤖 This ensures you get your market updates!"""

# Global session manager instance
session_manager = WhatsAppSessionManager()

def _client() -> Optional["Client"]: # type: ignore
    """Get Twilio client with proper error handling"""
    sid = settings.TWILIO_ACCOUNT_SID or os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    tok = settings.TWILIO_AUTH_TOKEN or os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not (sid and tok and Client):
        return None
    try:
        return Client(sid, tok)
    except Exception as e:
        log.warning("Twilio client init failed: %s", e)
        return None

def send_whatsapp(body: str, use_template: bool = False, template_vars: Optional[Dict] = None) -> dict:
    """
    Send a WhatsApp message via Twilio with session management.
    
    Args:
        body: Message text (max 1600 chars for WhatsApp)
        use_template: Whether to use a Twilio template
        template_vars: Variables for template substitution
    
    Returns:
        dict: {sent: bool, sid: str, status: str, reason: str}
    """
    from_num = settings.TWILIO_WHATSAPP_FROM or os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
    to_num = settings.WHATSAPP_TO or os.getenv("WHATSAPP_TO", "").strip()
    cli = _client()

    if not cli:
        reason = "Twilio unavailable or missing credentials"
        log.warning("WA send skipped: %s", reason)
        return {"sent": False, "reason": reason}
    if not (from_num and to_num):
        reason = "Missing TWILIO_WHATSAPP_FROM or WHATSAPP_TO"
        log.warning("WA send skipped: %s", reason)
        return {"sent": False, "reason": reason}

    try:
        # Use template if specified
        if use_template and settings.TWILIO_CONTENT_SID:
            msg = cli.messages.create(
                from_=from_num,
                to=to_num,
                content_sid=settings.TWILIO_CONTENT_SID,
                content_variables=template_vars or {}
            )
        else:
            # Regular message with length limit
            truncated_body = body[:1500] if len(body) > 1500 else body
            msg = cli.messages.create(from_=from_num, to=to_num, body=truncated_body)
        
        # Update session manager on successful send
        session_manager.last_successful_send = datetime.now()
        session_manager.session_expired = False
        
        log.info("WA message queued sid=%s status=%s", getattr(msg, "sid", "?"), getattr(msg, "status", "?"))
        return {
            "sent": True, 
            "sid": getattr(msg, "sid", None), 
            "status": getattr(msg, "status", None),
            "message_length": len(body)
        }
        
    except TwilioRestException as e:
        log.exception("WA send failed: %s", e)
        
        # Check if it's a session expiry error
        error_msg = str(e).lower()
        if "not a valid whatsapp recipient" in error_msg or "is not a whatsapp user" in error_msg:
            session_manager.session_expired = True
            log.warning("WhatsApp session expired. User needs to send: %s", session_manager.sandbox_code)
            return {
                "sent": False, 
                "reason": f"Session expired. Send '{session_manager.sandbox_code}' to reactivate",
                "session_expired": True,
                "renewal_code": session_manager.sandbox_code
            }
        
        return {"sent": False, "reason": str(e)}
    
    except Exception as e:
        log.exception("WA send failed: %s", e)
        return {"sent": False, "reason": str(e)}

def send_session_reminder() -> dict:
    """Send a session renewal reminder"""
    reminder = session_manager.create_session_reminder()
    return send_whatsapp(reminder)

def get_session_status() -> dict:
    """Get current WhatsApp session status"""
    return session_manager.check_session_status()

class WhatsAppDigestService:
    """Service for creating and sending WhatsApp digests with sentiment analysis"""
    
    @staticmethod
    def format_sentiment_emoji(sentiment_label: str, confidence: str = "medium") -> str:
        """Convert sentiment to emoji representation"""
        emoji_map = {
            "positive": "🟢" if confidence == "high" else "🟡",
            "negative": "🔴" if confidence == "high" else "🟠", 
            "neutral": "⚪"
        }
        return emoji_map.get(sentiment_label, "❓")
    
    @staticmethod
    def create_sentiment_summary(sentiment_data: Dict[str, Any]) -> str:
        """Create a formatted sentiment summary for WhatsApp"""
        if not sentiment_data:
            return "📊 No sentiment data available"
        
        distribution = sentiment_data.get("distribution", {})
        avg_score = sentiment_data.get("average_score", 0)
        total_count = sentiment_data.get("total_count", 0)
        
        # Overall sentiment indicator
        if avg_score > 0.2:
            overall_emoji = "📈"
            overall_text = "Bullish"
        elif avg_score < -0.2:
            overall_emoji = "📉"
            overall_text = "Bearish"
        else:
            overall_emoji = "➡️"
            overall_text = "Neutral"
        
        summary = f"""📊 *Market Sentiment Update*
{overall_emoji} Overall: *{overall_text}* (Score: {avg_score:.2f})

📈 Positive: {distribution.get('positive', 0):.1%}
➡️ Neutral: {distribution.get('neutral', 0):.1%}
📉 Negative: {distribution.get('negative', 0):.1%}

📰 Analyzed: {total_count} sources"""
        
        return summary
    
    @staticmethod
    def create_portfolio_sentiment_alert(portfolio_sentiment: Dict[str, Any]) -> str:
        """Create portfolio-specific sentiment alert"""
        alerts = []
        
        for ticker, data in portfolio_sentiment.items():
            sentiment = data.get("sentiment", {})
            label = sentiment.get("label", "neutral")
            score = sentiment.get("score", 0)
            confidence = sentiment.get("confidence", "low")
            
            emoji = WhatsAppDigestService.format_sentiment_emoji(label, confidence)
            
            if confidence == "high" and (score > 0.8 or (label == "negative" and score > 0.7)):
                alerts.append(f"{emoji} *{ticker}*: {label.title()} ({score:.2f})")
        
        if not alerts:
            return ""
        
        header = "🚨 *Portfolio Sentiment Alerts*\n"
        return header + "\n".join(alerts)
    
    @staticmethod
    def create_news_digest(news_sentiment: List[Dict[str, Any]], limit: int = 5) -> str:
        """Create a digest of top news with sentiment"""
        if not news_sentiment:
            return "📰 No recent news analyzed"
        
        # Sort by sentiment confidence and recency
        sorted_news = sorted(
            news_sentiment,
            key=lambda x: (
                x.get("sentiment", {}).get("score", 0) * 
                (1 if x.get("sentiment", {}).get("confidence", "low") == "high" else 0.7)
            ),
            reverse=True
        )[:limit]
        
        digest_lines = ["📰 *Top Market News*\n"]
        
        for i, item in enumerate(sorted_news, 1):
            title = item.get("title", "No title")[:50] + "..." if len(item.get("title", "")) > 50 else item.get("title", "")
            sentiment = item.get("sentiment", {})
            emoji = WhatsAppDigestService.format_sentiment_emoji(
                sentiment.get("label", "neutral"),
                sentiment.get("confidence", "low")
            )
            
            digest_lines.append(f"{i}. {emoji} {title}")
        
        return "\n".join(digest_lines)
    
    @staticmethod
    def create_anomaly_alert(anomalies: List[Dict[str, Any]]) -> str:
        """Create alert for sentiment anomalies"""
        if not anomalies:
            return ""
        
        high_significance = [a for a in anomalies if a.get("significance") == "high"]
        
        if high_significance:
            alert = "⚠️ *Unusual Market Sentiment Detected*\n"
            alert += f"🔍 {len(high_significance)} high-significance anomalies\n"
            alert += "📊 This might indicate breaking news or market events"
            return alert
        
        return ""

# Digest creation functions
def create_daily_digest(portfolio_tickers: List[str] = None) -> str:
    """Create a comprehensive daily sentiment digest"""
    try:
        from app.nlp.finbert import FinBERT
        
        if not FinBERT.is_available():
            return "🤖 Sentiment analysis temporarily unavailable. Using basic market data only."
        
        # Check session status first
        status = session_manager.check_session_status()
        if status.get("needs_renewal", False):
            return session_manager.create_session_reminder()
        
        digest = f"""🌅 *Daily Market Digest*
📅 {datetime.now().strftime('%B %d, %Y')}

📊 Session Status: ✅ Active ({status.get('expires_in_hours', 0):.1f}h remaining)

{WhatsAppDigestService.create_sentiment_summary({})}

---
🕐 Generated at {datetime.now().strftime('%H:%M')} IST
🤖 AI Investment Assistant"""
        
        return digest
        
    except Exception as e:
        log.error(f"Failed to create daily digest: {e}")
        return f"❌ Error creating digest: {str(e)}"

def create_alert_digest(sentiment_data: Dict[str, Any], 
                       portfolio_data: Optional[Dict[str, Any]] = None) -> str:
    """Create an alert-style digest for immediate notifications"""
    try:
        digest_parts = []
        
        # Add timestamp
        digest_parts.append(f"⏰ *Alert* - {datetime.now().strftime('%H:%M')} IST\n")
        
        # Portfolio alerts if available
        if portfolio_data:
            portfolio_alert = WhatsAppDigestService.create_portfolio_sentiment_alert(portfolio_data)
            if portfolio_alert:
                digest_parts.append(portfolio_alert)
        
        # Anomaly alerts
        anomalies = sentiment_data.get("anomalies", [])
        anomaly_alert = WhatsAppDigestService.create_anomaly_alert(anomalies)
        if anomaly_alert:
            digest_parts.append(anomaly_alert)
        
        # General sentiment if no specific alerts
        if len(digest_parts) == 1:  # Only timestamp added
            sentiment_summary = WhatsAppDigestService.create_sentiment_summary(sentiment_data)
            digest_parts.append(sentiment_summary)
        
        return "\n\n".join(digest_parts)
        
    except Exception as e:
        log.error(f"Failed to create alert digest: {e}")
        return f"❌ Alert generation failed: {str(e)}"

# Enhanced convenience functions
async def send_daily_digest(portfolio_tickers: List[str] = None) -> dict:
    """Send daily digest via WhatsApp with session awareness"""
    try:
        # Check if session needs renewal first
        status = session_manager.check_session_status()
        if status.get("needs_renewal", False) and not session_manager.session_expired:
            # Send renewal reminder instead of digest
            return send_session_reminder()
        
        digest = create_daily_digest(portfolio_tickers)
        return send_whatsapp(digest)
    except Exception as e:
        log.error(f"Failed to send daily digest: {e}")
        return {"sent": False, "reason": str(e)}

async def send_sentiment_alert(sentiment_data: Dict[str, Any], 
                              portfolio_data: Optional[Dict[str, Any]] = None) -> dict:
    """Send sentiment-based alert via WhatsApp"""
    try:
        alert = create_alert_digest(sentiment_data, portfolio_data)
        return send_whatsapp(alert)
    except Exception as e:
        log.error(f"Failed to send sentiment alert: {e}")
        return {"sent": False, "reason": str(e)}

def send_session_reminder() -> dict:
    """Send a session renewal reminder"""
    try:
        reminder = session_manager.create_session_reminder()
        return send_whatsapp(reminder)
    except Exception as e:
        log.error(f"Failed to send session reminder: {e}")
        return {"sent": False, "reason": str(e)}

def get_session_status() -> dict:
    """Get current WhatsApp session status"""
    return session_manager.check_session_status()

# Template-based messaging (if you want to use Twilio templates)
def send_template_alert(template_vars: Dict[str, str]) -> dict:
    """Send WhatsApp message using Twilio template"""
    try:
        return send_whatsapp("", use_template=True, template_vars=template_vars)
    except Exception as e:
        log.error(f"Failed to send template alert: {e}")
        return {"sent": False, "reason": str(e)}

# Scheduled session check function for your scheduler
async def scheduled_session_check():
    """
    Function to add to your scheduler to check session status.
    Call this every 4-6 hours to warn before expiry.
    """
    try:
        status = get_session_status()
        
        # Send reminder if session expires in less than 1 hour and not already expired
        if status.get("needs_renewal", False) and not session_manager.session_expired:
            log.info("Sending WhatsApp session renewal reminder")
            result = send_session_reminder()
            return {"reminder_sent": result.get("sent", False), "status": status}
        
        return {"reminder_sent": False, "status": status}
        
    except Exception as e:
        log.error(f"Scheduled session check failed: {e}")
        return {"error": str(e)}

# Smart digest that adapts based on session status
def create_smart_digest(sentiment_data: Dict[str, Any] = None, 
                       portfolio_data: Dict[str, Any] = None,
                       news_data: List[Dict[str, Any]] = None) -> str:
    """
    Create an intelligent digest that adapts content based on session status and data availability.
    """
    try:
        # Check session first
        status = session_manager.check_session_status()
        
        # If session expires soon, prioritize renewal reminder
        if status.get("expires_in_hours", 0) < 2 and status.get("session_active", False):
            return session_manager.create_session_reminder()
        
        digest_parts = [f"📊 *Market Update* - {datetime.now().strftime('%H:%M')} IST"]
        
        # Add sentiment summary if available
        if sentiment_data:
            sentiment_summary = WhatsAppDigestService.create_sentiment_summary(sentiment_data)
            digest_parts.append(sentiment_summary)
        
        # Add portfolio alerts if available
        if portfolio_data:
            portfolio_alert = WhatsAppDigestService.create_portfolio_sentiment_alert(portfolio_data)
            if portfolio_alert:
                digest_parts.append(portfolio_alert)
        
        # Add news digest if available
        if news_data:
            news_digest = WhatsAppDigestService.create_news_digest(news_data)
            digest_parts.append(news_digest)
        
        # Add session status footer
        session_emoji = "✅" if status.get("session_active", False) else "⚠️"
        digest_parts.append(f"{session_emoji} Session: {status.get('expires_in_hours', 0):.1f}h remaining")
        
        return "\n\n".join(digest_parts)
        
    except Exception as e:
        log.error(f"Failed to create smart digest: {e}")
        return f"❌ Digest creation failed: {str(e)}"