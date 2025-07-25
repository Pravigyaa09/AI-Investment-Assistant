from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def test_portfolio():
    return {"message": "Portfolio route working"}
