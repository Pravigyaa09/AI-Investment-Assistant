from __future__ import annotations
from datetime import datetime
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source, _handler):
        # Pydantic v2: minimal serializer/deserializer
        from pydantic import GetCoreSchemaHandler
        from pydantic_core import core_schema
        return core_schema.no_info_before_validator_function(
            cls.validate,
            core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.str_schema()
            ])
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(str(v))
        except Exception as e:
            raise ValueError("Invalid ObjectId") from e

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema.update(type="string")
        return json_schema

class MongoBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True, json_encoders={ObjectId: str})

class UserIn(MongoBase):
    name: str
    email: str

class UserOut(MongoBase):
    id: PyObjectId = Field(alias="_id")
    name: str
    email: str

class HoldingIn(MongoBase):
    user_id: PyObjectId
    ticker: str
    quantity: float
    avg_cost: float

class HoldingOut(MongoBase):
    id: PyObjectId = Field(alias="_id")
    user_id: PyObjectId
    ticker: str
    quantity: float
    avg_cost: float

class ScoreIn(MongoBase):
    ticker: str
    score: float
    label: str
    asof: datetime = Field(default_factory=datetime.utcnow)

class ScoreOut(MongoBase):
    id: PyObjectId = Field(alias="_id")
    ticker: str
    score: float
    label: str
    asof: datetime
