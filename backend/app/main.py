import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .guidance import llm
from .routers import access, admin, artefacts, auth, connect, enrol, expert, guidance, masters, profile, programme, training, training_me

logging.basicConfig(level=logging.INFO)

app = FastAPI(title=settings.APP_NAME, version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(guidance.router)
app.include_router(admin.router)
app.include_router(artefacts.router)
app.include_router(connect.router)
app.include_router(expert.router)
# Phase 1 – Core platform
app.include_router(masters.router)
app.include_router(access.router)
app.include_router(programme.router)
app.include_router(programme.files)
app.include_router(enrol.router)
app.include_router(training_me.router)  # before training.router: /training/me is more specific
app.include_router(training_me.public)
app.include_router(training.router)
app.include_router(training.files)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "env": settings.ENV, "ai": "on" if llm.enabled() else "demo"}
