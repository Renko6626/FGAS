from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

class DomainError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def yuan_to_minor(value: str) -> int:
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?', value):
        raise DomainError('金额须为正数，最多两位小数')
    amount = int(Decimal(value) * 100)
    if amount <= 0 or amount > 9223372036854775807:
        raise DomainError('金额超出有效范围')
    return amount

@dataclass(frozen=True)
class Line:
    account_id: str
    debit_minor: int
    credit_minor: int


def balanced_transfer(source: str, destination: str, amount: int) -> tuple[Line, Line]:
    if source == destination or amount <= 0:
        raise DomainError('来源与去向须不同，金额须大于零')
    return Line(source, 0, amount), Line(destination, amount, 0)
