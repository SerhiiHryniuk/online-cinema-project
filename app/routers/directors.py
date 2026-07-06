from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import allowed_roles_user
from app.crud.directors import (
    create_director,
    delete_director,
    get_all_directors,
    get_director_by_id,
    get_director_by_name,
    update_director,
)
from app.db.session import get_db
from app.models.accounts import User, UserGroupEnum
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DirectorSchema]:
    directors = await get_all_directors(db)
    return [
        DirectorSchema.model_validate(director)
        for director in directors
    ]


@router.post(
    "/",
    response_model=DirectorSchema,
    summary="Create a Director",
    description="Create a new director. Moderator or admin only.",
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        409: {"description": "Conflict - Director already exists."},
    },
)
async def create_new_director(
    payload: DirectorCreateSchema,
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
) -> DirectorSchema:
    existing = await get_director_by_name(db, payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Director already exists.",
        )

    director = await create_director(db, payload.name)
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
        409: {"description": "Conflict - Director name already taken."},
    },
)
async def update_existing_director(
    director_id: int,
    payload: DirectorCreateSchema,
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
) -> DirectorSchema:
    director = await get_director_by_id(db, director_id)
    if director is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Director not found.",
        )

    duplicate = await get_director_by_name(db, payload.name)
    if duplicate is not None and duplicate.id != director_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Director name already taken.",
        )

    director = await update_director(db, director, payload.name)
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
    director = await get_director_by_id(db, director_id)
    if director is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Director not found.",
        )

    await delete_director(db, director)
    await db.commit()
