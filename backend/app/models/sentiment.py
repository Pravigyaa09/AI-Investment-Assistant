from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from datetime import datetime
from app.db.base import Base

class Sentiment(Base):
    __tablename__ = "sentiments"
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("articles.id"), index=True, nullable=True)
    label = Column(String(8))   # 'positive', 'neutral', or 'negative'
    score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
