from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

app = FastAPI(title="YouTube Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from routes.conversations import router as conversations_router
from routes.assets import router as assets_router
from routes.chat import router as chat_router

app.include_router(conversations_router)
app.include_router(assets_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
