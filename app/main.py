from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_v1
from app.core.config import settings
from app.storage.minio import init_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_storage()
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.include_router(api_v1.api_router, prefix=settings.API_V1_PREFIX)
