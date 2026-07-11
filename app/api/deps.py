from typing import Annotated, Any, Callable, Coroutine

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app import crud
from app.db.session import get_db
from app.models import User
from app.repositories.certifications import CertificationRepository
from app.repositories.comments import CommentRepository
from app.repositories.directors import DirectorRepository
from app.repositories.favorites import FavoriteRepository
from app.repositories.genres import GenreRepository
from app.repositories.likes import LikeRepository
from app.repositories.movies import MovieRepository
from app.repositories.notifications import NotificationRepository
from app.repositories.ratings import RatingRepository
from app.repositories.stars import StarRepository
from app.security.tokens import decode_token
from app.services.comments import CommentService

bearer_scheme = HTTPBearer()


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> User:
    token = credentials.credentials
    try:
        token_data = decode_token(token=token, token_type="access")
        user_id = int(token_data["sub"])
    except Exception as e:
        logger.error(e)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user = await crud.get_user_with_group_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    return user


def allowed_roles_user(*roles: Any) -> Callable[[User], Coroutine[Any, Any, User]]:
    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.group.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
        return user
    return checker


async def get_star_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StarRepository:
    return StarRepository(db)


async def get_genre_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GenreRepository:
    return GenreRepository(db)


async def get_director_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DirectorRepository:
    return DirectorRepository(db)


async def get_certification_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CertificationRepository:
    return CertificationRepository(db)


async def get_movie_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MovieRepository:
    return MovieRepository(db)


async def get_favorite_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FavoriteRepository:
    return FavoriteRepository(db)


async def get_comment_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommentRepository:
    return CommentRepository(db)


async def get_notification_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationRepository:
    return NotificationRepository(db)


async def get_comment_service(
    comments: Annotated[CommentRepository, Depends(get_comment_repo)],
    notifications: Annotated[NotificationRepository, Depends(get_notification_repo)],
) -> CommentService:
    return CommentService(comments, notifications)


async def get_like_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LikeRepository:
    return LikeRepository(db)


async def get_rating_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RatingRepository:
    return RatingRepository(db)
