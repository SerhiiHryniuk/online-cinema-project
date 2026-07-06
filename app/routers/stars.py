from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import allowed_roles_user
from app.crud.stars import (
    create_star,
    delete_star,
    get_all_stars,
    get_star_by_id,
    get_star_by_name,
    update_star,
)
from app.db.session import get_db
from app.models.accounts import User, UserGroupEnum
from app.schemas.stars import StarCreateSchema, StarSchema

router = APIRouter()


@router.get(
    "/",
    response_model=list[StarSchema],
    summary="List Stars",
    description="Return all stars.",
    status_code=status.HTTP_200_OK,
)
async def list_stars(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[StarSchema]:
    stars = await get_all_stars(db)
    return [StarSchema.model_validate(star) for star in stars]


@router.post(
    "/",
    response_model=StarSchema,
    summary="Create a Star",
    description="Create a new star. Moderator or admin only.",
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        422: {"description": "Unprocessable - Star already exists."},
    },
)
async def create_new_star(
    payload: StarCreateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[
        User,
        Depends(
            allowed_roles_user(
                UserGroupEnum.MODERATOR,
                UserGroupEnum.ADMIN,
            )
        ),
    ],
) -> StarSchema:
    existing = await get_star_by_name(db, payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Star already exists.",
        )

    star = await create_star(db, payload.name)
    await db.commit()
    await db.refresh(star)

    return StarSchema.model_validate(star)


@router.put(
    "/{star_id}/",
    response_model=StarSchema,
    summary="Update a Star",
    description="Rename a star. Moderator or admin only.",
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Star does not exist."},
        422: {"description": "Unprocessable - Star name already taken."},
    },
)
async def update_existing_star(
    star_id: int,
    payload: StarCreateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[
        User,
        Depends(
            allowed_roles_user(
                UserGroupEnum.MODERATOR,
                UserGroupEnum.ADMIN,
            )
        ),
    ],
) -> StarSchema:
    star = await get_star_by_id(db, star_id)
    if star is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Star not found.",
        )

    duplicate = await get_star_by_name(db, payload.name)
    if duplicate is not None and duplicate.id != star_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Star name already taken.",
        )

    star = await update_star(db, star, payload.name)
    await db.commit()
    await db.refresh(star)

    return StarSchema.model_validate(star)


@router.delete(
    "/{star_id}/",
    summary="Delete a Star",
    description="Delete a star. Moderator or admin only.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Star does not exist."},
    },
)
async def delete_existing_star(
    star_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[
        User,
        Depends(
            allowed_roles_user(
                UserGroupEnum.MODERATOR,
                UserGroupEnum.ADMIN,
            )
        ),
    ],
) -> None:
    star = await get_star_by_id(db, star_id)
    if star is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Star not found.",
        )

    await delete_star(db, star)
    await db.commit()
