from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_certification_repo
from app.db.session import get_db
from app.repositories.certifications import CertificationRepository
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
    certifications: Annotated[
        CertificationRepository, Depends(get_certification_repo)
    ],
) -> list[CertificationSchema]:
    all_certifications = await certifications.get_all()
    return [
        CertificationSchema.model_validate(cert)
        for cert in all_certifications
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
    certifications: Annotated[
        CertificationRepository, Depends(get_certification_repo)
    ],
) -> CertificationSchema:
    existing = await certifications.get_by_name(payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Certification already exists.",
        )

    certification = await certifications.create(payload.name)
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
    certifications: Annotated[
        CertificationRepository, Depends(get_certification_repo)
    ],
) -> CertificationSchema:
    certification = await certifications.get_by_id(certification_id)
    if certification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found.",
        )

    duplicate = await certifications.get_by_name(payload.name)
    if duplicate is not None and duplicate.id != certification_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Certification name already taken.",
        )

    certification = await certifications.update(certification, payload.name)
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
    certifications: Annotated[
        CertificationRepository, Depends(get_certification_repo)
    ],
) -> None:
    certification = await certifications.get_by_id(certification_id)
    if certification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certification not found.",
        )

    await certifications.delete(certification)
    await db.commit()
