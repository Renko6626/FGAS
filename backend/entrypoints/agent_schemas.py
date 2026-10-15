"""Human credential-management inputs; secrets and ownership are server managed."""
from typing import Literal
from pydantic import AwareDatetime, Field
from backend.entrypoints.schemas import Input


class CredentialCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    level: Literal['low', 'high'] = 'low'
    expires_at: AwareDatetime | None = None


class CredentialPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    level: Literal['low', 'high'] | None = None
    active: bool | None = None
    expires_at: AwareDatetime | None = None
