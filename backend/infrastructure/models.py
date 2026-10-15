from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Integer, BigInteger, Boolean, Date, DateTime, ForeignKey, JSON, UniqueConstraint, CheckConstraint, Index, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def new_id(): return str(uuid4())
def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
class AgentCredential(Base):
    __tablename__ = 'agent_credentials'
    __table_args__ = (CheckConstraint("level IN ('low','high')"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String)
    secret_hash: Mapped[str] = mapped_column(String, unique=True)
    level: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class LoginSession(Base):
    __tablename__ = 'login_sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
class FundAccount(Base):
    __tablename__ = 'fund_accounts'
    __table_args__ = (CheckConstraint("kind IN ('public','private','external')"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    member_id: Mapped[str | None] = mapped_column(ForeignKey('members.id'), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
class StockAccount(Base):
    __tablename__ = 'stock_accounts'
    __table_args__ = (CheckConstraint("kind IN ('public','private','external')"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    member_id: Mapped[str | None] = mapped_column(ForeignKey('members.id'), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
class Transfer(Base):
    __tablename__ = 'transfers'
    __table_args__ = (CheckConstraint('amount_minor > 0'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    source_account_id: Mapped[str] = mapped_column(ForeignKey('fund_accounts.id'))
    destination_account_id: Mapped[str] = mapped_column(ForeignKey('fund_accounts.id'))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    effective_date: Mapped[object] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String, default='')
    tags: Mapped[list] = mapped_column(JSON, default=list)
    counterparty: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    approval_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, default=1)
    reversal_of: Mapped[str | None] = mapped_column(ForeignKey('transfers.id'), nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    submitted_credential_id: Mapped[str | None] = mapped_column(ForeignKey('agent_credentials.id'), nullable=True)
    submitted_credential_name: Mapped[str | None] = mapped_column(String, nullable=True)
class JournalLine(Base):
    __tablename__ = 'journal_lines'
    __table_args__ = (CheckConstraint('(debit_minor > 0 AND credit_minor = 0) OR (credit_minor > 0 AND debit_minor = 0)'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    transfer_id: Mapped[str] = mapped_column(ForeignKey('transfers.id'))
    account_id: Mapped[str] = mapped_column(ForeignKey('fund_accounts.id'))
    debit_minor: Mapped[int] = mapped_column(BigInteger)
    credit_minor: Mapped[int] = mapped_column(BigInteger)
class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    transfer_id: Mapped[str] = mapped_column(ForeignKey('transfers.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(String, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    agent_credential_id: Mapped[str | None] = mapped_column(ForeignKey('agent_credentials.id'), nullable=True)
    agent_credential_name: Mapped[str | None] = mapped_column(String, nullable=True)


class Member(Base):
    __tablename__ = 'members'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    note: Mapped[str] = mapped_column(String, default='')

class SettlementMatch(Base):
    __tablename__ = 'settlement_matches'
    __table_args__ = (CheckConstraint('amount_minor > 0'), CheckConstraint('settlement_transfer_id <> item_transfer_id'))
    settlement_transfer_id: Mapped[str] = mapped_column(ForeignKey('transfers.id'), primary_key=True)
    item_transfer_id: Mapped[str] = mapped_column(ForeignKey('transfers.id'), primary_key=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)

class Sku(Base):
    __tablename__ = 'skus'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    specification: Mapped[str] = mapped_column(String, default='')
    unit: Mapped[str] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class StockAccountCustody(Base):
    __tablename__ = 'stock_account_custodies'
    __table_args__ = (
        CheckConstraint('valid_to IS NULL OR valid_to >= valid_from'),
        Index('one_current_stock_account_custody', 'account_id', unique=True, postgresql_where=text('valid_to IS NULL')),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey('stock_accounts.id'))
    member_id: Mapped[str] = mapped_column(ForeignKey('members.id'))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    ended_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)

class StockTransfer(Base):
    __tablename__ = 'stock_transfers'
    __table_args__ = (CheckConstraint("status IN ('pending','in_transit','completed','rejected','cancelled')"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    source_account_id: Mapped[str] = mapped_column(ForeignKey('stock_accounts.id'))
    destination_account_id: Mapped[str] = mapped_column(ForeignKey('stock_accounts.id'))
    effective_date: Mapped[object] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String, default='')
    tags: Mapped[list] = mapped_column(JSON, default=list)
    related_transfer_id: Mapped[str | None] = mapped_column(ForeignKey('stock_transfers.id'), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    approval_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    approval_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    submitted_credential_id: Mapped[str | None] = mapped_column(ForeignKey('agent_credentials.id'), nullable=True)
    submitted_credential_name: Mapped[str | None] = mapped_column(String, nullable=True)


class StockTransferLine(Base):
    __tablename__ = 'stock_transfer_lines'
    __table_args__ = (UniqueConstraint('transfer_id', 'sku_id'), CheckConstraint('quantity > 0 AND quantity <= 9007199254740991'))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    transfer_id: Mapped[str] = mapped_column(ForeignKey('stock_transfers.id'))
    sku_id: Mapped[str] = mapped_column(ForeignKey('skus.id'))
    quantity: Mapped[int] = mapped_column(BigInteger)

class StockTransferFundReference(Base):
    __tablename__ = 'stock_transfer_fund_references'
    stock_transfer_id: Mapped[str] = mapped_column(ForeignKey('stock_transfers.id'), primary_key=True)
    fund_transfer_id: Mapped[str] = mapped_column(ForeignKey('transfers.id'), primary_key=True)

class StockAudit(Base):
    __tablename__ = 'stock_audit_events'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    stock_transfer_id: Mapped[str] = mapped_column(ForeignKey('stock_transfers.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    agent_credential_id: Mapped[str | None] = mapped_column(ForeignKey('agent_credentials.id'), nullable=True)
    agent_credential_name: Mapped[str | None] = mapped_column(String, nullable=True)


class StockConfirmation(Base):
    __tablename__ = 'stock_confirmations'
    __table_args__ = (
        CheckConstraint("status IN ('pending','completed','rejected','invalidated')"),
        Index('one_pending_stock_confirmation', 'transfer_id', unique=True, postgresql_where=text("status = 'pending'")),
        Index('one_completed_stock_confirmation', 'transfer_id', unique=True, postgresql_where=text("status = 'completed'")),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    transfer_id: Mapped[str] = mapped_column(ForeignKey('stock_transfers.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    effective_date: Mapped[object] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    execution_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    submitted_credential_id: Mapped[str | None] = mapped_column(ForeignKey('agent_credentials.id'), nullable=True)
    submitted_credential_name: Mapped[str | None] = mapped_column(String, nullable=True)


class StockMove(Base):
    __tablename__ = 'stock_moves'
    __table_args__ = (UniqueConstraint('confirmation_id','transfer_line_id'), UniqueConstraint('transfer_line_id'), CheckConstraint('quantity > 0 AND quantity <= 9007199254740991'))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    confirmation_id: Mapped[str] = mapped_column(ForeignKey('stock_confirmations.id'))
    transfer_line_id: Mapped[str] = mapped_column(ForeignKey('stock_transfer_lines.id'))
    sku_id: Mapped[str] = mapped_column(ForeignKey('skus.id'))
    source_account_id: Mapped[str] = mapped_column(ForeignKey('stock_accounts.id'))
    destination_account_id: Mapped[str] = mapped_column(ForeignKey('stock_accounts.id'))
    quantity: Mapped[int] = mapped_column(BigInteger)
    effective_date: Mapped[object] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class FundStocktake(Base):
    __tablename__ = 'fund_stocktakes'
    __table_args__ = (CheckConstraint("status IN ('in_progress','ended')"), CheckConstraint('gain_account_id <> loss_account_id'), CheckConstraint("length(trim(name)) > 0"))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String, default='')
    status: Mapped[str] = mapped_column(String, default='in_progress')
    gain_account_id: Mapped[str] = mapped_column(ForeignKey('fund_accounts.id'), unique=True)
    loss_account_id: Mapped[str] = mapped_column(ForeignKey('fund_accounts.id'), unique=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StockStocktake(Base):
    __tablename__ = 'stock_stocktakes'
    __table_args__ = (CheckConstraint("status IN ('in_progress','ended')"), CheckConstraint('gain_account_id <> loss_account_id'), CheckConstraint("length(trim(name)) > 0"))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String, default='')
    status: Mapped[str] = mapped_column(String, default='in_progress')
    gain_account_id: Mapped[str] = mapped_column(ForeignKey('stock_accounts.id'), unique=True)
    loss_account_id: Mapped[str] = mapped_column(ForeignKey('stock_accounts.id'), unique=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
