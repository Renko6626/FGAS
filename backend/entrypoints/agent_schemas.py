"""Agent tool input and output contracts."""
from typing import Literal
from pydantic import AwareDatetime, Field
from backend.entrypoints.schemas import Input


# Shared read contracts. Stock audit details contain operation metadata only.
from datetime import date, datetime
from typing import Any, Generic, TypeVar
from pydantic import BaseModel


class MeFilters(Input):
    pass


class CurrentUser(BaseModel):
    display_name: str
    role: Literal['untrusted', 'trusted', 'admin']


class CurrentConnection(BaseModel):
    name: str
    level: Literal['low', 'high']


class MeData(BaseModel):
    user: CurrentUser
    connection: CurrentConnection


class PageFilters(Input):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class DirectoryFilters(PageFilters):
    q: str | None = None


class SkuFilters(DirectoryFilters):
    active: bool | None = None


class SkuDirectoryFilters(SkuFilters):
    code: str | None = Field(default=None, description='业务SKU代号，精确查询，如ARC-01-A。')
    tag: str | None = None


class AccountFilters(SkuFilters):
    kind: Literal['public', 'private', 'external'] | None = None
    member_code: str | None = None
    tag: str | None = None

class StockAccountFilters(AccountFilters):
    kind: Literal['internal', 'external'] | None = None


class WindowFilters(PageFilters):
    created_at_from: AwareDatetime | None = None
    created_at_to: AwareDatetime | None = None
    all_time: bool = False


class BalanceFilters(AccountFilters):
    account_code: str | None = None
    as_of: AwareDatetime | None = None
    basis: Literal['posted', 'effective_date'] = Field(default='posted', description='默认按实际入账时间；仅用户明确要求按业务日期核对时选 effective_date。')


class TransferFilters(WindowFilters):
    q: str | None = None
    tag: str | None = None
    source_account_code: str | None = None
    destination_account_code: str | None = None
    effective_date_from: date | None = None
    effective_date_to: date | None = None
    submitted_by_current_connection: bool = False


class FundTransferFilters(TransferFilters):
    status: Literal['pending', 'posted', 'rejected', 'reversed'] | None = Field(default=None, description='pending 待审；posted 已过账；rejected 已拒绝；reversed 已冲销。')
    posted_at_from: AwareDatetime | None = None
    posted_at_to: AwareDatetime | None = None


class StockTransferFilters(TransferFilters):
    source_reference: str | None = None
    status: Literal['pending', 'in_transit', 'completed', 'rejected', 'cancelled'] | None = Field(default=None, description='pending 待审；in_transit 在途；completed 已完成；rejected 已拒绝；cancelled 已取消。')
    sku_code: str | None = None


class InventoryFilters(PageFilters):
    account_code: str | None = None
    sku_code: str | None = None
    member_code: str | None = Field(default=None, description='按当前负责人筛选；返回行的 member_code/member_name 也是此负责人。')
    as_of: AwareDatetime | None = None
    basis: Literal['posted', 'effective_date'] = Field(default='posted', description='默认按实际入账时间；仅用户明确要求按业务日期核对时选 effective_date。')


class StockMoveFilters(WindowFilters):
    transfer_code: str | None = None
    sku_code: str | None = None
    source_account_code: str | None = None
    destination_account_code: str | None = None
    effective_date_from: date | None = None
    effective_date_to: date | None = None
    posted_at_from: AwareDatetime | None = None
    posted_at_to: AwareDatetime | None = None


class StocktakeFilters(PageFilters):
    status: Literal['in_progress', 'ended'] | None = None


class SettlementFilters(Input):
    identifier: str


class SettlementOutstandingFilters(PageFilters):
    account_code: str | None = None
    direction: Literal['expense', 'receipt'] | None = None
    kind: Literal['item', 'payment'] | None = None


class IdentifierInput(Input):
    identifier: str


class MemberRow(BaseModel):
    code: str
    name: str


class SavedMember(MemberRow):
    note: str


class AccountRow(MemberRow):
    kind: str
    member_code: str | None
    member_name: str | None
    tags: list[str]
    active: bool


class ResponsibilityRow(BaseModel):
    member_code: str
    member_name: str
    valid_from: datetime
    valid_to: datetime | None
    actor_id: str
    actor_name: str
    ended_by: str | None
    ended_by_name: str | None


