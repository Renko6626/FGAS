import re
from backend.kernel.accounting import DomainError

def quantity_to_minor(value, allow_zero=False):
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


def validate_move(source_kind, destination_kind, quantity_minor, available_minor):
    if source_kind == destination_kind == 'external': raise DomainError('不能在两个外部位置间转移')
    if quantity_minor <= 0: raise DomainError('数量必须为正')
    if source_kind == 'physical' and (available_minor is None or available_minor < quantity_minor):
        raise DomainError('来源库存不足', 409)
