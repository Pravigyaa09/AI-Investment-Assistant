from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional

class ArticleOut(BaseModel):
    ticker: str
    title: str
    source: Optional[str] = None
    url: Optional[HttpUrl] = None
    published_at: Optional[datetime] = None