class StockAccountRow(AccountRow):
    kind: Literal['internal', 'external']


class SkuRow(MemberRow):
    code: str
    tags: list[str]
    unit: str
    active: bool


class BalanceRow(AccountRow):
    balance_minor: int
    balance: str


class SubmissionSource(BaseModel):
    submitted_credential_id: str | None
    submitted_credential_name: str | None


class TransferRow(SubmissionSource):
    code: str
    source_account_code: str
    destination_account_code: str
    source_account_name: str
    destination_account_name: str
    effective_date: date
    description: str
    tags: list[str]
    actor_id: str
    approved_by: str | None
    approval_mode: str | None
    status: str
    reason: str | None
    created_at: datetime


class FundTransferRow(TransferRow):
    amount_minor: int
    amount: str
    counterparty: str | None
    actor_name: str
    approved_by_name: str | None
    version: int
    reversal_of_code: str | None
    posted_at: datetime | None


class JournalRow(BaseModel):
    account_code: str
    debit_minor: int
    debit: str
    credit_minor: int
    credit: str


class FundAuditRow(BaseModel):
    actor_id: str
    action: str
    detail: str
    created_at: datetime
    agent_credential_id: str | None
    agent_credential_name: str | None


class FundTransferDetail(FundTransferRow):
    journal_lines: list[JournalRow]
    audit: list[FundAuditRow]


class StockLine(BaseModel):
    sku_code: str
    sku_name: str
    unit: str
    quantity: str


class StockTransferRow(TransferRow):
    source_kind: str
    destination_kind: str
    source_reference: str | None
    related_transfer_code: str | None
    lines: list[StockLine]
    snapshot_at: datetime


class ConfirmationRow(SubmissionSource):
    code: str
    transfer_code: str
    actor_id: str
    effective_date: date
    status: str
    approved_by: str | None
    created_at: datetime


class FundReference(BaseModel):
    code: str
    status: str
    description: str
    amount_minor: int
    amount: str
    reversal_of_code: str | None


class RelatedLine(BaseModel):
    sku_code: str
    quantity: str


class RelatedTransfer(BaseModel):
    code: str
    status: str
    source_account_code: str
    destination_account_code: str
    lines: list[RelatedLine]


class StockAuditRow(BaseModel):
    actor_id: str
    action: str
    detail: dict[str, Any]
    created_at: datetime
    agent_credential_id: str | None
    agent_credential_name: str | None


class StockTransferDetail(StockTransferRow):
    confirmations: list[ConfirmationRow]
    fund_references: list[FundReference]
    related_transfers: list[RelatedTransfer]
    audit: list[StockAuditRow]


class InventoryQuantity(BaseModel):
    sku_code: str
    sku_name: str
    unit: str
    quantity: str
    valuation: Literal['未估值']


class InventoryTotal(InventoryQuantity):
    incoming_to_org_quantity: str | None
    outgoing_from_org_quantity: str | None
    internal_transfer_quantity: str | None


class InventoryRow(InventoryQuantity):
    account_code: str
    account_name: str
    member_code: str | None
    member_name: str | None
    incoming_planned_quantity: str | None
    outgoing_planned_quantity: str | None


class StockMoveRow(BaseModel):
    confirmation_code: str
    sku_code: str
    source_account_code: str
    destination_account_code: str
    effective_date: date
    created_at: datetime
    posted_at: datetime
    quantity: str
    sku_name: str
    unit: str
    source_account_name: str
    destination_account_name: str
    applicant_id: str
    executor_id: str | None
    stock_transfer_code: str
    snapshot_at: datetime


class StocktakeRow(BaseModel):
    id: str
    name: str
    description: str
    status: str
    created_by: str
    created_at: datetime
    gain_account_code: str
    gain_account_name: str
    loss_account_code: str
    loss_account_name: str


T = TypeVar('T')
F = TypeVar('F')


class PageData(BaseModel, Generic[T, F]):
    items: list[T]
    page: int
    has_more: bool
    filters: F
    snapshot_at: datetime


class QueryResult(BaseModel, Generic[T]):
    api_version: Literal['2'] = '2'
    data: T


class BalanceData(PageData[BalanceRow, BalanceFilters]):
    total_minor: int
    total: str
    currency: Literal['CNY']
    as_of: datetime | None = None
    basis: Literal['posted', 'effective_date'] | None = None


