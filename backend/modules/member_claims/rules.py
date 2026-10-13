from backend.kernel.accounting import DomainError


def validate_confirmation(declared_minor: int, confirmed_minor: int, reason: str) -> None:
    if type(confirmed_minor) is not int or not 0 < confirmed_minor <= declared_minor:
        raise DomainError('确认金额须大于零且不超过申报金额')
    if confirmed_minor != declared_minor and not reason.strip():
        raise DomainError('确认金额不一致须填写原因')


from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OpenClaim:
    id: str
    member_id: str
    confirmed_at: datetime
    version: int
    outstanding_minor: int


def allocate_oldest(claims: list[OpenClaim], amount_minor: int) -> list[tuple[str, int]]:
    if type(amount_minor) is not int or amount_minor <= 0:
        raise DomainError('偿还金额须大于零')
    remaining = amount_minor
    result = []
    for claim in sorted(claims, key=lambda item: (item.confirmed_at, item.id)):
        amount = min(max(claim.outstanding_minor, 0), remaining)
        if amount:
            result.append((claim.id, amount))
            remaining -= amount
        if not remaining: break
    if remaining: raise DomainError('偿还金额超过未结垫付')
    return result


def validate_allocations(claims: list[OpenClaim], member_id: str, amount_minor: int,
                         allocations: list[tuple[str, int]]) -> None:
    available = {claim.id: claim for claim in claims}
    seen = set()
    total = 0
    for identifier, amount in allocations:
        claim = available.get(identifier)
        if not claim or claim.member_id != member_id: raise DomainError('匹配垫付须属于该成员且已确认')
        if identifier in seen or type(amount) is not int or amount <= 0:
            raise DomainError('匹配金额或重复匹配无效')
        if amount > claim.outstanding_minor: raise DomainError('匹配金额超过垫付未结金额')
        seen.add(identifier)
        total += amount
    if type(amount_minor) is not int or amount_minor <= 0 or total != amount_minor:
        raise DomainError('匹配总额须等于偿还金额')
