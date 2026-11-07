# ids.py
# Record identifiers in the Admin Panel (Fix Phase 7, ISS-21, decision DEC-15).
#
# The Admin Panel shows identifiers as plain numbers ("5", never "SALE-5" or
# "ORD-000012"). Where the type of a reference matters, a word goes next to the
# number ("Sale 5", "Online order 12"), usually as a small badge. Every page,
# flash message and dropdown label goes through these helpers so the formats
# cannot drift again. Database values, routes and URLs are not affected.
#
# Searches still accept the old prefixed forms people may have bookmarked or
# typed for years: parse_id_query() understands "SALE-5", "appt-#3", "ord12",
# "ORD-000012", "#5" and "5"; legacy_ref() gives the old display text so a
# list search can match old partial queries exactly as before.

import re

TYPE_WORDS = {
    'sale':           'Sale',
    'appointment':    'Appointment',
    'order':          'Online order',
    'payment':        'Payment',
    'purchase_order': 'Purchase order',
    'motorbike':      'Motorbike',
    'item':           'Item',
    'application':    'Application',
    'stock':          'Stock',
    'service':        'Service',
    'model':          'Model',
    'spare_part':     'Spare part',
}

# Prefixes accepted in a search box, per record type (lower case).
QUERY_PREFIXES = {
    'sale':           ('sale',),
    'appointment':    ('appt', 'appointment'),
    'order':          ('ord', 'order'),
    'payment':        ('pay', 'payment'),
    'purchase_order': ('po',),
    'motorbike':      ('nb',),
    'application':    ('app', 'application'),
    'item':           ('item',),
}

# Old display formats, used only to keep old partial searches working.
_LEGACY_FORMATS = {
    'sale':           'SALE-{}',
    'appointment':    'APPT-#{}',
    'payment':        'PAY-{}',
    'purchase_order': 'PO-{}',
    'motorbike':      'NB-{}',
}

_ID_QUERY_RE = re.compile(r'^\s*(?:([a-z]+)\s*-?\s*)?#?\s*0*(\d{1,9})\s*$', re.IGNORECASE)


def display_id(value):
    """5, '5' or '005' -> '5'. A missing or invalid id gives '-'."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return '-'
    return str(number) if number >= 0 else '-'


def typed_id(kind, value):
    """('sale', 5) -> 'Sale 5'. Used in titles, flash messages and dropdown labels."""
    return f'{TYPE_WORDS.get(kind, kind.capitalize())} {display_id(value)}'


def parse_id_query(text, kind):
    """
    The record number typed in a search box, or None. Accepts a plain number
    ('5', '#5', '000005') or one of the kind's prefixes followed by the number
    ('SALE-5', 'sale 5', 'APPT-#3', 'ord12', 'ORD-000012'). Case-insensitive.
    """
    match = _ID_QUERY_RE.match(text or '')
    if not match:
        return None
    prefix = (match.group(1) or '').lower()
    if prefix and prefix not in QUERY_PREFIXES.get(kind, ()):
        return None
    number = int(match.group(2))
    return number if number > 0 else None


def legacy_ref(kind, value):
    """Old display text in lower case ('sale-5'), for search haystacks only. Never displayed."""
    if kind == 'order':
        try:
            return f'ord-{int(value):06d}'
        except (TypeError, ValueError):
            return ''
    fmt = _LEGACY_FORMATS.get(kind)
    if not fmt or value is None:
        return ''
    return fmt.format(value).lower()
