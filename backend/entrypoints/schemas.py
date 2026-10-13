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

class MemberCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    note: str = ''
class MemberPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = None

class ClaimSubmit(Input):
    member_id: str
    destination_account_id: str
    amount: str
    effective_date: date
    description: str = ''
    basis: str = Field(min_length=1)
    confirm_now: bool = False
    idempotency_key: str = Field(min_length=1, max_length=200)
    confirmed_amount: str | None = None
    confirmation_reason: str = ''
class ClaimConfirmation(Approval):
    confirmed_amount: str
    confirmation_reason: str = ''

class RepaymentAllocationInput(Input):
    claim_id: str
    amount: str
class RepaymentAllocationSubmit(RepaymentAllocationInput):
    expected_version: int
class RepaymentPreview(Input):
    member_id: str
    source_account_id: str
    amount: str
    effective_date: date
    description: str = ''
    basis: str = Field(min_length=1)
    allocation_mode: Literal['oldest_first', 'manual'] = 'oldest_first'
    allocations: list[RepaymentAllocationInput] | None = None
class RepaymentSubmit(RepaymentPreview):
    idempotency_key: str = Field(min_length=1, max_length=200)
    allocations: list[RepaymentAllocationSubmit]
