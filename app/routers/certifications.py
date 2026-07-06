from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import allowed_roles_user
from app.crud.certifications import (
    create_certification,
    delete_certification,
    get_all_certifications,
    get_certification_by_id,
    get_certification_by_name,
    update_certification,
)
from app.db.session import get_db
from app.models.accounts import User, UserGroupEnum
from app.schemas.certifications import (
    CertificationCreateSchema,
    CertificationSchema,
)

router = APIRouter()


@router.get(
    "/",
    response_model=list[CertificationSchema],
    summary="List Certifications",
    description="Return all certifications.",
    status_code=status.HTTP_200_OK,
)
async def list_certifications(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CertificationSchema]:
    certifications = await get_all_certifications(db)
    return [
        CertificationSchema.model_validate(cert)
        for cert in certifications
    ]


@router.post(
    "/",
    response_model=CertificationSchema,
    summary="Create a Certification",
    description="Create a certification. Moderator or admin only.",
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        422: {
            "description": "Unprocessable - Certification already exists."
        },
    },
)
async def create_new_certification(
    payload: CertificationCreateSchema,
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
) -> CertificationSchema:
    existing = await get_certification_by_name(db, payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Certification already exists.",
        )

    certification = await create_certification(db, payload.name)
    await db.commit()
    await db.refresh(certification)

    return CertificationSchema.model_validate(certification)


@router.put(
    "/{certification_id}/",
    response_model=CertificationSchema,
    summary="Update a Certification",
    description="Rename a certification. Moderator or admin only.",
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Certification does not exist."},
        422: {"description": "Unprocessable - Name already taken."},
    },
)
async def update_existing_certification(
    certification_id: int,
    payload: CertificationCreateSchema,
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
) -> CertificationSchema:
    certification = await get_certification_by_id(
        db, certification_id
    )
    if certification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found.",
        )

    duplicate = await get_certification_by_name(db, payload.name)
    if duplicate is not None and duplicate.id != certification_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Certification name already taken.",
        )

    certification = await update_certification(
        db, certification, payload.name
    )
    await db.commit()
    await db.refresh(certification)

    return CertificationSchema.model_validate(certification)


@router.delete(
    "/{certification_id}/",
    summary="Delete a Certification",
    description="Delete a certification. Moderator or admin only.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Forbidden - Not enough permissions."},
        404: {"description": "Not Found - Certification does not exist."},
    },
)
async def delete_existing_certification(
    certification_id: int,
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
    certification = await get_certification_by_id(
        db, certification_id
    )
    if certification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found.",
        )

    await delete_certification(db, certification)
    await db.commit()
