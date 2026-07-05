from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    AfterValidator,
    model_validator
)


def validate_password_strength(password: str) -> str:
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_special = any(not char.isalnum() for char in password)

    errors = []
    if not has_upper:
        errors.append("one uppercase letter")
    if not has_lower:
        errors.append("one lowercase letter")
    if not has_digit:
        errors.append("one number")
    if not has_special:
        errors.append("one special character")

    if errors:
        raise ValueError(f"Password must contain at least: {', '.join(errors)}.")
    return password


ComplexPassword = Annotated[
    str,
    Field(min_length=8, max_length=128),
    AfterValidator(validate_password_strength)
]


class PasswordMatchMixin(BaseModel):
    password: ComplexPassword
    password_confirm: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def verify_password_match(self) -> "PasswordMatchMixin":
        if self.password != self.password_confirm:
            raise ValueError("The two passwords do not match.")
        return self


class UserRegistrationRequestSchema(PasswordMatchMixin):
    email: EmailStr


class UserRegistrationResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime


class UserActivationRequestSchema(BaseModel):
    email: EmailStr
    token: str


class ResendActivationRequestSchema(BaseModel):
    email: EmailStr


class MessageResponseSchema(BaseModel):
    message: str


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponseSchema(BaseModel):
    access_token: str
    refresh_token: str


class TokenRefreshSchema(BaseModel):
    refresh_token: str


class PasswordChangeRequestSchema(PasswordMatchMixin):
    old_password: str = Field(min_length=8, max_length=128)


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetCompleteRequestSchema(PasswordMatchMixin):
    token: str