class InventoryData(PageData[InventoryRow, InventoryFilters]):
    totals: list[InventoryTotal]
    as_of: datetime | None = None
    basis: Literal['posted', 'effective_date'] | None = None


class StocktakeDetail(BaseModel, Generic[T]):
    stocktake: StocktakeRow
    transfers: list[T]


class StocktakeMetadata(BaseModel):
    id: str
    name: str
    status: str


class StockAccountDetail(StockAccountRow):
    avatar_url: str | None
    stocktake: StocktakeMetadata | None
    responsibility_history: list[ResponsibilityRow]


class SettlementAccount(AccountRow):
    avatar_url: str | None
    balance_minor: int
    balance: str
    stocktake: StocktakeMetadata | None


class SettlementItem(BaseModel):
    transfer: FundTransferRow
    settled_minor: int
    settled: str
    outstanding_minor: int
    outstanding: str


class SettlementMatchRow(BaseModel):
    item_transfer_code: str
    amount_minor: int
    amount: str
    effective: bool


class SettlementRow(BaseModel):
    transfer: FundTransferRow
    matched_minor: int
    matched: str
    unmatched_minor: int
    unmatched: str
    matches: list[SettlementMatchRow]


class SettlementOverviewData(BaseModel):
    account: SettlementAccount
    expenses: list[SettlementItem]
    receipts: list[SettlementItem]
    settlements: list[SettlementRow]


class SettlementOutstandingRow(BaseModel):
    account_code: str
    account_name: str
    kind: Literal['item', 'payment']
    direction: Literal['expense', 'receipt']
    transfer_code: str
    effective_date: date
    description: str
    counterparty: str | None
    source_account_code: str
    source_account_name: str
    destination_account_code: str
    destination_account_name: str
    amount_minor: int
    amount: str
    matched_minor: int
    matched: str
    remaining_minor: int
    remaining: str


class SettlementOutstandingData(PageData[SettlementOutstandingRow, SettlementOutstandingFilters]):
    total: int
    limit: int


QUERY_OUTPUT_SCHEMAS = {
    'me': QueryResult[MeData],
    'list_fund_accounts': QueryResult[PageData[AccountRow, AccountFilters]],
    'list_stock_accounts': QueryResult[PageData[StockAccountRow, StockAccountFilters]],
    'get_stock_account': QueryResult[StockAccountDetail],
    'list_skus': QueryResult[PageData[SkuRow, SkuDirectoryFilters]],
    'list_members': QueryResult[PageData[SavedMember, DirectoryFilters]],
    'get_fund_balances': QueryResult[BalanceData],
    'list_fund_transfers': QueryResult[PageData[FundTransferRow, FundTransferFilters]],
    'get_fund_transfer': QueryResult[FundTransferDetail],
    'get_inventory': QueryResult[InventoryData],
    'list_stock_transfers': QueryResult[PageData[StockTransferRow, StockTransferFilters]],
    'get_stock_transfer': QueryResult[StockTransferDetail],
    'list_stock_moves': QueryResult[PageData[StockMoveRow, StockMoveFilters]],
    'get_settlement_overview': QueryResult[SettlementOverviewData],
    'list_settlement_outstanding': QueryResult[SettlementOutstandingData],
    'list_fund_stocktakes': QueryResult[PageData[StocktakeRow, StocktakeFilters]],
    'get_fund_stocktake': QueryResult[StocktakeDetail[FundTransferRow]],
    'list_stock_stocktakes': QueryResult[PageData[StocktakeRow, StocktakeFilters]],
    'get_stock_stocktake': QueryResult[StocktakeDetail[StockTransferRow]],
}

QUERY_INPUT_SCHEMAS = {
    'me': MeFilters,
    'list_fund_accounts': AccountFilters, 'list_stock_accounts': StockAccountFilters,
    'get_stock_account': IdentifierInput,
    'list_skus': SkuDirectoryFilters, 'list_members': DirectoryFilters,
    'get_fund_balances': BalanceFilters, 'list_fund_transfers': FundTransferFilters,
    'get_fund_transfer': IdentifierInput, 'get_inventory': InventoryFilters,
    'list_stock_transfers': StockTransferFilters, 'get_stock_transfer': IdentifierInput,
    'list_stock_moves': StockMoveFilters, 'get_settlement_overview': IdentifierInput,
    'list_settlement_outstanding': SettlementOutstandingFilters,
    'list_fund_stocktakes': StocktakeFilters, 'get_fund_stocktake': IdentifierInput,
    'list_stock_stocktakes': StocktakeFilters, 'get_stock_stocktake': IdentifierInput,
}

