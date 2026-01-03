import os
from dotenv import load_dotenv

load_dotenv()

# Database Vars
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_HOST = os.getenv("MONGO_HOST")
MONGO_PORT = os.getenv("MONGO_PORT")
MONGO_DB = os.getenv("MONGO_DB")

# Security Vars
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
ASSEMBLY_AI_API_KEY = os.getenv("ASSEMBLY_AI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
SIGHTENGINE_API_USER = os.getenv("SIGHTENGINE_API_USER")
SIGHTENGINE_API_SECRET = os.getenv("SIGHTENGINE_API_SECRET")

# Reddit API Vars
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "TrendsBot/1.0 by YourUsername")

# GNews API Vars
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
GNEWS_API_BASE_URL = os.getenv("GNEWS_API_BASE_URL", "https://gnews.io/api/v4/")

# Telegram API Vars
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
# Use absolute path from the backend directory for telegram session
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
TELEGRAM_SESSION_PATH = os.getenv("TELEGRAM_SESSION_PATH", os.path.join(_BACKEND_DIR, "telegram.session"))
TELEGRAM_CHANNELS = os.getenv("TELEGRAM_CHANNELS")


# Validation
if not MONGO_USER or not SECRET_KEY or not MONGO_PORT:
    raise ValueError("❌ ERROR: Missing values in .env file (Check MONGO_USER, PORT, or SECRET_KEY)")

# Construct URI
MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}"