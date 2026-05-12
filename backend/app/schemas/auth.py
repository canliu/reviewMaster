from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, value: str) -> str:
        if not _PASSWORD_RE.match(value):
            raise ValueError(
                "Password must be at least 8 characters and include at least "
                "one letter and one digit."
            )
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenOnly(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: UUID
    email: EmailStr
    timezone: str
