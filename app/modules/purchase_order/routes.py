from datetime import date as date_type
from flask import render_template, request, redirect, url_for
from app.modules.purchase_order import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields, is_positive_integer, is_positive_number

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

        supplier_id_raw  = form_data.get('Supplier_SupplierID', '').strip()
        porder_date_raw  = form_data.get('POrderDate', '').strip()
        expected_date_raw = form_data.get('ExpectedDate', '').strip()
        status_value     = form_data.get('Status', '').strip()

        # Supplier validation
        supplier_id = None
        if not supplier_id_raw:
            errors['Supplier_SupplierID'] = 'Supplier is required.'
        else:
            try:
                supplier_id = int(supplier_id_raw)
            except ValueError:
                errors['Supplier_SupplierID'] = 'Please select a valid supplier.'

        # Date validation
        porder_date,  porder_err  = _validate_date(porder_date_raw,  'Order Date')
        expected_date, exp_err    = _validate_date(expected_date_raw, 'Expected Date')

        if porder_err:
            errors['POrderDate'] = porder_err
        if exp_err:
            errors['ExpectedDate'] = exp_err

        # Cross-field: ExpectedDate must be on or after POrderDate
        if (not porder_err and not exp_err
                and porder_date and expected_date
                and expected_date < porder_date):
            errors['ExpectedDate'] = (
                'Expected date must be on or after the order date.'
            )

        # Status validation
        valid_statuses = [s for s, _ in PO_STATUS_OPTIONS]
        if not status_value:
            errors['Status'] = 'Status is required.'
        elif status_value not in valid_statuses:
            errors['Status'] = 'Please select a valid status.'

        if not errors:
            try:
                supabase.table('PurchaseOrder').insert({
                    'POrderDate':          porder_date,
                    'ExpectedDate':        expected_date,
                    'Status':              status_value,
                    'Supplier_SupplierID': supplier_id,
                }).execute()
                flash_success('Purchase order was created successfully.')
                return redirect(url_for('purchase_order.index'))
            except Exception as e:
                flash_error(f'Could not create purchase order: {str(e)}')

    return render_template(
        'modules/purchase_order/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        supplier_options=supplier_options,
        status_options=PO_STATUS_OPTIONS
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
 
        

    return render_template(
        'modules/purchase_order/view.html',
        record=record,
        supplier_name=supplier_name,
        po_items=po_items,
        po_id=po_id,
        po_status=record.get('Status')
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
    After a receive action, check all items for this PO and
    auto-update the PO Status field:
      All Received        → 'Received'
      Some Received       → 'Partially Received'
      None Received       → leave unchanged (remain Pending)
    """
    try:
        items_result = (
            supabase.table('PurchaseOrderItem')
            .select('Status')
            .eq('PurchaseOrder_ID', po_id)
            .execute()
        )
        items = items_result.data or []
        if not items:
            return

        total    = len(items)
        received = sum(1 for i in items if i.get('Status') == 'Received')

        if received == total:
            new_status = 'Received'
        elif received > 0:
            new_status = 'Partially Received'
        else:
            return  # Nothing received yet -> leave PO status as Pending

        supabase.table('PurchaseOrder').update(
            {'Status': new_status}
        ).eq('PurchaseOrderID', po_id).execute()

    except Exception:
        pass  # Non-fatal --> PO status can be corrected manually


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

    form_data = {}
    errors = {}
    sp_options = _get_spare_part_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        sp_id_raw  = form_data.get('SP_id', '').strip()
        qty_raw    = form_data.get('Quantity_Ordered', '').strip()
        price_raw  = form_data.get('BuyingPrice', '').strip()
        size_value = form_data.get('Size_Expected', '').strip()

        sp_id = None
        if not sp_id_raw:
            errors['SP_id'] = 'Spare part is required.'
        else:
            try:
                sp_id = int(sp_id_raw)
            except ValueError:
                errors['SP_id'] = 'Please select a valid spare part.'

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
                    'PurchaseOrder_ID': po_id,
                    'SP_id':            sp_id,
                    'Quantity_Ordered': qty,
                    'BuyingPrice':      price,
                    'Size_Expected':    size_value or None,
                    'Status':           'Ordered',
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
        sp_options=sp_options,
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
    errors = {}
    sp_options = _get_spare_part_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        sp_id_raw  = form_data.get('SP_id', '').strip()
        qty_raw    = form_data.get('Quantity_Ordered', '').strip()
        price_raw  = form_data.get('BuyingPrice', '').strip()
        size_value = form_data.get('Size_Expected', '').strip()

        sp_id = None
        if not sp_id_raw:
            errors['SP_id'] = 'Spare part is required.'
        else:
            try:
                sp_id = int(sp_id_raw)
            except ValueError:
                errors['SP_id'] = 'Please select a valid spare part.'

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
                    'SP_id':            sp_id,
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
        stock_res = (
            supabase.table('Stock')
            .select('Stock_ID, Size, Brand_Brand_ID, QOH')
            .eq('Spare_Parts_SP_id', sp_id)
            .execute()
        )
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
        date_recv, date_err = _validate_date(date_recv_raw, 'Date Received')
        if date_err:
            errors['DateReceived'] = date_err

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
                except ValueError:
                    errors['Stock_Stock_ID'] = 'Invalid stock selection.'

        elif recv_mode == 'new':
            brand_id_raw    = form_data.get('Brand_Brand_ID', '').strip()
            new_size        = form_data.get('New_Size', '').strip() or None
            new_price_raw   = form_data.get('S_Price', '').strip()
            new_warranty_raw = form_data.get('Warranty', '').strip()

            if not brand_id_raw:
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
        item_id=item_id
    )

