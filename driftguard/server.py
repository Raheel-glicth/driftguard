from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from driftguard.api.chatbot import create_chat_router
from driftguard.api.dashboard import create_dashboard_router
from driftguard.sdk import driftguard


def create_app() -> FastAPI:
    app = FastAPI(title="DriftGuard", version="0.1.0")
    app.include_router(create_dashboard_router(driftguard))
    app.include_router(create_chat_router(driftguard))

    @app.on_event("startup")
    async def startup() -> None:
        await driftguard.start()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await driftguard.stop()

    return app


app = create_app()


def main() -> None:
    uvicorn.run("driftguard.server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
