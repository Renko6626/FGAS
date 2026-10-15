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

# Shared read contracts. Dynamic audit snapshots alone retain free-form contents.
from datetime import date, datetime
from typing import Any, Generic, TypeVar
from pydantic import BaseModel


class PageFilters(Input):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class DirectoryFilters(PageFilters):
    q: str | None = None


class SkuFilters(DirectoryFilters):
    active: bool | None = None


class AccountFilters(SkuFilters):
    kind: Literal['public', 'private', 'external'] | None = None
    member_id: str | None = None
    tag: str | None = None


class BalanceFilters(AccountFilters):
    account_id: str | None = None


class FundTransferFilters(PageFilters):
    status: str | None = None
    tag: str | None = None
    source_account_id: str | None = None
    destination_account_id: str | None = None
    effective_date_from: date | None = None
    effective_date_to: date | None = None
    created_at_from: AwareDatetime | None = None
    created_at_to: AwareDatetime | None = None
    submitted_by_current_connection: bool = False


class StockTransferFilters(FundTransferFilters):
    sku_id: str | None = None


class InventoryFilters(PageFilters):
    account_id: str | None = None
    sku_id: str | None = None
    member_id: str | None = None
    custodian_id: str | None = None


class StockMoveFilters(PageFilters):
    transfer_id: str | None = None
    sku_id: str | None = None
    source_account_id: str | None = None
    destination_account_id: str | None = None


class StocktakeFilters(PageFilters):
    status: Literal['in_progress', 'ended'] | None = None


class SettlementFilters(Input):
    account_id: str


class IdentifierInput(Input):
    identifier: str


class MemberRow(BaseModel):
    id: str
    name: str


class AccountRow(MemberRow):
    kind: str
    member_id: str | None
    member_name: str | None
    tags: list[str]
    active: bool


class SkuRow(MemberRow):
    specification: str
    unit: str
    active: bool


class BalanceRow(AccountRow):
    balance_minor: int
    balance: str


class SubmissionSource(BaseModel):
    submitted_credential_id: str | None
    submitted_credential_name: str | None


class TransferRow(SubmissionSource):
    id: str
    source_account_id: str
    destination_account_id: str
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
    reversal_of: str | None


class JournalRow(BaseModel):
    account_id: str
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
    id: str
    sku_id: str
    sku_name: str
    specification: str
    unit: str
    quantity: str


class StockTransferRow(TransferRow):
    source_kind: str
    destination_kind: str
    source_reference: str | None
    related_transfer_id: str | None
    lines: list[StockLine]
    snapshot_at: datetime


class ConfirmationRow(SubmissionSource):
    id: str
    transfer_id: str
    actor_id: str
    effective_date: date
    status: str
    approved_by: str | None
    execution_snapshot: dict[str, Any] | None
    created_at: datetime


class FundReference(BaseModel):
    id: str
    status: str
    description: str
    amount_minor: int
    amount: str
    reversal_of: str | None


class RelatedLine(BaseModel):
    sku_id: str
    quantity: str


class RelatedTransfer(BaseModel):
    id: str
    status: str
    source_account_id: str
    destination_account_id: str
    lines: list[RelatedLine]


class StockAuditRow(BaseModel):
    id: str
    actor_id: str
    action: str
    snapshot: dict[str, Any]
    created_at: datetime
    agent_credential_id: str | None
    agent_credential_name: str | None


class StockTransferDetail(StockTransferRow):
    approval_snapshot: dict[str, Any] | None
    confirmations: list[ConfirmationRow]
    fund_references: list[FundReference]
    related_transfers: list[RelatedTransfer]
    audit: list[StockAuditRow]


class InventoryTotal(BaseModel):
    sku_id: str
    quantity: str
    valuation: Literal['未估值']


class InventoryRow(InventoryTotal):
    account_id: str
    account_name: str
    member_id: str | None
    member_name: str | None
    sku_name: str
    unit: str
    in_transit_planned_quantity: str


class StockMoveRow(BaseModel):
    id: str
    confirmation_id: str
    transfer_line_id: str
    sku_id: str
    source_account_id: str
    destination_account_id: str
    effective_date: date
    created_at: datetime
    quantity: str
    sku_name: str
    unit: str
    source_account_name: str
    destination_account_name: str
    applicant_id: str
    executor_id: str | None
    stock_transfer_id: str
    snapshot_at: datetime


class StocktakeRow(MemberRow):
    description: str
    status: str
    created_by: str
    created_at: datetime
    gain_account_id: str
    gain_account_name: str
    loss_account_id: str
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
    api_version: Literal['1'] = '1'
    data: T


class BalanceData(PageData[BalanceRow, BalanceFilters]):
    total_minor: int
    total: str
    currency: Literal['CNY']


class InventoryData(PageData[InventoryRow, InventoryFilters]):
    totals: list[InventoryTotal]


class StocktakeDetail(BaseModel, Generic[T]):
    stocktake: StocktakeRow
    transfers: list[T]


class StocktakeMetadata(BaseModel):
    id: str
    name: str
    status: str


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
    item_transfer_id: str
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


QUERY_OUTPUT_SCHEMAS = {
    'list_fund_accounts': QueryResult[PageData[AccountRow, AccountFilters]],
    'list_stock_accounts': QueryResult[PageData[AccountRow, AccountFilters]],
    'list_skus': QueryResult[PageData[SkuRow, SkuFilters]],
    'list_members': QueryResult[PageData[MemberRow, DirectoryFilters]],
    'get_fund_balances': QueryResult[BalanceData],
    'list_fund_transfers': QueryResult[PageData[FundTransferRow, FundTransferFilters]],
    'get_fund_transfer': QueryResult[FundTransferDetail],
    'get_inventory': QueryResult[InventoryData],
    'list_stock_transfers': QueryResult[PageData[StockTransferRow, StockTransferFilters]],
    'get_stock_transfer': QueryResult[StockTransferDetail],
    'list_stock_moves': QueryResult[PageData[StockMoveRow, StockMoveFilters]],
    'get_settlement_overview': QueryResult[SettlementOverviewData],
    'list_fund_stocktakes': QueryResult[PageData[StocktakeRow, StocktakeFilters]],
    'get_fund_stocktake': QueryResult[StocktakeDetail[FundTransferRow]],
    'list_stock_stocktakes': QueryResult[PageData[StocktakeRow, StocktakeFilters]],
    'get_stock_stocktake': QueryResult[StocktakeDetail[StockTransferRow]],
}

QUERY_INPUT_SCHEMAS = {
    'list_fund_accounts': AccountFilters, 'list_stock_accounts': AccountFilters,
    'list_skus': SkuFilters, 'list_members': DirectoryFilters,
    'get_fund_balances': BalanceFilters, 'list_fund_transfers': FundTransferFilters,
    'get_fund_transfer': IdentifierInput, 'get_inventory': InventoryFilters,
    'list_stock_transfers': StockTransferFilters, 'get_stock_transfer': IdentifierInput,
    'list_stock_moves': StockMoveFilters, 'get_settlement_overview': SettlementFilters,
    'list_fund_stocktakes': StocktakeFilters, 'get_fund_stocktake': IdentifierInput,
    'list_stock_stocktakes': StocktakeFilters, 'get_stock_stocktake': IdentifierInput,
}
