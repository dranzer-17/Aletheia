# This file will handle MongoDB integration for deepfake results.
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Any
from config import MONGO_URI, MONGO_DB

# Use shared database connection
from database import db

collection = db["deepfake_results"]

async def save_result(result: Dict[str, Any]):
    await collection.insert_one(result)

async def get_results():
    return await collection.find().to_list(length=None)
