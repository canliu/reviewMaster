from __future__ import annotations

from pydantic import BaseModel, Field


class CreateNoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=500)
