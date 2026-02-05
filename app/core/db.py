from motor.motor_asyncio import AsyncIOMotorClient
import os

# MongoDB Connection String
MONGODB_URL = "mongodb+srv://selvamashok1310_db_user:p4u3FUhj4KNmyr0x@cluster0.9lrvakf.mongodb.net/"
DATABASE_NAME = "aadhaar_kyc_db"

client = AsyncIOMotorClient(MONGODB_URL)
db = client[DATABASE_NAME]

# Collections
kyc_records = db.kyc_records
verification_logs = db.verification_logs

async def check_db_connection():
    try:
        await client.admin.command('ismaster')
        return True
    except Exception as e:
        print(f"MongoDB Connection Error: {e}")
        return False
