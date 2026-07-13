from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_star_repo
from app.repositories.stars import StarRepository

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
    stars: Annotated[StarRepository, Depends(get_star_repo)],
) -> list[StarSchema]:
    all_stars = await stars.get_all()
    return [StarSchema.model_validate(star) for star in all_stars]


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
    stars: Annotated[StarRepository, Depends(get_star_repo)],
) -> StarSchema:
    existing = await stars.get_by_name(payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Star already exists.",
        )

    star = await stars.create(payload.name)
    await stars.db.commit()
    await stars.db.refresh(star)

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
    stars: Annotated[StarRepository, Depends(get_star_repo)],
) -> StarSchema:
    star = await stars.get_by_id(star_id)
    if star is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Star not found.",
        )

    duplicate = await stars.get_by_name(payload.name)
    if duplicate is not None and duplicate.id != star_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Star name already taken.",
        )

    star = await stars.update(star, payload.name)
    await stars.db.commit()
    await stars.db.refresh(star)

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
    stars: Annotated[StarRepository, Depends(get_star_repo)],
) -> None:
    star = await stars.get_by_id(star_id)
    if star is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Star not found.",
        )

    await stars.delete(star)
    await stars.db.commit()
