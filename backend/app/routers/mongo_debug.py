from __future__ import annotations
from fastapi import APIRouter, Query
from app.db.mongo import get_db, _uri, _db_name

router = APIRouter(prefix="/mongo/_debug", tags=["mongo-debug"])

@router.get("/env")
async def mongo_env():
    return {"MONGO_URI": _uri(), "MONGO_DB_NAME": _db_name()}

@router.get("/ping")
async def mongo_ping():
    db = get_db()
    # list collections to verify we're connected to the expected db
    names = await db.list_collection_names()
    return {"db": db.name, "collections": names}

@router.get("/dump/holdings")
async def dump_holdings(user_id: str = Query(...)):
    db = get_db()
    docs = []
    async for d in db["holdings"].find({"user_id": user_id}):
        d["_id"] = str(d["_id"])
        docs.append(d)
    return {"count": len(docs), "docs": docs}