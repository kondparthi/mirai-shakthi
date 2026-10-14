import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .guidance import llm
from .routers import admin, artefacts, auth, connect, expert, guidance, profile

logging.basicConfig(level=logging.INFO)

app = FastAPI(title=settings.APP_NAME, version="0.5.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(guidance.router)
app.include_router(admin.router)
app.include_router(artefacts.router)
app.include_router(connect.router)
app.include_router(expert.router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "env": settings.ENV, "ai": "on" if llm.enabled() else "demo"}
