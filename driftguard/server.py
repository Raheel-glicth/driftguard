from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from driftguard.api.chatbot import create_chat_router
from driftguard.api.dashboard import create_dashboard_router
from driftguard.sdk import driftguard


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await driftguard.start()
        yield
        await driftguard.stop()

    app = FastAPI(title="DriftGuard", version="0.1.0", lifespan=lifespan)
    app.include_router(create_dashboard_router(driftguard))
    app.include_router(create_chat_router(driftguard))
    return app


app = create_app()


def main() -> None:
    uvicorn.run("driftguard.server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
