"""MongoDB database connection"""
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings


class Database:
    """Database connection manager"""
    client: AsyncIOMotorClient = None
    database = None


db = Database()


async def connect_to_mongo():
    """Connect to MongoDB"""
    db.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db.database = db.client[settings.DATABASE_NAME]
    print(f"Connected to MongoDB: {settings.MONGODB_URL}")
    print(f"Database: {settings.DATABASE_NAME}")

    # One-time migration: set existing users without a role to "executive"
    result = await db.database.users.update_many(
        {"role": {"$exists": False}},
        {"$set": {"role": "executive"}},
    )
    if result.modified_count:
        print(f"[Migration] Set role='executive' on {result.modified_count} existing users")


async def close_mongo_connection():
    """Close MongoDB connection"""
    if db.client:
        db.client.close()
        print("Disconnected from MongoDB")


def get_database():
    """Get database instance"""
    return db.database

