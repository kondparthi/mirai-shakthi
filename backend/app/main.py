import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .guidance import llm
from .routers import (access, admin, artefacts, auth, books, connect, mentoring, dpr, dpr_me, enrol, expert, guidance, market, masters, profile, programme, setup,
                      setup_portal, training, training_me)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title=settings.APP_NAME, version="1.7.0")
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
app.include_router(dpr_me.router)  # before dpr.router: /dpr/me is more specific
app.include_router(dpr.router)
app.include_router(setup_portal.me_router)  # before setup.router: /setup/me is more specific
app.include_router(setup_portal.supplier_router)
app.include_router(setup.router)
app.include_router(market.router)
app.include_router(market.public)
app.include_router(books.router)
app.include_router(books.public)
app.include_router(mentoring.router)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "env": settings.ENV, "ai": "on" if llm.enabled() else "demo"}
