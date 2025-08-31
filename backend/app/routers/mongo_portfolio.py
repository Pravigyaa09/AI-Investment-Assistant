from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.mongo import get_db as get_mongo_db
from app.schemas.mongo_models import HoldingUpsert, PortfolioSummary
from app.services.market_data import get_quote
from app.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/mongo", tags=["mongo"])

@router.post("/holdings", summary="Upsert a holding (user_id + ticker)")
async def upsert_holding(payload: HoldingUpsert, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    t = payload.ticker.upper().strip()
    if not t:
        raise HTTPException(status_code=400, detail="ticker required")

    # do the upsert and log result for visibility
    res = await db.holdings.update_one(
        {"user_id": payload.user_id, "ticker": t},
        {"$set": {
            "user_id": payload.user_id,
            "ticker": t,
            "quantity": float(payload.quantity),
            "avg_cost": float(payload.avg_cost),
        }},
        upsert=True,
    )
    log.info("upsert holdings matched=%s modified=%s upserted_id=%s",
             res.matched_count, res.modified_count, getattr(res, "upserted_id", None))

    doc = await db.holdings.find_one({"user_id": payload.user_id, "ticker": t})
    if not doc:
        # if this ever happens, we’re looking at a different DB or query mismatch
        raise HTTPException(status_code=500, detail="Upserted but could not re-read document")

    doc["_id"] = str(doc["_id"])
    return {"upsert": {
                "matched": res.matched_count,
                "modified": res.modified_count,
                "upserted_id": str(res.upserted_id) if getattr(res, "upserted_id", None) else None
            },
            "doc": doc}

@router.get("/holdings", summary="List holdings (computed MV/PNL)", response_model=list)
async def list_holdings(user_id: str = Query(...), db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    cursor = db.holdings.find({"user_id": user_id})
    out = []
    async for h in cursor:
        t = h["ticker"]
        qty = float(h["quantity"])
        avg = float(h["avg_cost"])
        last = float(get_quote(t)) or 0.0
        mv = last * qty
        cost = avg * qty
        pnl_abs = mv - cost
        pnl_pct = (pnl_abs / cost) if cost > 0 else 0.0
        h["_id"] = str(h["_id"])
        h.update({
            "last_price": round(last, 2),
            "market_value": round(mv, 2),
            "pnl_abs": round(pnl_abs, 2),
            "pnl_pct": round(pnl_pct, 4),
        })
        out.append(h)
    return out

@router.get("/portfolio/value", summary="Portfolio summary", response_model=PortfolioSummary)
async def portfolio_value(user_id: str = Query(...), db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    cursor = db.holdings.find({"user_id": user_id})
    positions = []
    total_cost = total_value = 0.0
    async for h in cursor:
        t = h["ticker"]
        qty = float(h["quantity"])
        avg = float(h["avg_cost"])
        last = float(get_quote(t)) or 0.0
        mv = last * qty
        cost = avg * qty
        pnl_abs = mv - cost
        pnl_pct = (pnl_abs / cost) if cost > 0 else 0.0
        positions.append({
            "_id": str(h["_id"]),
            "user_id": user_id,
            "ticker": t,
            "quantity": qty,
            "avg_cost": avg,
            "last_price": round(last, 2),
            "market_value": round(mv, 2),
            "pnl_abs": round(pnl_abs, 2),
            "pnl_pct": round(pnl_pct, 4),
        })
        total_cost += cost
        total_value += mv

    total_pnl_abs = total_value - total_cost
    total_pnl_pct = (total_pnl_abs / total_cost) if total_cost > 0 else 0.0
    return {
        "user_id": user_id,
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_pnl_abs": round(total_pnl_abs, 2),
        "total_pnl_pct": round(total_pnl_pct, 4),
        "positions": positions,
    }
