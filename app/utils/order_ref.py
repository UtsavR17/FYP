# order_ref.py
# Online order references (Task 40). Since Fix Phase 7 (DEC-15) the Admin Panel
# shows online orders by their plain number, like every other record. These are
# thin wrappers around app/utils/ids.py, kept so existing imports and the Jinja
# filter "order_ref" keep working. The shop (a different repo) keeps its own
# customer-facing "ORD-000012" reference.

from app.utils.ids import display_id, parse_id_query


def format_order_ref(order_id):
    """12 -> '12'. Returns '-' for a missing or invalid id."""
    return display_id(order_id)


def parse_order_query(text):
    """
    Order number typed in a search box: 'ORD-000012', 'ord12', '000012' or
    '12' all give 12. Anything else gives None.
    """
    return parse_id_query(text, 'order')
