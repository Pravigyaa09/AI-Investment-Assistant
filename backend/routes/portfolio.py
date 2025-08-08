from fastapi import APIRouter, Request, HTTPException
from logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/")
async def test_portfolio(request: Request):
    logger.info("GET request received at '/' route from %s", request.client.host)
    
    try:
        logger.debug("Health check route triggered.")
        return {"message": "Portfolio route working"}
    
    except Exception as e:
        logger.exception("Unexpected error in '/' route")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/")
async def handle_portfolio(request: Request):
    logger.info("POST request received at /api/portfolio from %s", request.client.host)
    try:
        data = await request.json()
        logger.debug("Received request data: %s", data)
        return {"message": "Portfolio processed", "data": data}
    except Exception:
        logger.exception("Error processing portfolio request.")
        raise HTTPException(status_code=500, detail="Internal server error")


    try:
        data = await request.json()
        logger.debug("Received request data: %s", data)

        # Simulate processing (replace this with actual logic)
        # result = process_portfolio(data)

        logger.info("Portfolio processed successfully.")
        return {"message": "Portfolio processed", "data": data}

    except Exception as e:
        logger.exception("Error processing portfolio request.")
        raise HTTPException(status_code=500, detail="Internal server error")
