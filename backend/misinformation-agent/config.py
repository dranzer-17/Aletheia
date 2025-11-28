import os
from dotenv import load_dotenv

load_dotenv()

APP_CONFIG = {
    "GNEWS_API_KEY": os.getenv("GNEWS_API_KEY"),
    "GNEWS_API_BASE_URL": "https://gnews.io/api/v4/",
    "GOOGLE_CLOUD_API_KEY": os.getenv("GOOGLE_CLOUD_API_KEY"),
    "LLM_MODEL_NAME": os.getenv("LLM_MODEL_NAME", "gemini-1.5-flash"),
    "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY"),
    "SERPAPI_API_KEY": os.getenv("SERPAPI_API_KEY"),
    "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
    "HUGGINGFACE_API_KEY": os.getenv("HUGGINGFACE_API_KEY"),
}