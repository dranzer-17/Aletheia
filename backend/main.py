import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from logger import get_logger
from auth.router import router as auth_router
# from dashboard.router import router as dashboard_router (Future)

MISINFO_DIR = Path(__file__).resolve().parent / "misinformation-agent"
if str(MISINFO_DIR) not in sys.path:
    sys.path.append(str(MISINFO_DIR))

from router import router as claims_router  # type: ignore  # noqa: E402
from trends.router import router as trends_router  # type: ignore  # noqa: E402
from trends.scheduler import setup_scheduler, shutdown_scheduler  # type: ignore  # noqa: E402
from globe.router import router as globe_router  # type: ignore  # noqa: E402
from social_graph.router import router as social_graph_router  # type: ignore  # noqa: E402
from tts.router import router as tts_router  # type: ignore  # noqa: E402
from ai_detection.router import router as ai_detection_router  # type: ignore  # noqa: E402
from chatbot.router import router as chatbot_router  # type: ignore  # noqa: E402
from deepfake.router import router as deepfake_router  # type: ignore  # noqa: E402

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting application...")
    setup_scheduler()
    logger.info("Application started successfully")
    yield
    # Shutdown
    logger.info("Shutting down application...")
    shutdown_scheduler()
    logger.info("Application shut down")


app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods including OPTIONS
    allow_headers=["*"],  # Allows all headers
)

app.include_router(auth_router)
app.include_router(claims_router)
app.include_router(trends_router)
app.include_router(globe_router)
app.include_router(social_graph_router)
app.include_router(tts_router)
app.include_router(ai_detection_router, prefix="/ai-detection", tags=["AI Detection"])
app.include_router(chatbot_router, prefix="/chatbot", tags=["Chatbot"])
app.include_router(deepfake_router, prefix="/deepfake", tags=["Deepfake Detection"])
# app.include_router(dashboard_router)

@app.get("/")
def home():
    logger.info("Health check endpoint accessed")
    return {"message": "System Online"}