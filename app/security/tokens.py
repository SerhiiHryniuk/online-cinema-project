from datetime import timedelta, datetime, UTC
from typing import Any

import jwt

from app.core.config import settings
from app.exceptions import InvalidTokenTypeError
from app.security.utils import generate_secure_token


def _create_jwt_token(
    user_id: int,
    expires_delta: timedelta,
    token_type: str
) -> str:
    time_now = datetime.now(tz=UTC)

    token_data = {
        "sub": str(user_id),
        "exp": time_now + expires_delta,
        "type": token_type,
        "iat": time_now,
        "jti": generate_secure_token(16)
    }

    return jwt.encode(
        token_data,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def create_access_token(
    user_id: int,
    expires_delta: timedelta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
) -> str:
    return _create_jwt_token(
        user_id,
        expires_delta,
        "access"
    )


def create_refresh_token(
    user_id: int,
    expires_delta: timedelta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
) -> str:

    return _create_jwt_token(
        user_id,
        expires_delta,
        "refresh"
    )


def decode_token(token: str, token_type: str) -> dict[str, Any]:
    decoded_data = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    if decoded_data["type"] != token_type:
        raise InvalidTokenTypeError("Invalid token type")

    return decoded_data
