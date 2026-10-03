"""
Supplier portal data helpers (Task 35).

Every helper takes the per-request supplier client as its first argument, so
all reads and writes run as the supplier and are limited by RLS. The logic is
copied from the admin Supplier and Purchase Order modules, which use the
shared admin client and must not be called from the portal.
"""
from datetime import datetime, timedelta, timezone

from app.utils.validators import is_positive_number

# The pure (client-free) model spec validator is shared with the admin module
# so both sides accept exactly the same values.
from app.modules.supplier.routes import _validate_model_specs as validate_model_specs  # noqa: F401
from app.modules.new_motorbike.routes import (  # noqa: F401
    FUEL_TYPE_OPTIONS,
    TRANSMISSION_OPTIONS,
)


MAURITIUS_TZ = timezone(timedelta(hours=4))

# A supplier may only ship lines on an order that is still open
OPEN_PO_STATUSES = ('Pending', 'Partially Received')

MAX_PRICE = 99999999.99   # NUMERIC(10,2)
MIN_SHIPPED_YEAR = 1990


def mauritius_today():
    """Today's date in Mauritius time (UTC+4)."""
    return datetime.now(MAURITIUS_TZ).date()


def format_date(raw_value, with_year=True):
    """'2026-10-02' -> '02 Oct 2026'. Empty or invalid values give ''."""
    try:
        value = datetime.strptime(str(raw_value)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return ''
    return value.strftime('%d %b %Y' if with_year else '%d %b')


def error_text(error):
    """Plain message text from a Supabase / PostgREST exception."""
    return str(getattr(error, 'message', None) or error)


def is_duplicate_error(error):
    text = error_text(error).lower()
    code = str(getattr(error, 'code', '') or '')
    return code == '23505' or 'duplicate' in text or 'unique' in text


def is_foreign_key_error(error):
    text = error_text(error).lower()
    code = str(getattr(error, 'code', '') or '')
    return code == '23503' or 'foreign key' in text


def friendly_shipping_error(error):
    """
    Translate a guard-trigger, RLS or constraint error raised while shipping
    into a message a supplier can act on.
    """
    text = error_text(error).lower()
    if 'purchase order is closed' in text:
        return 'This purchase order is closed, so it can no longer be shipped.'
    if 'can no longer be changed by the supplier' in text:
        return 'This line has already been shipped or received and can no longer be changed.'
    if 'suppliers may only' in text:
        return 'Only the shipping details of a line can be changed from the portal.'
    if is_duplicate_error(error):
        return 'This VIN already exists.'
    if 'row-level security' in text or str(getattr(error, 'code', '')) == '42501':
        return 'You do not have permission to change this line.'
    return 'The line could not be saved. Please try again.'


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------

def parse_price(raw_value, label='Buying price'):
    """Required, positive (greater than 0) price. Returns (float_or_None, error_or_None)."""
    value = (raw_value or '').strip()
    if not value:
        return None, f'{label} is required.'
    if not is_positive_number(value):
        return None, f'{label} must be a valid number greater than 0.'
    price = float(value)
    if price <= 0:
        return None, f'{label} must be greater than 0.'
    if price > MAX_PRICE:
        return None, f'{label} must not exceed {MAX_PRICE:,.2f}.'
    return round(price, 2), None


def parse_option_id(raw_value, allowed_ids, required_msg, invalid_msg):
    """Integer id that must be one of allowed_ids. Returns (id_or_None, error_or_None)."""
    value = (raw_value or '').strip()
    if not value:
        return None, required_msg
    try:
        parsed = int(value)
    except ValueError:
        return None, invalid_msg
    if parsed not in allowed_ids:
        return None, invalid_msg
    return parsed, None


def validate_shipped_vin(raw_value):
    """
    Same rules as the admin New_MotorBike VIN (required, at most 50 characters),
    plus trimming and upper-casing. Returns (vin_or_None, error_or_None).
    """
    vin = (raw_value or '').strip().upper()
    if not vin:
        return None, 'VIN is required.'
    if len(vin) > 50:
        return None, 'VIN must not exceed 50 characters.'
    return vin, None


def validate_shipped_year(raw_value, today=None):
    """
    Whole number between 1990 and next year. This range sits inside the admin
    New_MotorBike rule (1900 to 2100), so receiving never rejects it.
    """
    today = today or mauritius_today()
    max_year = today.year + 1
    value = (raw_value or '').strip()
    if not value:
        return None, 'Year is required.'
    try:
        year = int(value)
    except ValueError:
        return None, 'Year must be a valid 4-digit number.'
    if year < MIN_SHIPPED_YEAR or year > max_year:
        return None, f'Year must be between {MIN_SHIPPED_YEAR} and {max_year}.'
    return year, None


# -----------------------------------------------------------------------------
# Reference data (read-only for suppliers)
# -----------------------------------------------------------------------------

def get_brand_lookup(client):
    try:
        result = client.table('Brand').select('Brand_ID, Brand_Name').execute()
        return {r['Brand_ID']: r['Brand_Name'] for r in (result.data or [])}
    except Exception:
        return {}


def get_spare_part_lookup(client):
    try:
        result = client.table('Spare_Parts').select('SP_id, SP_name').execute()
        return {r['SP_id']: r['SP_name'] for r in (result.data or [])}
    except Exception:
        return {}


def get_model_lookup(client, brand_lookup=None):
    """{Model_No: 'Brand - Description'}"""
    brand_lookup = brand_lookup if brand_lookup is not None else get_brand_lookup(client)
    try:
        result = (
            client.table('Model')
            .select('Model_No, Brand_Brand_ID, Description')
            .order('Description')
            .execute()
        )
    except Exception:
        return {}
    return {
        m['Model_No']: f"{brand_lookup.get(m.get('Brand_Brand_ID'), 'Unknown Brand')} - {m['Description']}"
        for m in (result.data or [])
    }


def get_spare_part_options(client):
    """(SP_id, SP_name) tuples ordered by SP_name."""
    lookup = get_spare_part_lookup(client)
    return sorted(lookup.items(), key=lambda pair: (pair[1] or '').lower())


def get_brand_options(client):
    """(Brand_ID, Brand_Name) tuples ordered by Brand_Name."""
    lookup = get_brand_lookup(client)
    return sorted(lookup.items(), key=lambda pair: (pair[1] or '').lower())


def get_model_options(client, exclude_model_nos=None):
    """(Model_No, label) tuples ordered by label, minus models already listed."""
    exclude_model_nos = exclude_model_nos or set()
    lookup = get_model_lookup(client)
    return sorted(
        ((no, label) for no, label in lookup.items() if no not in exclude_model_nos),
        key=lambda pair: pair[1].lower(),
    )


# -----------------------------------------------------------------------------
# Catalogue (Supplier_Product / Supplier_Model)
# -----------------------------------------------------------------------------

def enrich_supplier_products(client, rows):
    """Attach _sp_name and _brand_name to each Supplier_Product row."""
    sp_lookup = get_spare_part_lookup(client)
    brand_lookup = get_brand_lookup(client)
    for r in rows:
        r['_sp_name'] = sp_lookup.get(r.get('SP_id'), f"SP-{r.get('SP_id')}")
        r['_brand_name'] = brand_lookup.get(r.get('Brand_Brand_ID'), 'Unknown Brand')
    return rows


def enrich_supplier_models(client, rows):
    """Attach _model_label to each Supplier_Model row."""
    model_lookup = get_model_lookup(client)
    for r in rows:
        r['_model_label'] = model_lookup.get(
            r.get('Model_Model_No'), f"Model #{r.get('Model_Model_No')}"
        )
    return rows


def get_catalogue_products(client, supplier_id):
    result = (
        client.table('Supplier_Product').select('*')
        .eq('Supplier_SupplierID', supplier_id)
        .order('SupplierProduct_ID')
        .execute()
    )
    return enrich_supplier_products(client, result.data or [])


def get_catalogue_models(client, supplier_id):
    result = (
        client.table('Supplier_Model').select('*')
        .eq('Supplier_SupplierID', supplier_id)
        .order('SupplierModel_ID')
        .execute()
    )
    return enrich_supplier_models(client, result.data or [])


def get_catalogue_row(client, table, id_column, row_id, supplier_id):
    """One catalogue row owned by this supplier, or None."""
    result = (
        client.table(table).select('*')
        .eq(id_column, row_id)
        .eq('Supplier_SupplierID', supplier_id)
        .limit(1)
        .execute()
    )
    return (result.data or [None])[0]


# -----------------------------------------------------------------------------
# Purchase orders
# -----------------------------------------------------------------------------

def get_supplier_pos(client, supplier_id):
    """This supplier's purchase orders, newest first."""
    result = (
        client.table('PurchaseOrder').select('*')
        .eq('Supplier_SupplierID', supplier_id)
        .order('PurchaseOrderID', desc=True)
        .execute()
    )
    return result.data or []


def get_owned_po(client, po_id, supplier_id):
    """The purchase order if it belongs to this supplier, otherwise None."""
    result = (
        client.table('PurchaseOrder').select('*')
        .eq('PurchaseOrderID', po_id)
        .eq('Supplier_SupplierID', supplier_id)
        .limit(1)
        .execute()
    )
    row = (result.data or [None])[0]
    if row and str(row.get('Supplier_SupplierID')) != str(supplier_id):
        return None
    return row


def get_po_items(client, po_ids):
    if not po_ids:
        return []
    result = (
        client.table('PurchaseOrderItem').select('*')
        .in_('PurchaseOrder_ID', list(po_ids))
        .order('POItem_ID')
        .execute()
    )
    return result.data or []


def get_po_bikes(client, po_ids):
    if not po_ids:
        return []
    result = (
        client.table('PO_NewMotorBike').select('*')
        .in_('PurchaseOrder_ID', list(po_ids))
        .order('POBike_ID')
        .execute()
    )
    return result.data or []


def item_awaits_shipment(item):
    return item.get('Status') == 'Ordered' and not item.get('DateShipped')


def bike_awaits_shipment(bike):
    return bike.get('Status') == 'Ordered'


def summarise_pos(pos, items, bikes):
    """Attach _line_count, _total and _awaiting (lines still to ship) to each PO."""
    by_po = {po['PurchaseOrderID']: po for po in pos}
    for po in pos:
        po['_line_count'] = 0
        po['_total'] = 0.0
        po['_awaiting'] = 0

    for item in items:
        po = by_po.get(item.get('PurchaseOrder_ID'))
        if not po:
            continue
        po['_line_count'] += 1
        po['_total'] += float(item.get('BuyingPrice') or 0) * int(item.get('Quantity_Ordered') or 0)
        if po.get('Status') in OPEN_PO_STATUSES and item_awaits_shipment(item):
            po['_awaiting'] += 1

    for bike in bikes:
        po = by_po.get(bike.get('PurchaseOrder_ID'))
        if not po:
            continue
        po['_line_count'] += 1
        po['_total'] += float(bike.get('BuyingPrice') or 0)
        if po.get('Status') in OPEN_PO_STATUSES and bike_awaits_shipment(bike):
            po['_awaiting'] += 1

    return pos


def enrich_po_items(client, items):
    """Attach _sp_name, _brand_name and _shipped_on to each PurchaseOrderItem."""
    sp_lookup = get_spare_part_lookup(client)
    brand_lookup = get_brand_lookup(client)

    brand_by_product = {}
    product_ids = [i['SupplierProduct_ID'] for i in items if i.get('SupplierProduct_ID')]
    if product_ids:
        try:
            result = (
                client.table('Supplier_Product')
                .select('SupplierProduct_ID, Brand_Brand_ID')
                .in_('SupplierProduct_ID', product_ids)
                .execute()
            )
            brand_by_product = {
                r['SupplierProduct_ID']: r['Brand_Brand_ID'] for r in (result.data or [])
            }
        except Exception:
            brand_by_product = {}

    for item in items:
        item['_sp_name'] = sp_lookup.get(item.get('SP_id'), f"SP-{item.get('SP_id')}")
        brand_id = brand_by_product.get(item.get('SupplierProduct_ID'))
        item['_brand_name'] = brand_lookup.get(brand_id, '-') if brand_id else '-'
        item['_shipped_on'] = format_date(item.get('DateShipped'))
    return items


def enrich_po_bikes(client, bikes):
    """Attach _model_label and _shipped_on to each PO_NewMotorBike line."""
    model_lookup = get_model_lookup(client)
    for bike in bikes:
        bike['_model_label'] = model_lookup.get(
            bike.get('Model_Model_No'), f"Model #{bike.get('Model_Model_No')}"
        )
        bike['_shipped_on'] = format_date(bike.get('DateShipped'))
    return bikes


def vin_in_use(client, vin):
    """True if the VIN is in New_MotorBike or already shipped on any order line."""
    return client.rpc('vin_in_use', {'p_vin': vin}).execute().data is True
