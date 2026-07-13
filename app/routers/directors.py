from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_director_repo
from app.db.session import get_db
from app.repositories.directors import DirectorRepository
from app.schemas.directors import (
    DirectorCreateSchema,
    DirectorSchema,
)

router = APIRouter()


@router.get(
    "/",
    response_model=list[DirectorSchema],
    summary="List Directors",
    description="Return all directors.",
    status_code=status.HTTP_200_OK,
)
async def list_directors(
    directors: Annotated[DirectorRepository, Depends(get_director_repo)],
) -> list[DirectorSchema]:
    all_directors = await directors.get_all()
    return [
        DirectorSchema.model_validate(director)
        for director in all_directors
    ]


@router.post(
    "/",
    response_model=DirectorSchema,
    summary="Create a Director",
    description="Create a new director. Moderator or admin only.",
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        422: {"description": "Unprocessable - Director already exists."},
    },
)
async def create_new_director(
    payload: DirectorCreateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    directors: Annotated[DirectorRepository, Depends(get_director_repo)],
) -> DirectorSchema:
    existing = await directors.get_by_name(payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Director already exists.",
        )

    director = await directors.create(payload.name)
    await db.commit()
    await db.refresh(director)

    return DirectorSchema.model_validate(director)


@router.put(
    "/{director_id}/",
    response_model=DirectorSchema,
    summary="Update a Director",
    description="Rename a director. Moderator or admin only.",
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Director does not exist."},
        422: {"description": "Unprocessable - Name already taken."},
    },
)
async def update_existing_director(
    director_id: int,
    payload: DirectorCreateSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    directors: Annotated[DirectorRepository, Depends(get_director_repo)],
) -> DirectorSchema:
    director = await directors.get_by_id(director_id)
    if director is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Director not found.",
        )

    duplicate = await directors.get_by_name(payload.name)
    if duplicate is not None and duplicate.id != director_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Director name already taken.",
        )

    director = await directors.update(director, payload.name)
    await db.commit()
    await db.refresh(director)

    return DirectorSchema.model_validate(director)


@router.delete(
    "/{director_id}/",
    summary="Delete a Director",
    description="Delete a director. Moderator or admin only.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Director does not exist."},
    },
)
async def delete_existing_director(
    director_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    directors: Annotated[DirectorRepository, Depends(get_director_repo)],
) -> None:
    director = await directors.get_by_id(director_id)
    if director is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Director not found.",
        )

    await directors.delete(director)
    await db.commit()
