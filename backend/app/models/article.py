from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from app.db.base import Base

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True)
    ticker = Column(String(12), index=True)
    title = Column(Text, nullable=False)
    source = Column(String(64))
    url = Column(Text)
    published_at = Column(DateTime)
    raw_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
