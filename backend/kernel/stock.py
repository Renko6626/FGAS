import re
from backend.kernel.accounting import DomainError

def parse_quantity(value, allow_zero=False):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+', value):
        raise DomainError('数量须为整数数字字符串')
    # Bound length before converting arbitrary input into a Python integer.
    digits = value.lstrip('0')
    if not digits and allow_zero: return 0
    if not digits or len(digits) > 16: raise DomainError('数量超出有效范围')
    minor = int(digits)
    if minor > 9007199254740991: raise DomainError('数量超出有效范围')
    return minor


def quantity_string(minor):
    return str(minor)
