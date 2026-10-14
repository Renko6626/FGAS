from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
    @field_validator('tags',check_fields=False)
    @classmethod
    def clean_tags(cls,value):
        return list(dict.fromkeys(t.strip() for t in value if t.strip())) if value is not None else value
class Login(Input): user_id: str
class AccountCreate(Input):
    name: str = Field(min_length=1,max_length=200)
    kind: Literal['public','private','external']
    member_id: str | None = None
    avatar_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    active: bool = True
class AccountPatch(Input):
    name: str | None = Field(default=None,min_length=1,max_length=200)
    member_id: str | None = None
    avatar_url: str | None = None
    tags: list[str] | None = None
    active: bool | None = None
class CustodyInput(Input):
    member_id: str | None
class SkuCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    specification: str = ''
    unit: str = Field(min_length=1, max_length=100)
    avatar_url: str | None = None
    active: bool = True
class SkuPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    specification: str | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=100)
    avatar_url: str | None = None
    active: bool | None = None
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
    tags: list[str] = Field(default_factory=list)
class Submit(Preview): pass
class Approval(Input): expected_version: int
class Rejection(Approval): reason: str = Field(min_length=1)
class Reversal(Input):
    reason: str = Field(min_length=1)

class MemberCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    note: str = ''
class MemberPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = None

class SettlementAllocation(Input):
    item_transfer_id: str
    amount: str
class SettlementMatches(Input):
    allocations: list[SettlementAllocation] = Field(min_length=1)
class SettlementCreate(SettlementMatches):
    transfer: Submit

class StockLineInput(Input):
    sku_id: str
    quantity: str
class StockTransferInput(Input):
    source_account_id: str
    destination_account_id: str
    effective_date: date
    description: str = ''
    tags: list[str] = Field(default_factory=list)
    related_transfer_id: str | None = None
    source_reference: str | None = None
    fund_transfer_ids: list[str] = Field(default_factory=list)
    lines: list[StockLineInput] = Field(min_length=1)
class StockApproval(Input):
    pass
class StockRejection(StockApproval):
    reason: str = Field(min_length=1)
class CompletionInput(Input):
    effective_date: date
class StockFundReferenceInput(Input):
    fund_transfer_id: str

class StockOperationInput(Input):
    stock: StockTransferInput
    money: Submit

class StocktakeCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    description: str = ''
class StocktakePatch(Input):
    description: str