# Writes reuse business inputs. Only fields that support clearing accept explicit null.
from pydantic import ConfigDict, field_validator
from backend.entrypoints import schemas as business


def non_null_patch_schema(schema, names):
    """Omission preserves a field; only explicitly clearable fields advertise null."""
    for name in names:
        field = schema['properties'][name]
        field.update(next(option for option in field.pop('anyOf') if option.get('type') != 'null'))
        field.pop('default', None)


def require_patch_value(value):
    if value is None:
        raise ValueError('不能为 null；不修改此字段时请省略')
    return value


class AgentAccountPatch(business.AccountPatch):
    model_config = ConfigDict(json_schema_extra=lambda schema: non_null_patch_schema(schema, ('name', 'tags', 'active')))
    reject_null = field_validator('name', 'tags', 'active', mode='before')(require_patch_value)


class AgentSkuPatch(business.SkuPatch):
    model_config = ConfigDict(json_schema_extra=lambda schema: non_null_patch_schema(schema, ('code', 'name', 'tags', 'unit', 'active')))
    reject_null = field_validator('code', 'name', 'tags', 'unit', 'active', mode='before')(require_patch_value)


class AgentMemberPatch(business.MemberPatch):
    model_config = ConfigDict(json_schema_extra=lambda schema: non_null_patch_schema(schema, ('name', 'note')))
    reject_null = field_validator('name', 'note', mode='before')(require_patch_value)


class AccountPatchOperation(AgentAccountPatch, IdentifierInput): pass
class SkuPatchOperation(AgentSkuPatch, IdentifierInput): pass
class MemberPatchOperation(AgentMemberPatch, IdentifierInput): pass
class CompletionOperation(business.CompletionInput, IdentifierInput): pass
class FundApprovalOperation(business.Approval, IdentifierInput): pass
class FundRejectionOperation(business.Rejection, IdentifierInput): pass
class FundReversalOperation(business.Reversal, IdentifierInput): pass
class StockApprovalOperation(business.StockApproval, IdentifierInput): pass
class StockRejectionOperation(business.StockRejection, IdentifierInput): pass
class SettlementMatchesOperation(business.SettlementMatches, IdentifierInput): pass
class StockFundReferenceOperation(business.StockFundReferenceInput, IdentifierInput): pass
class StocktakePatchOperation(business.StocktakePatch, IdentifierInput): pass


class WriteEffect(BaseModel):
    status: str
    ledger_effect_applied: bool
    approval_required: bool


class FundWriteData(WriteEffect):
    resource_type: Literal['fund_transfer']
    transfer_code: str


class StockWriteData(WriteEffect):
    resource_type: Literal['stock_transfer']
    stock_transfer_code: str


class CompletionWriteData(WriteEffect):
    resource_type: Literal['stock_confirmation']
    confirmation_code: str
    stock_transfer_code: str
    stock_transfer_status: str


class SavedAccount(AccountRow):
    avatar_url: str | None
    stocktake: StocktakeMetadata | None


class SavedFundAccount(SavedAccount):
    balance_minor: int
    balance: str


class SavedStockAccount(SavedAccount):
    kind: Literal['internal', 'external']


class SavedSku(SkuRow):
    avatar_url: str | None


class FundAccountWriteData(WriteEffect):
    resource_type: Literal['fund_account']
    account_code: str
    object: SavedFundAccount


class StockAccountWriteData(WriteEffect):
    resource_type: Literal['stock_account']
    account_code: str
    object: SavedStockAccount


class SkuWriteData(WriteEffect):
    resource_type: Literal['sku']
    sku_code: str
    object: SavedSku


class MemberWriteData(WriteEffect):
    resource_type: Literal['member']
    member_code: str
    object: SavedMember


class FundStocktakeWriteData(WriteEffect):
    resource_type: Literal['fund_stocktake']
    stocktake_id: str
    object: StocktakeRow


class StockStocktakeWriteData(WriteEffect):
    resource_type: Literal['stock_stocktake']
    stocktake_id: str
    object: StocktakeRow


class SettlementWriteData(WriteEffect):
    resource_type: Literal['settlement']
    transfer_code: str
    matches: list[SettlementMatchRow]


