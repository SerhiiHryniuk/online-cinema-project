from datetime import datetime, timezone
from typing import cast, Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import RefreshTokenModel
from app.models.accounts import UserGroupEnum, User
from app.schemas.accounts import (
    MessageResponseSchema,
    ResendActivationRequestSchema,
    UserActivationRequestSchema,
    UserRegistrationRequestSchema,
    UserRegistrationResponseSchema, TokenResponseSchema, UserLoginSchema, TokenRefreshSchema,
)
from app.security import hash_password
from app.core.config import settings
from app.security.tokens import create_access_token, create_refresh_token, decode_token
from app.tasks.emails import (
    send_activation_complete_email_task,
    send_activation_email_task,
)
from loguru import logger

router = APIRouter()


def _build_activation_link(email: str, token: str) -> str:
    query = urlencode({"email": email, "token": token})
    return f"{settings.BASE_URL}/api/v1/accounts/activate/?{query}"


@router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    summary="User Registration",
    description="Register a new user with an email and password.",
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {
            "description": "Conflict - User with this email already exists.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "A user with this email test@example.com already exists."
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - An error occurred during user creation.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred during user creation."
                    }
                }
            },
        },
    }
)
async def register_user(
        user_data: UserRegistrationRequestSchema,
        db: AsyncSession = Depends(get_db),
) -> UserRegistrationResponseSchema:
    existing_user = await crud.get_user_by_email(db, str(user_data.email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with this email {user_data.email} already exists."
        )

    user_group = await crud.get_user_group_by_name(db, UserGroupEnum.USER)
    if not user_group:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default user group not found."
        )

    try:
        new_user = await crud.create_user(
            db,
            email=str(user_data.email),
            hashed_password=hash_password(user_data.password),
            group_id=user_group.id,
        )
        activation_token = await crud.create_activation_token(db, user_id=new_user.id)

        await db.commit()
        await db.refresh(new_user)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation."
        ) from e
    else:
        activation_link = _build_activation_link(str(new_user.email), activation_token.token)
        send_activation_email_task.delay(str(new_user.email), activation_link)
        return UserRegistrationResponseSchema.model_validate(new_user)


async def _activate_user_account(
        email: str,
        token: str,
        db: AsyncSession,
) -> MessageResponseSchema:
    token_record = await crud.get_activation_token_with_user(
        db, email=email, token=token
    )

    now_utc = datetime.now(timezone.utc)
    if not token_record or cast(datetime, token_record.expires_at).replace(tzinfo=timezone.utc) < now_utc:
        if token_record:
            await crud.delete_activation_token(db, token_record)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token."
        )

    user = token_record.user
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active."
        )

    await crud.activate_user(user)
    await crud.delete_activation_token(db, token_record)
    await db.commit()

    login_link = f"{settings.BASE_URL}/api/v1/accounts/login/"
    send_activation_complete_email_task.delay(str(user.email), login_link)

    return MessageResponseSchema(message="User account activated successfully.")


@router.post(
    "/activate/",
    response_model=MessageResponseSchema,
    summary="Activate User Account",
    description="Activate a user's account using their email and activation token.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The activation token is invalid or expired, "
                           "or the user account is already active.",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_token": {
                            "summary": "Invalid Token",
                            "value": {
                                "detail": "Invalid or expired activation token."
                            }
                        },
                        "already_active": {
                            "summary": "Account Already Active",
                            "value": {
                                "detail": "User account is already active."
                            }
                        },
                    }
                }
            },
        },
    },
)
async def activate_account(
        activation_data: UserActivationRequestSchema,
        db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    return await _activate_user_account(
        str(activation_data.email), activation_data.token, db
    )


@router.get(
    "/activate/",
    response_model=MessageResponseSchema,
    summary="Activate User Account (via emailed link)",
    description=(
        "Activate a user's account by following the link sent in the "
        "activation email. This is the endpoint the link in the email "
        "actually points to, and it accepts the same email/token pair "
        "as query parameters instead of a JSON body."
    ),
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The activation token is invalid or expired, "
                           "or the user account is already active.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid or expired activation token."}
                }
            },
        },
    },
)
async def activate_account_via_link(
        email: EmailStr = Query(..., description="Email address from the activation link."),
        token: str = Query(..., description="Activation token from the activation link."),
        db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    return await _activate_user_account(str(email), token, db)


@router.post(
    "/resend-activation/",
    response_model=MessageResponseSchema,
    summary="Resend Activation Email",
    description=(
        "Issue a new activation token and resend the activation link, e.g. when "
        "the previous 24-hour link has expired."
    ),
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The user account is already active.",
            "content": {
                "application/json": {
                    "example": {"detail": "User account is already active."}
                }
            },
        },
        404: {
            "description": "Not Found - No user with this email was found.",
            "content": {
                "application/json": {
                    "example": {"detail": "User with this email was not found."}
                }
            },
        },
    },
)
async def resend_activation(
        resend_data: ResendActivationRequestSchema,
        db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    user = await crud.get_user_by_email(db, str(resend_data.email))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email was not found."
        )

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active."
        )

    old_token = await crud.get_activation_token_by_user_id(db, user.id)
    if old_token:
        await crud.delete_activation_token(db, old_token)
        await db.flush()

    new_token = await crud.create_activation_token(db, user_id=user.id)
    await db.commit()

    activation_link = _build_activation_link(str(user.email), new_token.token)
    send_activation_email_task.delay(str(user.email), activation_link)

    return MessageResponseSchema(message="A new activation link has been sent to your email.")


