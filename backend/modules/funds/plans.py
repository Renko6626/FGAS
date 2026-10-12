from backend.kernel.accounting import balanced_transfer, yuan_to_minor

def transfer_plan(source, destination, amount):
    return balanced_transfer(source, destination, yuan_to_minor(amount))
