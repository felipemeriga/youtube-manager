import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes.assets import router as assets_router
from routes.chat import router as chat_router
from routes.clips import router as clips_router
from routes.conversations import router as conversations_router
from routes.memories import router as memories_router
from routes.personas import router as personas_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    if settings.database_url:
        from services.thumbnail_graph import get_thumbnail_graph

        await get_thumbnail_graph()
        logger.info("LangGraph thumbnail graph initialized with PostgresSaver")
    else:
        logger.warning("DATABASE_URL not set — thumbnail graph will use fallback")
    yield


app = FastAPI(title="YouTube Manager API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations_router)
app.include_router(assets_router)
app.include_router(chat_router)
app.include_router(personas_router)
app.include_router(memories_router)
app.include_router(clips_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
