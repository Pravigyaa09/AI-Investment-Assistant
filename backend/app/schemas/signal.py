from pydantic import BaseModel
from typing import Dict

class SignalOut(BaseModel):
    ticker: str
    counts: Dict[str, int]
    action: str
    confidence: float
