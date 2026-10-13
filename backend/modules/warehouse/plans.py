"""One immutable whole-transfer move plan, without persistence."""
def build_moves(source_id, destination_id, lines):
    return [dict(source_account_id=source_id, destination_account_id=destination_id, transfer_line_id=line['id'], sku_id=line['sku_id'], quantity=line['quantity']) for line in lines]
