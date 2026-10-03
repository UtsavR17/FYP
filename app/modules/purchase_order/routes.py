from datetime import date as date_type
from flask import render_template, request, redirect, url_for
from app.modules.purchase_order import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields, is_positive_integer, is_positive_number

from app.modules.new_motorbike.routes import (
    _validate_form as _validate_new_motorbike_fields,
    _get_form_options as _get_new_motorbike_dropdown_options,
    FUEL_TYPE_OPTIONS as NB_FUEL_TYPE_OPTIONS,
    TRANSMISSION_OPTIONS as NB_TRANSMISSION_OPTIONS,
    STATUS_OPTIONS as NB_STATUS_OPTIONS,
)

# Predefined Status values for Purchase Orders
PO_STATUS_OPTIONS = [
    ('Pending',            'Pending'),
    ('Partially Received', 'Partially Received'),
    ('Received',           'Received'),
    ('Cancelled',          'Cancelled'),
]


def _get_supplier_options():
    """Fetch Supplier dropdown options ordered by SupplierName."""
    try:
        result = (
            supabase.table('Supplier')
            .select('SupplierID, SupplierName')
            .order('SupplierName')
            .execute()
        )
        return [
            (r['SupplierID'], r['SupplierName'])
            for r in (result.data or [])
        ]
    except Exception:
        return []


def _format_shipped_date(raw_value, with_year=False):
    """'2026-10-02' -> '02 Oct' (or '02 Oct 2026'). Empty or invalid values give ''."""
    try:
        value = date_type.fromisoformat(str(raw_value)[:10])
    except (TypeError, ValueError):
        return ''
    return value.strftime('%d %b %Y' if with_year else '%d %b')


def _validate_date(raw_value, field_label):
    """
    Validate an optional date string in YYYY-MM-DD format.

    Returns:
        (date_string_or_None, error_string_or_None)
    """
    value = (raw_value or '').strip()
    if not value:
        return None, f'{field_label} is required.'
    try:
        date_type.fromisoformat(value)
        return value, None
    except ValueError:
        return None, f'{field_label} must be a valid date.'


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('PurchaseOrder')
            .select('*')
            .order('PurchaseOrderID', desc=True)
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load purchase orders: {str(e)}')
        all_records = []

    # Build Supplier lookup dict
    try:
        sup_result = (
            supabase.table('Supplier')
            .select('SupplierID, SupplierName')
            .execute()
        )
        supplier_lookup = {
            r['SupplierID']: r['SupplierName']
            for r in (sup_result.data or [])
        }
    except Exception:
        supplier_lookup = {}

    # Enrich each record
    for po in all_records:
        po['_supplier_name'] = supplier_lookup.get(
            po.get('Supplier_SupplierID'), '—'
        )

    # Search
    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('_supplier_name', '').lower()
            or q in r.get('Status', '').lower()
            or q in str(r.get('POrderDate', '') or '')
            or q in str(r.get('ExpectedDate', '') or '')
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/purchase_order/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors = {}
    supplier_options = _get_supplier_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        supplier_id_raw   = form_data.get('Supplier_SupplierID', '').strip()
        expected_date_raw = form_data.get('ExpectedDate', '').strip()

        supplier_id = None
        if not supplier_id_raw:
            errors['Supplier_SupplierID'] = 'Supplier is required.'
        else:
            try:
                supplier_id = int(supplier_id_raw)
            except ValueError:
                errors['Supplier_SupplierID'] = 'Please select a valid supplier.'

        porder_date = date_type.today().isoformat()   # recorded automatically
        expected_date, exp_err = _validate_date(expected_date_raw, 'Expected Date')
        if exp_err:
            errors['ExpectedDate'] = exp_err
        elif expected_date < porder_date:
            errors['ExpectedDate'] = 'Expected date cannot be before today.'

        if not errors:
            try:
                created = supabase.table('PurchaseOrder').insert({
                    'POrderDate':          porder_date,
                    'ExpectedDate':        expected_date,
                    'Status':              'Pending',
                    'Supplier_SupplierID': supplier_id,
                }).execute()
                new_po_id = created.data[0]['PurchaseOrderID']
                flash_success('Purchase order created. Add spare parts or motorcycles below.')
                return redirect(url_for('purchase_order.view', po_id=new_po_id))
            except Exception as e:
                flash_error(f'Could not create purchase order: {str(e)}')

    return render_template(
        'modules/purchase_order/form.html',
        form_data=form_data, errors=errors, is_edit=False,
        supplier_options=supplier_options, status_options=PO_STATUS_OPTIONS
    )