class StockOperationWriteData(BaseModel):
    resource_type: Literal['stock_operation']
    fund_transfer: FundWriteData
    stock_transfer: StockWriteData


# Identifier-bearing inputs are flat MCP objects. The adapter removes identifier,
# then dumps with mode='json'. Patch tools additionally use exclude_unset=True;
# creation tools retain Schema defaults required by existing business services.
OPERATION_INPUT_SCHEMAS = {
    'propose_fund_transfer': business.Submit,
    'propose_stock_transfer': business.StockTransferInput,
    'propose_stock_completion': CompletionOperation,
    'create_fund_transfer': business.Submit,
    'create_stock_transfer': business.StockTransferInput,
    'complete_stock_transfer': CompletionOperation,
    'create_fund_account': business.AccountCreate,
    'update_fund_account': AccountPatchOperation,
    'create_stock_account': business.StockAccountCreate,
    'update_stock_account': AccountPatchOperation,
    'create_sku': business.SkuCreate,
    'update_sku': SkuPatchOperation,
    'create_member': business.MemberCreate,
    'update_member': MemberPatchOperation,
    'approve_fund_transfer': FundApprovalOperation,
    'reject_fund_transfer': FundRejectionOperation,
    'reverse_fund_transfer': FundReversalOperation,
    'approve_stock_transfer': StockApprovalOperation,
    'reject_stock_transfer': StockRejectionOperation,
    'cancel_stock_transfer': StockRejectionOperation,
    'approve_stock_completion': StockApprovalOperation,
    'reject_stock_completion': StockRejectionOperation,
    'create_settlement': business.SettlementCreate,
    'add_settlement_matches': SettlementMatchesOperation,
    'create_stock_operation': business.StockOperationInput,
    'add_stock_fund_reference': StockFundReferenceOperation,
    'create_fund_stocktake': business.StocktakeCreate,
    'update_fund_stocktake': StocktakePatchOperation,
    'end_fund_stocktake': IdentifierInput,
    'create_stock_stocktake': business.StocktakeCreate,
    'update_stock_stocktake': StocktakePatchOperation,
    'end_stock_stocktake': IdentifierInput,
}

OPERATION_OUTPUT_SCHEMAS = {
    'propose_fund_transfer': QueryResult[FundWriteData],
    'propose_stock_transfer': QueryResult[StockWriteData],
    'propose_stock_completion': QueryResult[CompletionWriteData],
    'create_fund_transfer': QueryResult[FundWriteData],
    'create_stock_transfer': QueryResult[StockWriteData],
    'complete_stock_transfer': QueryResult[CompletionWriteData],
    'create_fund_account': QueryResult[FundAccountWriteData],
    'update_fund_account': QueryResult[FundAccountWriteData],
    'create_stock_account': QueryResult[StockAccountWriteData],
    'update_stock_account': QueryResult[StockAccountWriteData],
    'create_sku': QueryResult[SkuWriteData],
    'update_sku': QueryResult[SkuWriteData],
    'create_member': QueryResult[MemberWriteData],
    'update_member': QueryResult[MemberWriteData],
    'approve_fund_transfer': QueryResult[FundWriteData],
    'reject_fund_transfer': QueryResult[FundWriteData],
    'reverse_fund_transfer': QueryResult[FundWriteData],
    'approve_stock_transfer': QueryResult[StockWriteData],
    'reject_stock_transfer': QueryResult[StockWriteData],
    'cancel_stock_transfer': QueryResult[StockWriteData],
    'approve_stock_completion': QueryResult[CompletionWriteData],
    'reject_stock_completion': QueryResult[CompletionWriteData],
    'create_settlement': QueryResult[SettlementWriteData],
    'add_settlement_matches': QueryResult[SettlementWriteData],
    'create_stock_operation': QueryResult[StockOperationWriteData],
    'add_stock_fund_reference': QueryResult[StockWriteData],
    'create_fund_stocktake': QueryResult[FundStocktakeWriteData],
    'update_fund_stocktake': QueryResult[FundStocktakeWriteData],
    'end_fund_stocktake': QueryResult[FundStocktakeWriteData],
    'create_stock_stocktake': QueryResult[StockStocktakeWriteData],
    'update_stock_stocktake': QueryResult[StockStocktakeWriteData],
    'end_stock_stocktake': QueryResult[StockStocktakeWriteData],
}
