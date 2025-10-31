# backend/app/routers/__init__.py
"""
Router modules for API endpoints
"""

# Core functionality
from . import health
from . import news
from . import sentiment
from . import signal
from . import price
from . import chart
from . import analysis

# MongoDB routers
from . import auth
from . import mongo_users
from . import mongo_portfolio_v2
from . import mongo_debug

# ML/AI routers
from . import recommender

# Debug routers
from . import debug_providers

# Import enhanced debug if it exists
try:
    from . import debug_enhanced
except ImportError:
    debug_enhanced = None

__all__ = [
    "health",
    "news",
    "sentiment",
    "signal",
    "price",
    "chart",
    "analysis",
    "auth",
    "mongo_users",
    "mongo_portfolio_v2",
    "mongo_debug",
    "recommender",
    "debug_providers",
    "debug_enhanced"
]