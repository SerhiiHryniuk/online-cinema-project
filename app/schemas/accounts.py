from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegistrationRequestSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


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
