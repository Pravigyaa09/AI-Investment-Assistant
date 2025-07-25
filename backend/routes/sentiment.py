from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Union, List
from utils.sentiment_model import run_finbert

router = APIRouter()

class SentimentRequest(BaseModel):
    text: Union[str, List[str]]

@router.post("/analyze")
def analyze_sentiment(req: SentimentRequest):
    if isinstance(req.text, str) and not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    result = run_finbert(req.text)

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result

@router.get("/")
def test():
    return {"message": "Sentiment route working"}
