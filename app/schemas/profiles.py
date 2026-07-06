from datetime import date
from typing import Optional

from fastapi import File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.models.accounts import GenderEnum


ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024
MIN_BIRTH_YEAR = 1900


def validate_name(value: str) -> None:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Name cannot be empty or contain only spaces.")

    if not all(char.isalpha() or char in "-'" for char in stripped):
        raise ValueError("Name must contain only letters, hyphens or apostrophes.")

    if len(stripped) > 100:
        raise ValueError("Name must be at most 100 characters long.")


def validate_birth_date(value: date) -> None:
    if value >= date.today():
        raise ValueError("Date of birth must be in the past.")

    if value.year < MIN_BIRTH_YEAR:
        raise ValueError(f"Date of birth must be after {MIN_BIRTH_YEAR}.")


def validate_image(value: UploadFile) -> None:
    if value.content_type not in ALLOWED_AVATAR_TYPES:
        raise ValueError("Unsupported avatar format.")

    if value.size is not None and value.size > MAX_AVATAR_SIZE:
        raise ValueError("Avatar is too large.")


class ProfileUpdateRequestSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None
    avatar: Optional[UploadFile] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            validate_name(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: Optional[date]) -> Optional[date]:
        if value is not None:
            validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def validate_info(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return value

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, value: Optional[UploadFile]) -> Optional[UploadFile]:
        if value is not None:
            validate_image(value)
        return value

    @classmethod
    def as_form(
        cls,
        first_name: Optional[str] = Form(None),
        last_name: Optional[str] = Form(None),
        gender: Optional[str] = Form(None),
        date_of_birth: Optional[date] = Form(None),
        info: Optional[str] = Form(None),
        avatar: Optional[UploadFile] = File(None),
    ) -> "ProfileUpdateRequestSchema":
        provided_fields = {
            key: value
            for key, value in {
                "first_name": first_name,
                "last_name": last_name,
                "gender": gender,
                "date_of_birth": date_of_birth,
                "info": info,
                "avatar": avatar,
            }.items()
            if value is not None
        }

        try:
            return cls(**provided_fields)  # type: ignore[arg-type]
        except ValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=[
                    {"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
                    for e in error.errors()
                ],
            ) from error


class ProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    info: Optional[str] = None
    avatar_url: Optional[str] = None
