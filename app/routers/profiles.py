from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_profile_repo
from app.db.session import get_db
from app.exceptions import MinioConnectionError, MinioFileUploadError
from app.models.accounts import User
from app.repositories.profiles import ProfileRepository
from app.schemas.profiles import ProfileResponseSchema, ProfileUpdateRequestSchema
from app.storage.minio import delete_avatar, get_avatar_url, upload_avatar

router = APIRouter()


async def _build_response(profile: Any) -> ProfileResponseSchema:
    response = ProfileResponseSchema.model_validate(profile)
    response.avatar_url = await get_avatar_url(profile.avatar)
    return response


@router.get(
    "/me/",
    response_model=ProfileResponseSchema,
    summary="Get Current User Profile",
    description="Return the profile of the currently authenticated user, creating an empty one if it doesn't exist yet.",
    status_code=status.HTTP_200_OK,
)
async def get_my_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    profiles: Annotated[ProfileRepository, Depends(get_profile_repo)],
    user: Annotated[User, Depends(get_current_user)],
) -> ProfileResponseSchema:
    profile = await profiles.get_by_user_id(user.id)
    if profile is None:
        profile = await profiles.create(user.id)
        await db.commit()
        await db.refresh(profile)

    return await _build_response(profile)


@router.put(
    "/me/",
    response_model=ProfileResponseSchema,
    summary="Update Current User Profile",
    description="Update profile fields and, optionally, upload/replace the avatar for the currently authenticated user.",
    status_code=status.HTTP_200_OK,
    responses={
        422: {
            "description": "Unprocessable Entity - Invalid profile fields or avatar.",
        },
        502: {
            "description": "Bad Gateway - Failed to upload the avatar to the storage.",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to upload avatar."}
                }
            },
        },
        503: {
            "description": "Service Unavailable - The storage service is unreachable.",
            "content": {
                "application/json": {
                    "example": {"detail": "Storage is currently unavailable."}
                }
            },
        },
    },
)
async def update_my_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    profiles: Annotated[ProfileRepository, Depends(get_profile_repo)],
    user: Annotated[User, Depends(get_current_user)],
    profile_data: Annotated[ProfileUpdateRequestSchema, Depends(ProfileUpdateRequestSchema.as_form)],
) -> ProfileResponseSchema:
    profile = await profiles.get_by_user_id(user.id)
    if profile is None:
        profile = await profiles.create(user.id)

    old_avatar = profile.avatar
    new_avatar_key = None

    if profile_data.avatar is not None:
        file_data = await profile_data.avatar.read()
        try:
            new_avatar_key = await upload_avatar(
                str(user.id), file_data, profile_data.avatar.content_type  # type: ignore[arg-type]
            )
        except MinioConnectionError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage is currently unavailable.",
            )
        except MinioFileUploadError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to upload avatar.",
            )

    update_data = profile_data.model_dump(exclude_unset=True, exclude={"avatar"})
    if new_avatar_key is not None:
        update_data["avatar"] = new_avatar_key

    try:
        await profiles.update(profile, **update_data)
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the profile.",
        )

    if new_avatar_key and old_avatar:
        await delete_avatar(old_avatar)

    return await _build_response(profile)
