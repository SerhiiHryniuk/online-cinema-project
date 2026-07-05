from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app import crud
from app.db.session import get_db
from app.models import User
from app.security.tokens import decode_token

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


def allowed_roles_user(*roles):
    async def checker(user: Annotated[User, Depends(get_current_user)]):
        if user.group.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )
        return user
    return checker
