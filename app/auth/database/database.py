from motor.motor_asyncio import AsyncIOMotorClient

from auth.config import settings


client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db_name]
user_collections = db.get_collection("users")
