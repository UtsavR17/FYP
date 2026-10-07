# order_ref.py
# Online order references (Task 40). Orders are shown as "ORD-" plus the id
# left-padded to 6 digits, e.g. ORD-000012. This is the single helper used by
# the Online Orders module, the Payments module and the dashboard, and it is
# registered as the Jinja filter "order_ref".

import re

ORDER_ID_PREFIX = 'ORD-'

_ORDER_QUERY_RE = re.compile(r'^\s*(?:ORD-?)?0*(\d{1,9})\s*$', re.IGNORECASE)


def format_order_ref(order_id):
    """12 -> 'ORD-000012'. Returns '-' for a missing or invalid id."""
    try:
        return f'{ORDER_ID_PREFIX}{int(order_id):06d}'
    except (TypeError, ValueError):
        return '-'


def parse_order_query(text):
    """
    Order number typed in a search box: 'ORD-000012', 'ord12', '000012' or
    '12' all give 12. Anything else gives None.
    """
    match = _ORDER_QUERY_RE.match(text or '')
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None
