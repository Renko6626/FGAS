from backend.kernel.accounting import DomainError


def validate_confirmation(declared_minor: int, confirmed_minor: int, reason: str) -> None:
    if type(confirmed_minor) is not int or not 0 < confirmed_minor <= declared_minor:
        raise DomainError('确认金额须大于零且不超过申报金额')
    if confirmed_minor != declared_minor and not reason.strip():
        raise DomainError('确认金额不一致须填写原因')
