from datetime import datetime, timezone
from typing import cast
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.session import get_db
from app.models.accounts import UserGroupEnum
from app.schemas.accounts import (
    MessageResponseSchema,
    ResendActivationRequestSchema,
    UserActivationRequestSchema,
    UserRegistrationRequestSchema,
    UserRegistrationResponseSchema,
)
from app.security import hash_password
from app.core.config import settings
from app.tasks.emails import (
    send_activation_complete_email_task,
    send_activation_email_task,
)

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