@bp.route('/edit/<int:po_id>', methods=['GET', 'POST'])
@login_required
def edit(po_id):
    try:
        result = (
            supabase.table('PurchaseOrder')
            .select('*')
            .eq('PurchaseOrderID', po_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Purchase order ID {po_id} was not found.')
        return redirect(url_for('purchase_order.index'))

    errors = {}
    form_data = record.copy()
    supplier_options = _get_supplier_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        supplier_id_raw   = form_data.get('Supplier_SupplierID', '').strip()
        porder_date_raw   = form_data.get('POrderDate', '').strip()
        expected_date_raw = form_data.get('ExpectedDate', '').strip()
        status_value      = form_data.get('Status', '').strip()

        supplier_id = None
        if not supplier_id_raw:
            errors['Supplier_SupplierID'] = 'Supplier is required.'
        else:
            try:
                supplier_id = int(supplier_id_raw)
            except ValueError:
                errors['Supplier_SupplierID'] = 'Please select a valid supplier.'

        porder_date,   porder_err = _validate_date(porder_date_raw,  'Order Date')
        expected_date, exp_err    = _validate_date(expected_date_raw, 'Expected Date')

        if porder_err:
            errors['POrderDate'] = porder_err
        if exp_err:
            errors['ExpectedDate'] = exp_err

        if (not porder_err and not exp_err
                and porder_date and expected_date
                and expected_date < porder_date):
            errors['ExpectedDate'] = (
                'Expected date must be on or after the order date.'
            )

        valid_statuses = [s for s, _ in PO_STATUS_OPTIONS]
        if not status_value:
            errors['Status'] = 'Status is required.'
        elif status_value not in valid_statuses:
            errors['Status'] = 'Please select a valid status.'

        if not errors:
            try:
                supabase.table('PurchaseOrder').update({
                    'POrderDate':          porder_date,
                    'ExpectedDate':        expected_date,
                    'Status':              status_value,
                    'Supplier_SupplierID': supplier_id,
                }).eq('PurchaseOrderID', po_id).execute()
                flash_success(f'Purchase order PO-{po_id} was updated successfully.')
                return redirect(url_for('purchase_order.index'))
            except Exception as e:
                flash_error(f'Could not update purchase order: {str(e)}')

    return render_template(
        'modules/purchase_order/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        supplier_options=supplier_options,
        status_options=PO_STATUS_OPTIONS
    )


@bp.route('/view/<int:po_id>')
@login_required
def view(po_id):
    try:
        result = (
            supabase.table('PurchaseOrder')
            .select('*')
            .eq('PurchaseOrderID', po_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Purchase order ID {po_id} was not found.')
        return redirect(url_for('purchase_order.index'))

    # Resolve supplier name
    supplier_name = '—'
    try:
        sup_result = (
            supabase.table('Supplier')
            .select('SupplierName')
            .eq('SupplierID', record.get('Supplier_SupplierID'))
            .single()
            .execute()
        )
        supplier_name = sup_result.data.get('SupplierName', '-')
    except Exception:
        pass

    # Fetch PO items wirh SP name 
    po_items = []
    try:
        items_result = (
            supabase.table('PurchaseOrderItem')
            .select('*')
            .eq('PurchaseOrder_ID', po_id)
            .order('POItem_ID')
            .execute()
        )
        po_items = items_result.data or []
    except Exception:
        pass
    
    #build spare part name lookup for item display

    sp_lookup_view={}
    try :
        sp_res = supabase.table('Spare_Parts').select('SP_id, SP_name').execute()
        sp_lookup_view={
            r['SP_id']: r['SP_name'] 
            for r in (sp_res.data or [])
        }

    except Exception:
        pass
    for item in po_items:
        item['_sp_name'] = sp_lookup_view.get(item.get('SP_id'), f"SP-{item.get('SP_id')}")
        item['_shipped_on'] = _format_shipped_date(item.get('DateShipped'))

    # Fetch linked New_MotorBike procurement rows
    po_motorbikes = []
    try:
        mb_result = (
            supabase.table('PO_NewMotorBike').select('*')
            .eq('PurchaseOrder_ID', po_id).order('POBike_ID').execute()
        )
        po_motorbikes = _enrich_po_motorbikes(mb_result.data or [])
    except Exception:
        pass

    po_items_total = sum(
        float(i.get('BuyingPrice') or 0) * int(i.get('Quantity_Ordered') or 0)
        for i in po_items
    )
    po_bikes_total = sum(float(m.get('BuyingPrice') or 0) for m in po_motorbikes)
    po_total = po_items_total + po_bikes_total

    return render_template(
    'modules/purchase_order/view.html',
    record=record,
    supplier_name=supplier_name,
    po_items=po_items,
    po_id=po_id,
    po_status=record.get('Status'),
    po_motorbikes=po_motorbikes,
    po_items_total=po_items_total,
    po_bikes_total=po_bikes_total,
    po_total=po_total
)


@bp.route('/delete/<int:po_id>', methods=['POST'])
@login_required
def delete(po_id):
    try:
        supabase.table('PurchaseOrder').delete().eq('PurchaseOrderID', po_id).execute()
        flash_success(f'Purchase order PO-{po_id} was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete PO-{po_id} because it has one or more line items. '
                f'Remove all items from this purchase order first.'
            )
        else:
            flash_error(f'Could not delete purchase order: {error_msg}')

    return redirect(url_for('purchase_order.index'))



# =============================================================================
# PURCHASE ORDER ITEM ROUTES
# Items are accessed through the PO view page, not through a sidebar link.

def _get_spare_part_options():
    """Fetch Spare Part dropdown options ordered by SP_name."""
    try:
        result = (
            supabase.table('Spare_Parts')
            .select('SP_id, SP_name')
            .order('SP_name')
            .execute()
        )
        return [(r['SP_id'], r['SP_name']) for r in (result.data or [])]
    except Exception:
        return []


def _get_brand_options():
    """Fetch Brand dropdown options ordered by Brand_Name."""
    try:
        result = (
            supabase.table('Brand')
            .select('Brand_ID, Brand_Name')
            .order('Brand_Name')
            .execute()
        )
        return [(r['Brand_ID'], r['Brand_Name']) for r in (result.data or [])]
    except Exception:
        return []


def _auto_update_po_status(po_id):
    """
    Recalculate PO Status from ALL lines: spare-part items and motorcycle lines.
      All Received  -> 'Received'
      Some Received -> 'Partially Received'
      None Received -> leave unchanged
    """
    try:
        statuses = []
        items = (
            supabase.table('PurchaseOrderItem').select('Status')
            .eq('PurchaseOrder_ID', po_id).execute()
        )
        statuses += [r.get('Status') for r in (items.data or [])]
        bikes = (
            supabase.table('PO_NewMotorBike').select('Status')
            .eq('PurchaseOrder_ID', po_id).execute()
        )
        statuses += [r.get('Status') for r in (bikes.data or [])]

        if not statuses:
            return
        received = sum(1 for s in statuses if s == 'Received')
        if received == len(statuses):
            new_status = 'Received'
        elif received > 0:
            new_status = 'Partially Received'
        else:
            return
        supabase.table('PurchaseOrder').update(
            {'Status': new_status}
        ).eq('PurchaseOrderID', po_id).execute()
    except Exception:
        pass


def _get_supplier_catalog_for_po(po_id):
    """
    Return the Supplier_Product catalog for the Supplier linked to this PO.
    Result: list of dicts with keys:
        SupplierProduct_ID, SP_id, Brand_Brand_ID,
        BuyingPrice, _sp_name, _brand_name
    Returns empty list if the supplier has no catalog entries yet.
    """
    # Resolve the supplier for this PO
    supplier_id = None
    try:
        po = (
            supabase.table('PurchaseOrder')
            .select('Supplier_SupplierID')
            .eq('PurchaseOrderID', po_id)
            .single()
            .execute()
        )
        supplier_id = po.data.get('Supplier_SupplierID')
    except Exception:
        return []

    if not supplier_id:
        return []

    # Fetch catalog rows
    rows = []
    try:
        result = (
            supabase.table('Supplier_Product')
            .select('SupplierProduct_ID, SP_id, Brand_Brand_ID, BuyingPrice')
            .eq('Supplier_SupplierID', supplier_id)
            .execute()
        )
        rows = result.data or []
    except Exception:
        return []

    if not rows:
        return []

    # Enrich with display names
    sp_lookup, brand_lookup = {}, {}
    try:
        sp_res = supabase.table('Spare_Parts').select('SP_id, SP_name').execute()
        sp_lookup = {r['SP_id']: r['SP_name'] for r in (sp_res.data or [])}
        br_res = supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
        brand_lookup = {r['Brand_ID']: r['Brand_Name'] for r in (br_res.data or [])}
    except Exception:
        pass

    for r in rows:
        r['_sp_name'] = sp_lookup.get(r['SP_id'], f"SP-{r['SP_id']}")
        r['_brand_name'] = brand_lookup.get(r['Brand_Brand_ID'], 'Unknown Brand')

    return rows


def _catalog_to_dropdown_options(catalog_rows, already_added_sp_ids=None):
    """
    Convert catalog rows to (SupplierProduct_ID, label) tuples for the
    select_field macro, optionally excluding parts already on this PO.
    Label format: 'SP_name — Brand_Name'
    """
    already_added_sp_ids = already_added_sp_ids or set()
    options = []
    for r in catalog_rows:
        if r['SP_id'] in already_added_sp_ids:
            continue
        label = f"{r['_sp_name']} \u2014 {r['_brand_name']}"
        options.append((r['SupplierProduct_ID'], label))
    return options


@bp.route('/<int:po_id>/items/add', methods=['GET', 'POST'])
@login_required
def add_item(po_id):
    """Add a line item to an existing Purchase Order."""
    try:
        po_result = (
            supabase.table('PurchaseOrder')
            .select('PurchaseOrderID, Status')
            .eq('PurchaseOrderID', po_id)
            .single()
            .execute()
        )
        po_record = po_result.data
    except Exception:
        flash_error(f'Purchase order ID {po_id} was not found.')
        return redirect(url_for('purchase_order.index'))

    # Block adding items to a closed PO
    locked_statuses = ('Received', 'Cancelled')
    if po_record.get('Status') in locked_statuses:
        flash_error(
            f'Cannot add items to PO-{po_id} because its status is '
            f'"{po_record.get("Status")}". '
            f'Only Pending or Partially Received orders can have items added.'
        )
        return redirect(url_for('purchase_order.view', po_id=po_id))

    # Build catalog for the dropdown — only parts this supplier supplies
    catalog = _get_supplier_catalog_for_po(po_id)

    # Get SP_ids already on this PO so we don't duplicate
    already_added_sp_ids = set()
    try:
        existing = (
            supabase.table('PurchaseOrderItem')
            .select('SP_id')
            .eq('PurchaseOrder_ID', po_id)
            .execute()
        )
        already_added_sp_ids = {r['SP_id'] for r in (existing.data or [])}
    except Exception:
        pass

    # Build a lookup dict so JS can auto-fill price/brand when part is selected
    # key = SupplierProduct_ID (string, matches option value from select_field)
    catalog_lookup = {
        str(r['SupplierProduct_ID']): {
            'buying_price': float(r['BuyingPrice']),
            'brand_name': r['_brand_name'],
        }
        for r in catalog
    }

    item_options = _catalog_to_dropdown_options(catalog, already_added_sp_ids)

    form_data = {}
    errors = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()

        sp_product_id_raw = form_data.get('SupplierProduct_ID', '').strip()
        qty_raw           = form_data.get('Quantity_Ordered', '').strip()
        price_raw         = form_data.get('BuyingPrice', '').strip()
        size_value        = form_data.get('Size_Expected', '').strip()

        # Resolve selected catalog entry
        supplier_product_id = None
        sp_id = None
        brand_id = None
        catalog_by_spid = {str(r['SupplierProduct_ID']): r for r in catalog}

        if not sp_product_id_raw:
            errors['SupplierProduct_ID'] = 'Please select a product from the supplier\'s catalogue.'
        else:
            try:
                supplier_product_id = int(sp_product_id_raw)
                catalog_row = catalog_by_spid.get(sp_product_id_raw)
                if catalog_row:
                    sp_id    = catalog_row['SP_id']
                    brand_id = catalog_row['Brand_Brand_ID']
                else:
                    errors['SupplierProduct_ID'] = 'Selected product is not in this supplier\'s catalogue.'
            except ValueError:
                errors['SupplierProduct_ID'] = 'Please select a valid product.'

        qty = None
        if not qty_raw:
            errors['Quantity_Ordered'] = 'Quantity ordered is required.'
        elif not is_positive_integer(qty_raw) or int(qty_raw) < 1:
            errors['Quantity_Ordered'] = 'Quantity must be a whole number of at least 1.'
        else:
            qty = int(qty_raw)

        price = None
        if not price_raw:
            errors['BuyingPrice'] = 'Buying price is required.'
        elif not is_positive_number(price_raw):
            errors['BuyingPrice'] = 'Buying price must be a valid number of 0 or more.'
        else:
            price = float(price_raw)

        if size_value and len(size_value) > 20:
            errors['Size_Expected'] = 'Expected size must not exceed 20 characters.'

        if not errors:
            try:
                supabase.table('PurchaseOrderItem').insert({
                    'PurchaseOrder_ID':   po_id,
                    'SP_id':              sp_id,
                    'SupplierProduct_ID': supplier_product_id,
                    'Quantity_Ordered':   qty,
                    'BuyingPrice':        price,
                    'Size_Expected':      size_value or None,
                    'Status':             'Ordered',
                }).execute()
                flash_success('Item was added to the purchase order successfully.')
                return redirect(url_for('purchase_order.view', po_id=po_id))
            except Exception as e:
                flash_error(f'Could not add item: {str(e)}')

    return render_template(
        'modules/purchase_order/item_form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        item_options=item_options,
        catalog_lookup=catalog_lookup,
        catalog_empty=(len(catalog) == 0),
        po_id=po_id
    )

@bp.route('/<int:po_id>/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(po_id, item_id):
    """Edit a line item that has not yet been received."""
    try:
        item_result = (
            supabase.table('PurchaseOrderItem')
            .select('*')
            .eq('POItem_ID', item_id)
            .eq('PurchaseOrder_ID', po_id)
            .single()
            .execute()
        )
        item = item_result.data
    except Exception:
        flash_error('Item not found.')
        return redirect(url_for('purchase_order.view', po_id=po_id))

    if item.get('Status') == 'Received':
        flash_error(
            'This item has already been received and cannot be edited. '
            'Adjust stock directly via the Stock module if needed.'
        )
        return redirect(url_for('purchase_order.view', po_id=po_id))

    form_data = item.copy()
    # Resolve SP name for the read-only display in item_form.html (edit mode)
    try:
        sp_res = (
            supabase.table('Spare_Parts')
            .select('SP_name')
            .eq('SP_id', item.get('SP_id'))
            .single()
            .execute()
        )
        form_data['_sp_name'] = sp_res.data.get('SP_name', f"SP-{item.get('SP_id')}")
    except Exception:
        form_data['_sp_name'] = f"SP-{item.get('SP_id')}"
            
    errors = {}
    sp_options = _get_spare_part_options()

    if request.method == 'POST':
        sp_name_display = form_data.get('_sp_name')
        form_data = request.form.to_dict()
        form_data['_sp_name'] = sp_name_display

        qty_raw    = form_data.get('Quantity_Ordered', '').strip()
        price_raw  = form_data.get('BuyingPrice', '').strip()
        size_value = form_data.get('Size_Expected', '').strip()

        qty = None
        if not qty_raw:
            errors['Quantity_Ordered'] = 'Quantity ordered is required.'
        elif not is_positive_integer(qty_raw) or int(qty_raw) < 1:
            errors['Quantity_Ordered'] = 'Quantity must be a whole number of at least 1.'
        else:
            qty = int(qty_raw)

        price = None
        if not price_raw:
            errors['BuyingPrice'] = 'Buying price is required.'
        elif not is_positive_number(price_raw):
            errors['BuyingPrice'] = 'Buying price must be a valid number of 0 or more.'
        else:
            price = float(price_raw)

        if size_value and len(size_value) > 20:
            errors['Size_Expected'] = 'Expected size must not exceed 20 characters.'

        if not errors:
            try:
                supabase.table('PurchaseOrderItem').update({
                    'Quantity_Ordered': qty,
                    'BuyingPrice':      price,
                    'Size_Expected':    size_value or None,
                }).eq('POItem_ID', item_id).execute()
                flash_success(f'Item #{item_id} was updated successfully.')
                return redirect(url_for('purchase_order.view', po_id=po_id))
            except Exception as e:
                flash_error(f'Could not update item: {str(e)}')

    return render_template(
        'modules/purchase_order/item_form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        sp_options=sp_options,
        po_id=po_id,
        item_id=item_id
    )


@bp.route('/<int:po_id>/items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(po_id, item_id):
    """Delete a PO line item. Only allowed if Status is Ordered."""
    try:
        item_result = (
            supabase.table('PurchaseOrderItem')
            .select('Status')
            .eq('POItem_ID', item_id)
            .eq('PurchaseOrder_ID', po_id)
            .single()
            .execute()
        )
        item_status = item_result.data.get('Status', '')
    except Exception:
        flash_error('Item not found.')
        return redirect(url_for('purchase_order.view', po_id=po_id))

    if item_status == 'Received':
        flash_error(
            f'Cannot delete item #{item_id} because it has already been received. '
            f'Deleting a received item would leave stock records inconsistent.'
        )
        return redirect(url_for('purchase_order.view', po_id=po_id))

    try:
        supabase.table('PurchaseOrderItem').delete().eq('POItem_ID', item_id).execute()
        flash_success(f'Item #{item_id} was removed from PO-{po_id}.')
        _auto_update_po_status(po_id)
    except Exception as e:
        flash_error(f'Could not delete item: {str(e)}')

    return redirect(url_for('purchase_order.view', po_id=po_id))


@bp.route('/<int:po_id>/items/<int:item_id>/receive', methods=['GET', 'POST'])
@login_required
def receive_item(po_id, item_id):
    """
    Receiving workflow for a single PO line item.

    GET:  Renders the receiving form showing existing stock options for this
          spare part plus a new stock creation form.

    POST: Executes one of two paths:
          - existing: UPDATE Stock.QOH += Quantity_Received
          - new:      INSERT new Stock record, QOH = Quantity_Received
          In both cases, the POItem is updated and the PO status auto-updates.
    """
    try:
        item_result = (
            supabase.table('PurchaseOrderItem')
            .select('*')
            .eq('POItem_ID', item_id)
            .eq('PurchaseOrder_ID', po_id)
            .single()
            .execute()
        )
        item = item_result.data
    except Exception:
        flash_error('Item not found.')
        return redirect(url_for('purchase_order.view', po_id=po_id))

    if item.get('Status') == 'Received':
        flash_error(f'Item #{item_id} has already been received.')
        return redirect(url_for('purchase_order.view', po_id=po_id))

    sp_id = item.get('SP_id')

    # Brand is fixed by the supplier catalogue row this item was ordered from
    locked_brand_id, locked_brand_name = None, None
    if item.get('SupplierProduct_ID'):
        try:
            sp_row = (
                supabase.table('Supplier_Product')
                .select('Brand_Brand_ID')
                .eq('SupplierProduct_ID', item['SupplierProduct_ID'])
                .single().execute()
            )
            locked_brand_id = sp_row.data.get('Brand_Brand_ID')
            br_row = (
                supabase.table('Brand').select('Brand_Name')
                .eq('Brand_ID', locked_brand_id).single().execute()
            )
            locked_brand_name = br_row.data.get('Brand_Name')
        except Exception:
            locked_brand_id, locked_brand_name = None, None

    # Resolve spare part name for display
    sp_name = f'SP-{sp_id}'
    try:
        sp_res = (
            supabase.table('Spare_Parts')
            .select('SP_name')
            .eq('SP_id', sp_id)
            .single()
            .execute()
        )
        sp_name = sp_res.data.get('SP_name', sp_name)
    except Exception:
        pass

    # Fetch existing stock records for this spare part (for existing stock dropdown)
    existing_stock_options = []
    try:
        stock_query = (
            supabase.table('Stock')
            .select('Stock_ID, Size, Brand_Brand_ID, QOH')
            .eq('Spare_Parts_SP_id', sp_id)
        )
        if locked_brand_id:
            stock_query = stock_query.eq('Brand_Brand_ID', locked_brand_id)
        stock_res = stock_query.execute()
        brand_lookup_recv = {}
        try:
            br = supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
            brand_lookup_recv = {r['Brand_ID']: r['Brand_Name'] for r in (br.data or [])}
        except Exception:
            pass

        for s in (stock_res.data or []):
            size  = s.get('Size') or 'No size'
            brand = brand_lookup_recv.get(s.get('Brand_Brand_ID'), 'Unknown Brand')
            label = f"{size} \u2014 {brand} (QOH: {s.get('QOH', 0)})"
            existing_stock_options.append((s['Stock_ID'], label))
    except Exception:
        pass

    brand_options = _get_brand_options()
    form_data = {}
    errors = {}

    if request.method == 'POST':
        form_data    = request.form.to_dict()
        recv_mode    = form_data.get('receiving_mode', 'existing')
        qty_recv_raw = form_data.get('Quantity_Received', '').strip()
        date_recv_raw = form_data.get('DateReceived', '').strip()

        # Validate Quantity_Received
        qty_recv = None
        if not qty_recv_raw:
            errors['Quantity_Received'] = 'Quantity received is required.'
        elif not is_positive_integer(qty_recv_raw) or int(qty_recv_raw) < 1:
            errors['Quantity_Received'] = 'Quantity must be a whole number of at least 1.'
        elif int(qty_recv_raw) > item.get('Quantity_Ordered', 0):
            errors['Quantity_Received'] = (
                f'Quantity received cannot exceed quantity ordered '
                f'({item.get("Quantity_Ordered")}).'
            )
        else:
            qty_recv = int(qty_recv_raw)

        # Validate DateReceived
        date_recv, date_err = _validate_date(date_recv_raw, 'DateReceived')
        if date_err:
            errors['DateReceived'] = date_err
        elif date_recv:
            # DateReceived should not be  before the PO order date creation
            try:
                po_date_result = (
                    supabase.table('PurchaseOrder')
                    .select('POrderDate')
                    .eq('PurchaseOrderID', po_id)
                    .single()
                    .execute()
                )
                po_order_date = po_date_result.data.get('POrderDate', '')
                if po_order_date and date_recv < po_order_date:
                    errors['DateReceived'] = (
                        'Date received cannot be before the order date'
                    )
            except Exception:
                pass 
                   

        # Mode-specific validation
        stock_id_to_link = None
        new_brand_id = None
        new_size = None
        new_price = None
        new_warranty = None

        if recv_mode == 'existing':
            stock_id_raw = form_data.get('Stock_Stock_ID', '').strip()
            if not stock_id_raw:
                errors['Stock_Stock_ID'] = 'Please select an existing stock record.'
            else:
                try:
                    stock_id_to_link = int(stock_id_raw)
                    allowed_ids = {sid for sid, _ in existing_stock_options}
                    if stock_id_to_link not in allowed_ids:
                        errors['Stock_Stock_ID'] = 'That stock record does not match this item.'
                except ValueError:
                    errors['Stock_Stock_ID'] = 'Invalid stock selection.'

        elif recv_mode == 'new':
            brand_id_raw    = form_data.get('Brand_Brand_ID', '').strip()
            new_size        = form_data.get('New_Size', '').strip() or None
            new_price_raw   = form_data.get('S_Price', '').strip()
            new_warranty_raw = form_data.get('Warranty', '').strip()

            if locked_brand_id:
                new_brand_id = locked_brand_id   # anything posted is ignored
            elif not brand_id_raw:
                errors['Brand_Brand_ID'] = 'Brand is required for new stock.'
            else:
                try:
                    new_brand_id = int(brand_id_raw)
                except ValueError:
                    errors['Brand_Brand_ID'] = 'Please select a valid brand.'

            if not new_price_raw:
                errors['S_Price'] = 'Selling price is required for new stock.'
            elif not is_positive_number(new_price_raw):
                errors['S_Price'] = 'Selling price must be a valid number of 0 or more.'
            else:
                new_price = float(new_price_raw)

            if not new_warranty_raw:
                errors['Warranty'] = 'Warranty is required for new stock.'
            elif not is_positive_integer(new_warranty_raw):
                errors['Warranty'] = 'Warranty must be a whole number of 0 or more.'
            else:
                new_warranty = int(new_warranty_raw)

        if not errors:
            try:
                if recv_mode == 'existing':
                    # CASE A — Update existing stock QOH
                    existing_result = (
                        supabase.table('Stock')
                        .select('QOH')
                        .eq('Stock_ID', stock_id_to_link)
                        .single()
                        .execute()
                    )
                    current_qoh = existing_result.data.get('QOH', 0)
                    supabase.table('Stock').update(
                        {'QOH': current_qoh + qty_recv}
                    ).eq('Stock_ID', stock_id_to_link).execute()

                elif recv_mode == 'new':
                    # CASE B — Create new stock record
                    new_stock_result = supabase.table('Stock').insert({
                        'Spare_Parts_SP_id': sp_id,
                        'Brand_Brand_ID':    new_brand_id,
                        'Size':              new_size,
                        'QOH':              qty_recv,
                        'S_Price':           new_price,
                        'Warranty':          new_warranty,
                    }).execute()
                    stock_id_to_link = new_stock_result.data[0]['Stock_ID']

                # Update the PO Item with receiving details
                supabase.table('PurchaseOrderItem').update({
                    'Quantity_Received': qty_recv,
                    'DateReceived':      date_recv,
                    'Stock_Stock_ID':    stock_id_to_link,
                    'Status':           'Received',
                }).eq('POItem_ID', item_id).execute()

                # Auto-update PO status
                _auto_update_po_status(po_id)

                action = 'updated existing stock' if recv_mode == 'existing' else 'created new stock'
                flash_success(
                    f'Item #{item_id} received successfully. '
                    f'Stock record was {action} (QOH adjusted by {qty_recv}).'
                )
                return redirect(url_for('purchase_order.view', po_id=po_id))

            except Exception as e:
                flash_error(f'Could not process receipt: {str(e)}')

    return render_template(
        'modules/purchase_order/receive_form.html',
        item=item,
        sp_name=sp_name,
        existing_stock_options=existing_stock_options,
        brand_options=brand_options,
        form_data=form_data,
        errors=errors,
        po_id=po_id,
        item_id=item_id,
        locked_brand_name=locked_brand_name
    )

def _get_model_catalog_for_po(po_id):
    """Supplier_Model rows for this PO's supplier, each with a _model_label."""
    try:
        po = (
            supabase.table('PurchaseOrder').select('Supplier_SupplierID')
            .eq('PurchaseOrderID', po_id).single().execute()
        )
        supplier_id = po.data.get('Supplier_SupplierID')
        rows = (
            supabase.table('Supplier_Model')
            .select('SupplierModel_ID, Model_Model_No, BuyingPrice')
            .eq('Supplier_SupplierID', supplier_id).execute()
        ).data or []
    except Exception:
        return []

    brand_lookup, model_lookup = {}, {}
    try:
        br = supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
        brand_lookup = {r['Brand_ID']: r['Brand_Name'] for r in (br.data or [])}
        ml = supabase.table('Model').select('Model_No, Brand_Brand_ID, Description').execute()
        for m in (ml.data or []):
            model_lookup[m['Model_No']] = (
                f"{brand_lookup.get(m.get('Brand_Brand_ID'), 'Unknown Brand')} "
                f"\u2014 {m['Description']}"
            )
    except Exception:
        pass

    for r in rows:
        r['_model_label'] = model_lookup.get(r['Model_Model_No'], f"Model #{r['Model_Model_No']}")
    return rows


def _enrich_po_motorbikes(rows):
    """
    Attach _model_label, _vin and _shipped_on to each PO_NewMotorBike row.
    _vin is the inventory VIN once received, otherwise the supplier's ShippedVIN.
    """
    brand_lookup, model_lookup = {}, {}
    try:
        br = supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
        brand_lookup = {r['Brand_ID']: r['Brand_Name'] for r in (br.data or [])}
        ml = supabase.table('Model').select('Model_No, Brand_Brand_ID, Description').execute()
        for m in (ml.data or []):
            model_lookup[m['Model_No']] = (
                f"{brand_lookup.get(m.get('Brand_Brand_ID'), 'Unknown Brand')} "
                f"\u2014 {m['Description']}"
            )
    except Exception:
        pass

    nb_ids = [r['New_MotorBike_NB_ID'] for r in rows if r.get('New_MotorBike_NB_ID')]
    vin_lookup = {}
    if nb_ids:
        try:
            bikes = (
                supabase.table('New_MotorBike').select('NB_ID, VIN')
                .in_('NB_ID', nb_ids).execute()
            )
            vin_lookup = {b['NB_ID']: b['VIN'] for b in (bikes.data or [])}
        except Exception:
            pass

    for r in rows:
        r['_model_label'] = model_lookup.get(r['Model_Model_No'], f"Model #{r['Model_Model_No']}")
        if r.get('New_MotorBike_NB_ID'):
            r['_vin'] = vin_lookup.get(r.get('New_MotorBike_NB_ID')) or r.get('ShippedVIN')
        else:
            r['_vin'] = r.get('ShippedVIN')
        r['_shipped_on'] = _format_shipped_date(r.get('DateShipped'))
    return rows


def _get_motorbike_line_or_redirect(po_id, pobike_id):
    try:
        line = (
            supabase.table('PO_NewMotorBike').select('*')
            .eq('POBike_ID', pobike_id).eq('PurchaseOrder_ID', po_id)
            .single().execute()
        ).data
        return line, None
    except Exception:
        flash_error('Motorcycle order line not found.')
        return None, redirect(url_for('purchase_order.view', po_id=po_id))


def _get_po_status(po_id):
    try:
        return (
            supabase.table('PurchaseOrder').select('Status')
            .eq('PurchaseOrderID', po_id).single().execute()
        ).data.get('Status')
    except Exception:
        return None


@bp.route('/<int:po_id>/motorbikes/add', methods=['GET', 'POST'])
@login_required
def add_motorbike(po_id):
    po_status = _get_po_status(po_id)
    if po_status is None:
        flash_error(f'Purchase order ID {po_id} was not found.')
        return redirect(url_for('purchase_order.index'))
    if po_status in ('Received', 'Cancelled'):
        flash_error(f'Cannot add motorcycles to PO-{po_id} because its status is "{po_status}".')
        return redirect(url_for('purchase_order.view', po_id=po_id))

    catalog = _get_model_catalog_for_po(po_id)
    catalog_lookup = {
        str(r['SupplierModel_ID']): {'buying_price': float(r['BuyingPrice'])}
        for r in catalog
    }
    model_options = [(r['SupplierModel_ID'], r['_model_label']) for r in catalog]
    _, color_options = _get_new_motorbike_dropdown_options()
    valid_colors = [c for c, _ in color_options]
    form_data, errors = {}, {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        sm_raw    = form_data.get('SupplierModel_ID', '').strip()
        color     = form_data.get('Color_Color', '').strip()
        qty_raw   = form_data.get('Quantity', '').strip()
        price_raw = form_data.get('BuyingPrice', '').strip()

        catalog_row = None
        if not sm_raw:
            errors['SupplierModel_ID'] = "Please select a model from the supplier's catalogue."
        else:
            catalog_row = next((r for r in catalog if str(r['SupplierModel_ID']) == sm_raw), None)
            if not catalog_row:
                errors['SupplierModel_ID'] = "Selected model is not in this supplier's catalogue."

        if not color:
            errors['Color_Color'] = 'Colour is required.'
        elif color not in valid_colors:
            errors['Color_Color'] = 'Please select a valid colour.'

        qty = None
        if not qty_raw:
            errors['Quantity'] = 'Quantity is required.'
        elif not is_positive_integer(qty_raw) or not (1 <= int(qty_raw) <= 25):
            errors['Quantity'] = 'Quantity must be a whole number between 1 and 25.'
        else:
            qty = int(qty_raw)

        price = None
        if not price_raw:
            errors['BuyingPrice'] = 'Buying price is required.'
        elif not is_positive_number(price_raw):
            errors['BuyingPrice'] = 'Buying price must be a valid number of 0 or more.'
        else:
            price = float(price_raw)

        if not errors:
            try:
                row = {
                    'PurchaseOrder_ID': po_id,
                    'Model_Model_No':   catalog_row['Model_Model_No'],
                    'SupplierModel_ID': catalog_row['SupplierModel_ID'],
                    'Color_Color':      color,
                    'BuyingPrice':      price,
                    'Status':           'Ordered',
                }
                supabase.table('PO_NewMotorBike').insert([dict(row) for _ in range(qty)]).execute()
                flash_success(f'{qty} motorcycle line{"s" if qty != 1 else ""} added to the purchase order.')
                return redirect(url_for('purchase_order.view', po_id=po_id))
            except Exception as e:
                flash_error(f'Could not add motorcycle: {str(e)}')

    return render_template(
        'modules/purchase_order/motorbike_form.html',
        form_data=form_data, errors=errors, is_edit=False, po_id=po_id,
        model_options=model_options, color_options=color_options,
        catalog_lookup=catalog_lookup, catalog_empty=(len(catalog) == 0)
    )


@bp.route('/<int:po_id>/motorbikes/<int:pobike_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_motorbike(po_id, pobike_id):
    line, redir = _get_motorbike_line_or_redirect(po_id, pobike_id)
    if redir:
        return redir
    if line.get('Status') == 'Received':
        flash_error('This motorcycle has already been received and cannot be edited.')
        return redirect(url_for('purchase_order.view', po_id=po_id))
    if line.get('Status') != 'Ordered':
        flash_error(
            'This motorcycle has been shipped by the supplier and cannot be edited. '
            'Revert the shipment first if the line needs to change.'
        )
        return redirect(url_for('purchase_order.view', po_id=po_id))

    model_label = _enrich_po_motorbikes([dict(line)])[0]['_model_label']
    _, color_options = _get_new_motorbike_dropdown_options()
    valid_colors = [c for c, _ in color_options]
    form_data = {'Color_Color': line.get('Color_Color', ''),
                 'BuyingPrice': str(line.get('BuyingPrice', '') or '')}
    errors = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        color     = form_data.get('Color_Color', '').strip()
        price_raw = form_data.get('BuyingPrice', '').strip()

        if not color:
            errors['Color_Color'] = 'Colour is required.'
        elif color not in valid_colors:
            errors['Color_Color'] = 'Please select a valid colour.'

        price = None
        if not price_raw:
            errors['BuyingPrice'] = 'Buying price is required.'
        elif not is_positive_number(price_raw):
            errors['BuyingPrice'] = 'Buying price must be a valid number of 0 or more.'
        else:
            price = float(price_raw)

        if not errors:
            try:
                # Status filter: the supplier may have shipped it since the form opened
                updated = supabase.table('PO_NewMotorBike').update(
                    {'Color_Color': color, 'BuyingPrice': price}
                ).eq('POBike_ID', pobike_id).eq('Status', 'Ordered').execute()
                if updated.data:
                    flash_success('Motorcycle order line updated.')
                else:
                    flash_error(
                        'This motorcycle line was not updated because it is no longer '
                        'Ordered (the supplier may have just shipped it).'
                    )
                return redirect(url_for('purchase_order.view', po_id=po_id))
            except Exception as e:
                flash_error(f'Could not update motorcycle line: {str(e)}')

    return render_template(
        'modules/purchase_order/motorbike_form.html',
        form_data=form_data, errors=errors, is_edit=True, po_id=po_id,
        model_label=model_label, color_options=color_options
    )


@bp.route('/<int:po_id>/motorbikes/<int:pobike_id>/delete', methods=['POST'])
@login_required
def delete_motorbike(po_id, pobike_id):
    line, redir = _get_motorbike_line_or_redirect(po_id, pobike_id)
    if redir:
        return redir
    if line.get('Status') == 'Received':
        flash_error('Cannot delete a motorcycle line that has already been received.')
        return redirect(url_for('purchase_order.view', po_id=po_id))
    if line.get('Status') != 'Ordered':
        flash_error(
            'Cannot delete a motorcycle line that the supplier has shipped. '
            'Revert the shipment first if the line should be removed.'
        )
        return redirect(url_for('purchase_order.view', po_id=po_id))
    try:
        deleted = (
            supabase.table('PO_NewMotorBike').delete()
            .eq('POBike_ID', pobike_id).eq('Status', 'Ordered').execute()
        )
        if deleted.data:
            flash_success('Motorcycle line removed from the purchase order.')
            _auto_update_po_status(po_id)
        else:
            flash_error(
                'This motorcycle line was not removed because it is no longer '
                'Ordered (the supplier may have just shipped it).'
            )
    except Exception as e:
        flash_error(f'Could not remove motorcycle line: {str(e)}')
    return redirect(url_for('purchase_order.view', po_id=po_id))


@bp.route('/<int:po_id>/motorbikes/<int:pobike_id>/receive', methods=['GET', 'POST'])
@login_required
def receive_motorbike(po_id, pobike_id):
    """
    Receiving creates the real New_MotorBike record (VIN, year, specs, selling
    price) for one ordered unit, then marks the order line Received.
    Model and Colour come from the order line and cannot be changed here.
    Status is always set to 'Available'.
    When the supplier shipped the line, VIN and Year come from ShippedVIN and
    ShippedYear and cannot be changed here either (Task 35).
    """
    line, redir = _get_motorbike_line_or_redirect(po_id, pobike_id)
    if redir:
        return redir
    if line.get('Status') == 'Received':
        flash_error('This motorcycle has already been received.')
        return redirect(url_for('purchase_order.view', po_id=po_id))
    if line.get('Status') not in ('Ordered', 'Shipped'):
        flash_error('This motorcycle line cannot be received in its current status.')
        return redirect(url_for('purchase_order.view', po_id=po_id))

    line = _enrich_po_motorbikes([dict(line)])[0]
    shipped = bool(line.get('ShippedVIN'))
    shipped_on = _format_shipped_date(line.get('DateShipped'), with_year=True)

    # Model-level specs come from the supplier catalogue when they are set
    locked_specs = None
    if line.get('SupplierModel_ID'):
        try:
            sm = (
                supabase.table('Supplier_Model')
                .select('EngineCC, FuelType, Transmission, FuelTankCapacity')
                .eq('SupplierModel_ID', line['SupplierModel_ID'])
                .single().execute()
            ).data
            keys = ('EngineCC', 'FuelType', 'Transmission', 'FuelTankCapacity')
            if sm and all(sm.get(k) not in (None, '') for k in keys):
                locked_specs = sm
        except Exception:
            locked_specs = None

    form_data, errors = {}, {}

    if request.method == 'POST':
        form_data = request.form.to_dict()

        if shipped:
            # Supplier values win: anything posted for VIN or Year is ignored
            form_data['VIN']  = line['ShippedVIN']
            form_data['Year'] = '' if line.get('ShippedYear') is None else str(line['ShippedYear'])

        check = dict(form_data)
        check['Model_Model_No'] = str(line['Model_Model_No'])
        check['Color_Color']    = line['Color_Color']
        check['Status']         = 'Available'
        if locked_specs:
            # Catalogue values win: anything posted for these fields is ignored
            check['EngineCC']         = str(locked_specs['EngineCC'])
            check['FuelType']         = locked_specs['FuelType']
            check['Transmission']     = locked_specs['Transmission']
            check['FuelTankCapacity'] = str(locked_specs['FuelTankCapacity'])

        errors, parsed = _validate_new_motorbike_fields(check)

        date_received, date_err = _validate_date(form_data.get('DateReceived', ''), 'Date Received')
        if date_err:
            errors['DateReceived'] = date_err

        if shipped:
            # VIN and Year are read-only on the form, so show their errors as a flash
            for field in ('VIN', 'Year'):
                if field in errors:
                    flash_error(
                        f'The {field} provided by the supplier is not valid: {errors[field]} '
                        f'Revert the shipment so the supplier can correct it.'
                    )

        if not errors:
            nb_id = None
            try:
                created = supabase.table('New_MotorBike').insert(parsed).execute()
                nb_id = created.data[0]['NB_ID']
            except Exception as e:
                msg = str(e)
                if 'duplicate' in msg.lower() or 'unique' in msg.lower():
                    errors['VIN'] = 'A motorbike with this VIN already exists.'
                    if shipped:
                        flash_error(
                            "The supplier's VIN already exists in inventory. "
                            "Revert the shipment so the supplier can correct it."
                        )
                else:
                    flash_error(f'Could not create the motorbike record: {msg}')

            if nb_id and not errors:
                try:
                    supabase.table('PO_NewMotorBike').update({
                        'New_MotorBike_NB_ID': nb_id,
                        'DateReceived':        date_received,
                        'Status':              'Received',
                    }).eq('POBike_ID', pobike_id).execute()
                    _auto_update_po_status(po_id)
                    flash_success(f'Motorcycle received and added to inventory as NB-{nb_id}.')
                    return redirect(url_for('purchase_order.view', po_id=po_id))
                except Exception as e:
                    # Roll back the bike we just created so inventory stays consistent
                    try:
                        supabase.table('New_MotorBike').delete().eq('NB_ID', nb_id).execute()
                    except Exception:
                        pass
                    flash_error(f'Could not complete receiving: {str(e)}')

    return render_template(
        'modules/purchase_order/motorbike_receive_form.html',
        form_data=form_data, errors=errors, line=line, po_id=po_id, pobike_id=pobike_id,
        fuel_type_options=NB_FUEL_TYPE_OPTIONS,
        transmission_options=NB_TRANSMISSION_OPTIONS,
        locked_specs=locked_specs,
        shipped=shipped,
        shipped_on=shipped_on
    )


@bp.route('/<int:po_id>/motorbikes/<int:pobike_id>/unship', methods=['POST'])
@login_required
def unship_motorbike(po_id, pobike_id):
    """
    Revert a supplier shipment (Task 35): the line goes back to Ordered and the
    supplier's VIN, year and shipped date are cleared so it can be shipped again.
    """
    line, redir = _get_motorbike_line_or_redirect(po_id, pobike_id)
    if redir:
        return redir
    if line.get('Status') != 'Shipped':
        flash_error('Only a motorcycle line with status Shipped can have its shipment reverted.')
        return redirect(url_for('purchase_order.view', po_id=po_id))

    try:
        reverted = (
            supabase.table('PO_NewMotorBike').update({
                'Status':      'Ordered',
                'ShippedVIN':  None,
                'ShippedYear': None,
                'DateShipped': None,
            })
            .eq('POBike_ID', pobike_id).eq('Status', 'Shipped')
            .execute()
        )
        if reverted.data:
            flash_success(
                'Shipment reverted. The motorcycle line is back to Ordered and the '
                'supplier can ship it again.'
            )
        else:
            flash_error('The shipment could not be reverted because the line is no longer Shipped.')
    except Exception as e:
        flash_error(f'Could not revert the shipment: {str(e)}')

    return redirect(url_for('purchase_order.view', po_id=po_id))