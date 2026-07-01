from fastapi import FastAPI

from app.api import api_v1
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME)

app.include_router(api_v1.api_router, prefix=settings.API_V1_PREFIX)
