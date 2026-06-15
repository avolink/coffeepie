from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGO_URI, MONGO_DB_NAME

# Shared MongoDB client and database
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB_NAME]
