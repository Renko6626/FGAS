import re
from backend.kernel.accounting import DomainError

def quantity_to_minor(value, scale, allow_zero=False):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value):
        raise DomainError('数量须为正十进制字符串')
    whole, _, fraction = value.partition('.')
    if len(fraction) > scale: raise DomainError('数量超过 SKU 精度')
    # Bound length before converting arbitrary input into a Python integer.
    digits = (whole + fraction.ljust(scale, '0')).lstrip('0')
    if not digits and allow_zero: return 0
    if not digits or len(digits) > 16: raise DomainError('数量超出有效范围')
    minor = int(digits)
    if minor > 9007199254740991: raise DomainError('数量超出有效范围')
    return minor


def quantity_string(minor, scale):
    if not scale: return str(minor)
    whole, fraction = divmod(minor, 10 ** scale)
    return f'{whole}.{fraction:0{scale}d}'


def validate_move(source_kind, destination_kind, quantity_minor, available_minor):
    if source_kind == destination_kind == 'external': raise DomainError('不能在两个外部位置间转移')
    if quantity_minor <= 0: raise DomainError('数量必须为正')
    if source_kind == 'physical' and (available_minor is None or available_minor < quantity_minor):
        raise DomainError('来源库存不足', 409)
