from pydantic import BaseModel
from typing import List

class SentimentIn(BaseModel):
    texts: List[str]

class SentimentOut(BaseModel):
    label: str
    score: float

