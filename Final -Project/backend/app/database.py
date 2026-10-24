from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGO_URL

client = AsyncIOMotorClient(MONGO_URL)
db = client.notes_database
notes_collection = db.get_collection("notes")