@router.post(
    "/login/",
    response_model=TokenResponseSchema,
    summary="User Login",
    description="Authenticate a user and return access and refresh tokens.",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {
            "description": "Unauthorized - Invalid email or password.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid email or password."
                    }
                }
            },
        },
        403: {
            "description": "Forbidden - User account is not activated.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User account is not activated."
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - An error occurred while processing the request.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An error occurred while processing the request."
                    }
                }
            },
        },
    },
)
async def login(
    login_data: UserLoginSchema,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    user = await crud.authenticate_user(
        db=db,
        email=login_data.email,
        password=login_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated.",
        )

    jwt_refresh_token = create_refresh_token(user_id=user.id)
    try:
        refresh_token = RefreshTokenModel.create(
            user_id=user.id,
            days_valid=settings.REFRESH_TOKEN_EXPIRE_DAYS,
            token=jwt_refresh_token
        )
        db.add(refresh_token)
        await db.flush()
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request.",
        )

    return TokenResponseSchema(
        access_token=create_access_token(user_id=user.id),
        refresh_token=jwt_refresh_token
    )


@router.post(
    "/refresh/",
    response_model=TokenResponseSchema,
    summary="Refresh Access Token",
    description="Invalidates the old refresh token, rotates it, and returns a brand new pair of access and refresh tokens.",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Bad Request - The provided refresh token is malformed, invalid, or expired.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid token"}
                }
            },
        },
        401: {
            "description": "Unauthorized - The refresh token does not exist in the database or is unauthorized.",
            "content": {
                "application/json": {
                    "example": {"detail": "Refresh token not found."}
                }
            },
        },
    },
)
async def refresh(
    refresh_token_data: TokenRefreshSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        decoded_data = decode_token(
            token=refresh_token_data.refresh_token,
            token_type="refresh"
        )
    except Exception as error:
        logger.error(error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token"
        )

    refresh_token_record = await crud.get_refresh_token(db, refresh_token_data.refresh_token)
    if not refresh_token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found.",
        )

    await crud.delete_refresh_token(db, refresh_token_record)

    user_id = int(decoded_data.get("sub"))
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    new_jwt_refresh_token = create_refresh_token(user_id=user_id)
    try:
        new_refresh_token_db = RefreshTokenModel.create(
            user_id=user_id,
            days_valid=settings.REFRESH_TOKEN_EXPIRE_DAYS,
            token=new_jwt_refresh_token
        )
        db.add(new_refresh_token_db)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request.",
        )

    return TokenResponseSchema(
        access_token=create_access_token(user_id=user_id),
        refresh_token=new_jwt_refresh_token
    )


@router.post(
    "/logout/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="User Logout",
    description="Log out the current user by deleting their refresh token from the database, preventing future token refreshes.",
    responses={
        204: {
            "description": "Successfully logged out. No content is returned."
        },
        401: {
            "description": "Unauthorized - Missing/invalid access token or refresh token session already expired.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid token"}
                }
            },
        },
    },
)
async def logout(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)]
) -> None:
    token = await crud.get_refresh_token_by_user_id(db, user.id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    try:
        await crud.delete_refresh_token(db, token)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout."
        )
