from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
class Login(Input): user_id: str
class AccountCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal['asset', 'liability', 'equity', 'income', 'expense']
    tags: list[str] = Field(default_factory=list)
    is_fund: bool = False
class AccountPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    tags: list[str] | None = None
class LocationCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    custodian_label: str = ''
    tags: list[str] = Field(default_factory=list)
class LocationPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    custodian_label: str | None = None
    tags: list[str] | None = None
class UserPatch(Input):
    role: Literal['admin', 'trusted', 'untrusted'] | None = None
    active: bool | None = None
class Preview(Input):
    source_account_id: str
    destination_account_id: str
    amount: str
    effective_date: date
    description: str = ''
    counterparty: str | None = None
class Submit(Preview): idempotency_key: str = Field(min_length=1, max_length=200)
class Approval(Input): expected_version: int
class Rejection(Approval): reason: str = Field(min_length=1)
class Reversal(Input):
    reason: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=200)
