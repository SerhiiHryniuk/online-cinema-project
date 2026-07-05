from fastapi import APIRouter

from app.routers.accounts import router as accounts_router
from app.routers.profiles import router as profiles_router

api_router = APIRouter()

api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
api_router.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
