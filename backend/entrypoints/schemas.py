from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, AwareDatetime
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
ExternalKind = Literal['supplier', 'customer', 'opening', 'loss', 'adjustment_gain', 'adjustment_loss']
class LocationCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    custodian_label: str = ''
    tags: list[str] = Field(default_factory=list)
    kind: Literal['physical', 'external'] = 'physical'
    external_kind: ExternalKind | None = None
    active: bool = True
class LocationPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    custodian_label: str | None = None
    tags: list[str] | None = None
    kind: Literal['physical', 'external'] | None = None
    external_kind: ExternalKind | None = None
    active: bool | None = None
class CustodyInput(Input):
    member_id: str | None
class SkuCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    specification: str = ''
    unit: str = Field(min_length=1, max_length=100)
    active: bool = True
class SkuPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    specification: str | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=100)
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

class ClaimSubmit(Input):
    member_id: str
    destination_account_id: str
    amount: str
    effective_date: date
    description: str = ''
    basis: str = Field(min_length=1)
    confirm_now: bool = False
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
    allocations: list[RepaymentAllocationSubmit]

class StockLineInput(Input):
    sku_id: str
    quantity: str
class StockTransferInput(Input):
    source_location_id: str
    destination_location_id: str
    action_kind: Literal['opening','arrival','sale','gift','loss','return','internal','adjustment_gain','adjustment_loss']
    effective_date: date
    description: str = ''
    basis: str = Field(min_length=1)
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
    basis: str = Field(min_length=1)
class StockFundReferenceInput(Input):
    fund_transfer_id: str

class StockFundMoney(Input):
    kind: Literal['fund_transfer']
    data: Submit
class StockClaimMoney(Input):
    kind: Literal['member_claim']
    data: ClaimSubmit
class StockOperationInput(Input):
    stock: StockTransferInput
    money: StockFundMoney | StockClaimMoney = Field(discriminator='kind')
