from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument

from config import MONGO_URI, MONGO_DB
from logger import get_logger

logger = get_logger(__name__)

logger.info(f"Connecting to MongoDB: {MONGO_URI.split('@')[-1] if '@' in MONGO_URI else MONGO_URI}")
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB]
logger.info(f"Connected to database: {MONGO_DB}")


async def get_next_sequence(name: str) -> int:
    doc = await db["counters"].find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
        projection={"seq": 1, "_id": 0},
    )
    logger.debug(f"Generated next sequence for '{name}': {doc['seq']}")
    return doc["seq"]