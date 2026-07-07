from fastapi import APIRouter

from app.routers.accounts import router as accounts_router
from app.routers.certifications import router as certifications_router
from app.routers.comments import router as comments_router
from app.routers.directors import router as directors_router
from app.routers.favorites import router as favorites_router
from app.routers.genres import router as genres_router
from app.routers.likes import router as likes_router
from app.routers.movie_admin import router as movie_admin_router
from app.routers.movies import router as movies_router
from app.routers.notifications import router as notifications_router
from app.routers.profiles import router as profiles_router
from app.routers.ratings import router as ratings_router
from app.routers.stars import router as stars_router
from app.routers.carts import router as carts_router

api_router = APIRouter()

api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
api_router.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
api_router.include_router(carts_router, prefix="/carts", tags=["carts"])
api_router.include_router(
    favorites_router, prefix="/movies", tags=["favorites"]
)
api_router.include_router(movies_router, prefix="/movies", tags=["movies"])
api_router.include_router(likes_router, prefix="/movies", tags=["likes"])
api_router.include_router(ratings_router, prefix="/movies", tags=["ratings"])
api_router.include_router(
    comments_router, prefix="/movies", tags=["comments"]
)
api_router.include_router(
    movie_admin_router, prefix="/movies", tags=["movie-admin"]
)
api_router.include_router(
    notifications_router, prefix="/notifications", tags=["notifications"]
)
api_router.include_router(genres_router, prefix="/genres", tags=["genres"])
api_router.include_router(stars_router, prefix="/stars", tags=["stars"])
api_router.include_router(
    directors_router, prefix="/directors", tags=["directors"]
)
api_router.include_router(
    certifications_router,
    prefix="/certifications",
    tags=["certifications"],
)
