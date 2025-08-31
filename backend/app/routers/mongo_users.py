from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.mongo import get_mongo_db
from app.schemas.mongo_models import UserCreate

router = APIRouter(prefix="/mongo/users", tags=["mongo"])

@router.post("", summary="Create or get a user by email")
async def create_user(payload: UserCreate, db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    doc = await db.users.find_one({"email": payload.email})
    if doc:
        # normalize _id to string for JSON
        doc["_id"] = str(doc["_id"])
        return doc

    res = await db.users.insert_one({"email": payload.email, "name": payload.name})
    doc = await db.users.find_one({"_id": res.inserted_id})
    doc["_id"] = str(doc["_id"])
    return doc
