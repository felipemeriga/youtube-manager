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

app.include_router(conversations_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
