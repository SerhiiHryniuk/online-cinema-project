from fastapi import APIRouter

from app.routers.accounts import router as accounts_router
from app.routers.favorites import router as favorites_router
from app.routers.likes import router as likes_router
from app.routers.movies import router as movies_router
from app.routers.profiles import router as profiles_router
from app.routers.ratings import router as ratings_router

api_router = APIRouter()

api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
api_router.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
api_router.include_router(
    favorites_router, prefix="/movies", tags=["favorites"]
)
api_router.include_router(movies_router, prefix="/movies", tags=["movies"])
api_router.include_router(likes_router, prefix="/movies", tags=["likes"])
api_router.include_router(ratings_router, prefix="/movies", tags=["ratings"])
