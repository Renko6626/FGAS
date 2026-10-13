"""One immutable whole-transfer move plan, without persistence."""
def build_moves(source_id, destination_id, lines):
    return [dict(source_location_id=source_id, destination_location_id=destination_id, transfer_line_id=line['id'], sku_id=line['sku_id'], quantity_minor=line['quantity_minor']) for line in lines]
