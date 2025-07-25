from fastapi import FastAPI
from routes import sentiment, portfolio

app = FastAPI()

app.include_router(sentiment.router, prefix="/api/sentiment")
app.include_router(portfolio.router, prefix="/api/portfolio")

@app.get("/")
def read_root():
    return {"message": "Backend is working!"}
