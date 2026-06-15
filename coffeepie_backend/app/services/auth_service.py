from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from app.config import MONGO_URI, MONGO_DB_NAME, JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from bson import ObjectId

# MongoDB client setup
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB_NAME]
users_collection = db.get_collection("users")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# JWT token creation

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

# User retrieval and authentication

async def get_user_by_email(email: str) -> dict | None:
    return await users_collection.find_one({"email": email})

async def authenticate_user(email: str, password: str) -> dict | None:
    user = await get_user_by_email(email)
    if not user or not verify_password(password, user.get("hashed_password", "")):
        return None
    return user

async def get_user_by_id(user_id: str) -> dict | None:
    return await users_collection.find_one({"_id": ObjectId(user_id)})

# User registration now takes name, email, password
async def create_user(name: str, email: str, password: str) -> dict:
    # Check existing user
    existing = await users_collection.find_one({"email": email})
    if existing:
        raise RuntimeError("Email already registered")
    # Hash password and prepare user document
    hashed = pwd_context.hash(password)
    user = {
        "name": name,
        "email": email,
        "hashed_password": hashed,
        "type": "individual",
        "companyID": None,
        "createdVMs": [],
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    # Insert into Mongo
    result = await users_collection.insert_one(user)
    user["_id"] = result.inserted_id
    return user