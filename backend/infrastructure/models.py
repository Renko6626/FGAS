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
class LoginSession(Base):
    __tablename__ = 'login_sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
class Account(Base):
    __tablename__ = 'ledger_accounts'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    tags: Mapped[list] = mapped_column(JSON, default=list)
class FundAccount(Base):
    __tablename__ = 'fund_accounts'
    account_id: Mapped[str] = mapped_column(ForeignKey('ledger_accounts.id'), primary_key=True)
class Location(Base):
    __tablename__ = 'stock_locations'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    custodian_label: Mapped[str] = mapped_column(String, default='')
    tags: Mapped[list] = mapped_column(JSON, default=list)
class Transfer(Base):
    __tablename__ = 'transfers'
    __table_args__ = (UniqueConstraint('actor_id', 'idempotency_key'), CheckConstraint('amount_minor > 0'))
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    source_account_id: Mapped[str] = mapped_column(ForeignKey('ledger_accounts.id'))
    destination_account_id: Mapped[str] = mapped_column(ForeignKey('ledger_accounts.id'))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    effective_date: Mapped[object] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String, default='')
    counterparty: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    approval_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    reversal_of: Mapped[str | None] = mapped_column(ForeignKey('transfers.id'), nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class JournalLine(Base):
    __tablename__ = 'journal_lines'
    __table_args__ = (CheckConstraint('(debit_minor > 0 AND credit_minor = 0) OR (credit_minor > 0 AND debit_minor = 0)'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    transfer_id: Mapped[str] = mapped_column(ForeignKey('transfers.id'))
    account_id: Mapped[str] = mapped_column(ForeignKey('ledger_accounts.id'))
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

class Member(Base):
    __tablename__ = 'members'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    note: Mapped[str] = mapped_column(String, default='')
    account_id: Mapped[str] = mapped_column(ForeignKey('ledger_accounts.id'), unique=True)
class MemberClaim(Base):
    __tablename__ = 'member_claims'
    __table_args__ = (CheckConstraint('declared_minor > 0'), CheckConstraint('confirmed_minor IS NULL OR (confirmed_minor > 0 AND confirmed_minor <= declared_minor)'))
    transfer_id: Mapped[str] = mapped_column(ForeignKey('transfers.id'), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey('members.id'))
    declared_minor: Mapped[int] = mapped_column(BigInteger)
    confirmed_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    basis: Mapped[str] = mapped_column(String)
    confirmation_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
class Repayment(Base):
    __tablename__ = 'repayments'
    transfer_id: Mapped[str] = mapped_column(ForeignKey('transfers.id'), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey('members.id'))
    basis: Mapped[str] = mapped_column(String)
    allocation_mode: Mapped[str] = mapped_column(String)
class RepaymentAllocation(Base):
    __tablename__ = 'repayment_allocations'
    __table_args__ = (CheckConstraint('amount_minor > 0'),)
    repayment_id: Mapped[str] = mapped_column(ForeignKey('repayments.transfer_id'), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey('member_claims.transfer_id'), primary_key=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)


class Sku(Base):
    __tablename__ = 'skus'
    __table_args__ = (CheckConstraint('quantity_scale BETWEEN 0 AND 3'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    specification: Mapped[str] = mapped_column(String, default='')
    unit: Mapped[str] = mapped_column(String)
    quantity_scale: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class LocationProfile(Base):
    __tablename__ = 'stock_location_profiles'
    __table_args__ = (CheckConstraint("(kind = 'physical' AND external_kind IS NULL) OR (kind = 'external' AND external_kind IS NOT NULL AND external_kind IN ('supplier','customer','opening','loss','adjustment_gain','adjustment_loss'))"),)
    location_id: Mapped[str] = mapped_column(ForeignKey('stock_locations.id'), primary_key=True)
    kind: Mapped[str] = mapped_column(String)
    external_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class LocationCustody(Base):
    __tablename__ = 'location_custodies'
    __table_args__ = (
        CheckConstraint('valid_to IS NULL OR valid_to >= valid_from'),
        Index('one_current_location_custody', 'location_id', unique=True, postgresql_where=text('valid_to IS NULL')),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    location_id: Mapped[str] = mapped_column(ForeignKey('stock_locations.id'))
    member_id: Mapped[str] = mapped_column(ForeignKey('members.id'))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    ended_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
