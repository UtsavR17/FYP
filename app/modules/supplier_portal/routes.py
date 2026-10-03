"""
Supplier Portal routes (Task 35, Phase 1).

Rules that hold for every route here:
  - The supplier id always comes from session['supplier_id'], never from the
    URL or a form field.
  - Every query runs through get_supplier_client() (a per-request client
    authenticated as the supplier). The shared admin client is never used.
  - Shipping actions re-check PO ownership, PO status and line status on the
    server before writing; RLS and the guard triggers check them again.
"""
from flask import redirect, render_template, request, session, url_for

from app.modules.supplier_portal import bp
from app.modules.supplier_portal import services as svc
from app.modules.supplier_portal.decorators import (
    clear_supplier_session,
    get_supplier_client,
    new_anon_client,
    supplier_login_required,
)
from app.utils.flash_messages import flash_error, flash_info, flash_success


def _supplier_id():
    return session.get('supplier_id')


def _plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


# =============================================================================
# AUTHENTICATION
# =============================================================================

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Supplier sign in. Uses a throwaway client (never the shared admin client),
    then confirms the Auth user is linked to a Supplier row before creating
    the supplier session.
    """
    if session.get('supplier_access_token'):
        return redirect(url_for('supplier_portal.dashboard'))

    error = None
    email = ''

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            error = 'Email and password are required.'
        else:
            client = new_anon_client()
            auth_response = None
            try:
                auth_response = client.auth.sign_in_with_password({
                    'email':    email,
                    'password': password,
                })
            except Exception:
                error = 'Invalid email or password. Please try again.'

            if auth_response is not None:
                supplier, lookup_failed = None, False
                try:
                    client.postgrest.auth(auth_response.session.access_token)
                    result = (
                        client.table('Supplier')
                        .select('SupplierID, SupplierName')
                        .eq('AuthUserID', auth_response.user.id)
                        .limit(1)
                        .execute()
                    )
                    supplier = (result.data or [None])[0]
                except Exception:
                    lookup_failed = True

                if supplier:
                    clear_supplier_session()
                    session['supplier_access_token']  = auth_response.session.access_token
                    session['supplier_refresh_token'] = auth_response.session.refresh_token
                    session['supplier_id']            = supplier['SupplierID']
                    session['supplier_name']          = supplier['SupplierName']
                    session['supplier_email']         = auth_response.user.email
                    return redirect(url_for('supplier_portal.dashboard'))

                try:
                    client.auth.sign_out({'scope': 'local'})
                except Exception:
                    pass
                if lookup_failed:
                    flash_error('Your supplier account could not be loaded. Please try again.')
                else:
                    flash_error('This login is not linked to a supplier account.')

    return render_template('supplier_portal/login.html', error=error, email=email)


@bp.route('/logout', methods=['POST'])
def logout():
    """Sign out on a supplier client and clear only the supplier session keys."""
    access_token = session.get('supplier_access_token')
    refresh_token = session.get('supplier_refresh_token')
    if access_token and refresh_token:
        try:
            client = new_anon_client()
            client.auth.set_session(access_token, refresh_token)
            client.auth.sign_out({'scope': 'local'})
        except Exception:
            pass
    clear_supplier_session()
    flash_info('You have been signed out of the Supplier Portal.')
    return redirect(url_for('supplier_portal.login'))


# =============================================================================
# DASHBOARD
# =============================================================================

@bp.route('/')
@supplier_login_required
def dashboard():
    client = get_supplier_client()
    supplier_id = _supplier_id()

    pos, items, bikes = [], [], []
    try:
        pos = svc.get_supplier_pos(client, supplier_id)
        po_ids = [p['PurchaseOrderID'] for p in pos]
        items = svc.get_po_items(client, po_ids)
        bikes = svc.get_po_bikes(client, po_ids)
    except Exception:
        flash_error('Could not load your purchase orders. Please refresh the page.')
    svc.summarise_pos(pos, items, bikes)

    product_count, model_count = 0, 0
    try:
        product_count = (
            client.table('Supplier_Product').select('SupplierProduct_ID', count='exact')
            .eq('Supplier_SupplierID', supplier_id).execute()
        ).count or 0
        model_count = (
            client.table('Supplier_Model').select('SupplierModel_ID', count='exact')
            .eq('Supplier_SupplierID', supplier_id).execute()
        ).count or 0
    except Exception:
        flash_error('Could not load your catalogue totals.')

    stats = {
        'open_pos':  sum(1 for p in pos if p.get('Status') in svc.OPEN_PO_STATUSES),
        'awaiting_response': sum(1 for p in pos if svc.po_stage(p) == svc.STAGE_SENT),
        'awaiting':  sum(p['_awaiting'] for p in pos),
        'products':  product_count,
        'models':    model_count,
    }

    return render_template(
        'supplier_portal/dashboard.html',
        stats=stats,
        recent_pos=sorted(pos, key=svc.order_list_key)[:5],
    )


# =============================================================================
# CATALOGUE: SPARE PARTS (Supplier_Product)
# =============================================================================

@bp.route('/products')
@supplier_login_required
def products():
    client = get_supplier_client()
    rows = []
    try:
        rows = svc.get_catalogue_products(client, _supplier_id())
    except Exception:
        flash_error('Could not load your products. Please refresh the page.')
    return render_template('supplier_portal/products.html', products=rows)


@bp.route('/products/add', methods=['GET', 'POST'])
@supplier_login_required
def add_product():
    client = get_supplier_client()
    supplier_id = _supplier_id()
    sp_options = svc.get_spare_part_options(client)
    brand_options = svc.get_brand_options(client)
    form_data, errors = {}, {}

    if request.method == 'POST':
        form_data = request.form.to_dict()

        sp_id, err = svc.parse_option_id(
            form_data.get('SP_id'), {v for v, _ in sp_options},
            'Spare part is required.', 'Please select a valid spare part.'
        )
        if err:
            errors['SP_id'] = err

        brand_id, err = svc.parse_option_id(
            form_data.get('Brand_Brand_ID'), {v for v, _ in brand_options},
            'Brand is required.', 'Please select a valid brand.'
        )
        if err:
            errors['Brand_Brand_ID'] = err

        price, err = svc.parse_price(form_data.get('BuyingPrice'))
        if err:
            errors['BuyingPrice'] = err

        if not errors:
            try:
                client.table('Supplier_Product').insert({
                    'Supplier_SupplierID': supplier_id,
                    'SP_id':               sp_id,
                    'Brand_Brand_ID':      brand_id,
                    'BuyingPrice':         price,
                }).execute()
                flash_success('Product was added to your catalogue.')
                return redirect(url_for('supplier_portal.products'))
            except Exception as e:
                if svc.is_duplicate_error(e):
                    errors['SP_id'] = (
                        'You already list this part for this brand. '
                        'Edit the existing entry instead of adding it again.'
                    )
                else:
                    flash_error('Could not add the product. Please try again.')

    return render_template(
        'supplier_portal/product_form.html',
        form_data=form_data, errors=errors, is_edit=False,
        sp_options=sp_options, brand_options=brand_options
    )


@bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@supplier_login_required
def edit_product(product_id):
    client = get_supplier_client()
    supplier_id = _supplier_id()

    try:
        row = svc.get_catalogue_row(
            client, 'Supplier_Product', 'SupplierProduct_ID', product_id, supplier_id
        )
    except Exception:
        row = None
    if not row:
        flash_error('Product listing not found.')
        return redirect(url_for('supplier_portal.products'))

    enriched = svc.enrich_supplier_products(client, [dict(row)])[0]
    product_label = f"{enriched['_sp_name']} - {enriched['_brand_name']}"
    form_data = {'BuyingPrice': str(row.get('BuyingPrice', '') or '')}
    errors = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        price, err = svc.parse_price(form_data.get('BuyingPrice'))
        if err:
            errors['BuyingPrice'] = err

        if not errors:
            try:
                updated = (
                    client.table('Supplier_Product').update({'BuyingPrice': price})
                    .eq('SupplierProduct_ID', product_id)
                    .eq('Supplier_SupplierID', supplier_id)
                    .execute()
                )
                if updated.data:
                    flash_success('Buying price updated.')
                else:
                    flash_error('Product listing not found.')
                return redirect(url_for('supplier_portal.products'))
            except Exception:
                flash_error('Could not update the product. Please try again.')

    return render_template(
        'supplier_portal/product_form.html',
        form_data=form_data, errors=errors, is_edit=True,
        product_id=product_id, product_label=product_label
    )


@bp.route('/products/<int:product_id>/delete', methods=['POST'])
@supplier_login_required
def delete_product(product_id):
    client = get_supplier_client()
    try:
        deleted = (
            client.table('Supplier_Product').delete()
            .eq('SupplierProduct_ID', product_id)
            .eq('Supplier_SupplierID', _supplier_id())
            .execute()
        )
        if deleted.data:
            flash_success('Product removed from your catalogue.')
        else:
            flash_error('Product listing not found.')
    except Exception as e:
        if svc.is_foreign_key_error(e):
            flash_error(
                'This product appears on one or more purchase orders, so it cannot be '
                'removed. You can still change its price.'
            )
        else:
            flash_error('Could not remove the product. Please try again.')
    return redirect(url_for('supplier_portal.products'))


# =============================================================================
# CATALOGUE: MOTORBIKE MODELS (Supplier_Model)
# =============================================================================

@bp.route('/models')
@supplier_login_required
def models():
    client = get_supplier_client()
    rows = []
    try:
        rows = svc.get_catalogue_models(client, _supplier_id())
    except Exception:
        flash_error('Could not load your models. Please refresh the page.')
    return render_template('supplier_portal/models.html', models=rows)


@bp.route('/models/add', methods=['GET', 'POST'])
@supplier_login_required
def add_model():
    client = get_supplier_client()
    supplier_id = _supplier_id()

    existing_ids = set()
    try:
        existing = (
            client.table('Supplier_Model').select('Model_Model_No')
            .eq('Supplier_SupplierID', supplier_id).execute()
        )
        existing_ids = {r['Model_Model_No'] for r in (existing.data or [])}
    except Exception:
        pass

    model_options = svc.get_model_options(client, exclude_model_nos=existing_ids)
    form_data, errors = {}, {}

    if request.method == 'POST':
        form_data = request.form.to_dict()

        model_no, err = svc.parse_option_id(
            form_data.get('Model_Model_No'), {v for v, _ in model_options},
            'Motorbike model is required.', 'Please select a valid model.'
        )
        if err:
            errors['Model_Model_No'] = err

        price, err = svc.parse_price(form_data.get('BuyingPrice'))
        if err:
            errors['BuyingPrice'] = err

        spec_errors, specs = svc.validate_model_specs(form_data)
        errors.update(spec_errors)

        if not errors:
            try:
                client.table('Supplier_Model').insert({
                    'Supplier_SupplierID': supplier_id,
                    'Model_Model_No':      model_no,
                    'BuyingPrice':         price,
                    **specs,
                }).execute()
                flash_success('Model was added to your catalogue.')
                return redirect(url_for('supplier_portal.models'))
            except Exception as e:
                if svc.is_duplicate_error(e):
                    errors['Model_Model_No'] = 'You already list this model.'
                else:
                    flash_error('Could not add the model. Please try again.')

    return render_template(
        'supplier_portal/model_form.html',
        form_data=form_data, errors=errors, is_edit=False,
        model_options=model_options,
        fuel_type_options=svc.FUEL_TYPE_OPTIONS,
        transmission_options=svc.TRANSMISSION_OPTIONS
    )


@bp.route('/models/<int:model_id>/edit', methods=['GET', 'POST'])
@supplier_login_required
def edit_model(model_id):
    client = get_supplier_client()
    supplier_id = _supplier_id()

    try:
        row = svc.get_catalogue_row(
            client, 'Supplier_Model', 'SupplierModel_ID', model_id, supplier_id
        )
    except Exception:
        row = None
    if not row:
        flash_error('Model listing not found.')
        return redirect(url_for('supplier_portal.models'))

    model_label = svc.enrich_supplier_models(client, [dict(row)])[0]['_model_label']
    form_data = {
        'BuyingPrice':      str(row.get('BuyingPrice', '') or ''),
        'EngineCC':         str(row.get('EngineCC') or ''),
        'FuelType':         row.get('FuelType') or '',
        'Transmission':     row.get('Transmission') or '',
        'FuelTankCapacity': str(row.get('FuelTankCapacity') or ''),
    }
    errors = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()

        price, err = svc.parse_price(form_data.get('BuyingPrice'))
        if err:
            errors['BuyingPrice'] = err

        spec_errors, specs = svc.validate_model_specs(form_data)
        errors.update(spec_errors)

        if not errors:
            try:
                updated = (
                    client.table('Supplier_Model').update({'BuyingPrice': price, **specs})
                    .eq('SupplierModel_ID', model_id)
                    .eq('Supplier_SupplierID', supplier_id)
                    .execute()
                )
                if updated.data:
                    flash_success('Model listing updated.')
                else:
                    flash_error('Model listing not found.')
                return redirect(url_for('supplier_portal.models'))
            except Exception:
                flash_error('Could not update the model. Please try again.')

    return render_template(
        'supplier_portal/model_form.html',
        form_data=form_data, errors=errors, is_edit=True,
        model_id=model_id, model_label=model_label,
        fuel_type_options=svc.FUEL_TYPE_OPTIONS,
        transmission_options=svc.TRANSMISSION_OPTIONS
    )


@bp.route('/models/<int:model_id>/delete', methods=['POST'])
@supplier_login_required
def delete_model(model_id):
    client = get_supplier_client()
    try:
        deleted = (
            client.table('Supplier_Model').delete()
            .eq('SupplierModel_ID', model_id)
            .eq('Supplier_SupplierID', _supplier_id())
            .execute()
        )
        if deleted.data:
            flash_success('Model removed from your catalogue.')
        else:
            flash_error('Model listing not found.')
    except Exception as e:
        if svc.is_foreign_key_error(e):
            flash_error(
                'This model appears on one or more purchase orders, so it cannot be '
                'removed. You can still change its price and specifications.'
            )
        else:
            flash_error('Could not remove the model. Please try again.')
    return redirect(url_for('supplier_portal.models'))


# =============================================================================
# PURCHASE ORDERS
# =============================================================================

def _get_owned_po_or_redirect(client, po_id):
    """
    Returns (po, None) or (None, redirect). A PO that does not exist and a PO
    of another supplier give the same message, so ids cannot be probed.
    """
    try:
        po = svc.get_owned_po(client, po_id, _supplier_id())
    except Exception:
        flash_error('Could not load the purchase order. Please try again.')
        return None, redirect(url_for('supplier_portal.orders'))
    if not po:
        flash_error('Purchase order not found.')
        return None, redirect(url_for('supplier_portal.orders'))
    return po, None


@bp.route('/orders')
@supplier_login_required
def orders():
    client = get_supplier_client()
    pos, items, bikes = [], [], []
    try:
        pos = svc.get_supplier_pos(client, _supplier_id())
        po_ids = [p['PurchaseOrderID'] for p in pos]
        items = svc.get_po_items(client, po_ids)
        bikes = svc.get_po_bikes(client, po_ids)
    except Exception:
        flash_error('Could not load your purchase orders. Please refresh the page.')
    svc.summarise_pos(pos, items, bikes)
    return render_template('supplier_portal/orders.html', pos=sorted(pos, key=svc.order_list_key))


@bp.route('/orders/<int:po_id>')
@supplier_login_required
def order_detail(po_id):
    client = get_supplier_client()
    po, redir = _get_owned_po_or_redirect(client, po_id)
    if redir:
        return redir

    items, bikes = [], []
    try:
        items = svc.enrich_po_items(client, svc.get_po_items(client, [po_id]))
        bikes = svc.enrich_po_bikes(client, svc.get_po_bikes(client, [po_id]))
    except Exception:
        flash_error('Could not load the order lines. Please refresh the page.')

    can_ship = svc.can_ship_po(po)
    items_total = sum(
        float(i.get('BuyingPrice') or 0) * int(i.get('Quantity_Ordered') or 0) for i in items
    )
    bikes_total = sum(float(b.get('BuyingPrice') or 0) for b in bikes)

    return render_template(
        'supplier_portal/order_detail.html',
        po=po,
        po_id=po_id,
        items=items,
        bikes=bikes,
        can_ship=can_ship,
        items_to_ship=sum(1 for i in items if svc.item_awaits_shipment(i)),
        bikes_to_ship=sum(1 for b in bikes if svc.bike_awaits_shipment(b)),
        items_total=items_total,
        bikes_total=bikes_total,
        order_total=items_total + bikes_total,
        order_date=svc.format_date(po.get('POrderDate')),
        expected_date=svc.format_date(po.get('ExpectedDate')),
        stage=svc.po_stage(po),
        date_sent=svc.format_date(po.get('DateSent')),
        date_responded=svc.format_date(po.get('DateResponded')),
        reason_min=svc.REJECTION_REASON_MIN,
        reason_max=svc.REJECTION_REASON_MAX,
    )


def _respond_to_order(po_id, values, success_message):
    """
    Accept or reject: only SupplierStage (and RejectionReason when rejecting)
    is ever sent. The database trigger sets Status and DateResponded. The
    update is conditional on the stage still being Sent.
    """
    client = get_supplier_client()
    detail_url = url_for('supplier_portal.order_detail', po_id=po_id)
    po, redir = _get_owned_po_or_redirect(client, po_id)
    if redir:
        return redir
    if svc.po_stage(po) != svc.STAGE_SENT:
        flash_error('This order is no longer awaiting your response.')
        return redirect(detail_url)

    try:
        result = (
            client.table('PurchaseOrder')
            .update(values)
            .eq('PurchaseOrderID', po_id)
            .eq('Supplier_SupplierID', _supplier_id())
            .eq('SupplierStage', svc.STAGE_SENT)
            .execute()
        )
    except Exception as e:
        flash_error(svc.friendly_response_error(e))
        return redirect(detail_url)

    if result.data:
        flash_success(success_message)
    else:
        flash_error('This order has changed. Refresh and try again.')
    return redirect(detail_url)


@bp.route('/orders/<int:po_id>/accept', methods=['POST'])
@supplier_login_required
def accept_order(po_id):
    return _respond_to_order(
        po_id, {'SupplierStage': svc.STAGE_ACCEPTED},
        'Order accepted. You can now ship its items.'
    )


@bp.route('/orders/<int:po_id>/reject', methods=['POST'])
@supplier_login_required
def reject_order(po_id):
    reason = request.form.get('RejectionReason', '').strip()
    if not reason:
        error = 'Please give a reason for rejecting the order.'
    elif len(reason) < svc.REJECTION_REASON_MIN:
        error = f'The reason must be at least {svc.REJECTION_REASON_MIN} characters.'
    elif len(reason) > svc.REJECTION_REASON_MAX:
        error = f'The reason must not exceed {svc.REJECTION_REASON_MAX} characters.'
    else:
        error = None
    if error:
        flash_error(f'The order was not rejected. {error}')
        return redirect(url_for('supplier_portal.order_detail', po_id=po_id))

    return _respond_to_order(
        po_id, {'SupplierStage': svc.STAGE_REJECTED, 'RejectionReason': reason},
        'Order rejected.'
    )


@bp.route('/orders/<int:po_id>/ship-items', methods=['POST'])
@supplier_login_required
def ship_items(po_id):
    """Mark every unshipped spare-part item of this PO as shipped today."""
    client = get_supplier_client()
    po, redir = _get_owned_po_or_redirect(client, po_id)
    if redir:
        return redir

    if svc.po_stage(po) != svc.STAGE_ACCEPTED:
        flash_error('Accept this order before shipping it.')
        return redirect(url_for('supplier_portal.order_detail', po_id=po_id))
    if po.get('Status') not in svc.OPEN_PO_STATUSES:
        flash_error(f'This purchase order is {po.get("Status")}, so it can no longer be shipped.')
        return redirect(url_for('supplier_portal.order_detail', po_id=po_id))

    try:
        result = (
            client.table('PurchaseOrderItem')
            .update({'DateShipped': svc.mauritius_today().isoformat()})
            .eq('PurchaseOrder_ID', po_id)
            .eq('Status', 'Ordered')
            .is_('DateShipped', None)
            .execute()
        )
        count = len(result.data or [])
    except Exception as e:
        flash_error(f'No items were shipped. {svc.friendly_shipping_error(e)}')
        return redirect(url_for('supplier_portal.order_detail', po_id=po_id))

    if count:
        flash_success(f'{_plural(count, "spare-part item")} marked as shipped.')
    else:
        flash_info('There are no spare-part items waiting to be shipped on this order.')
    return redirect(url_for('supplier_portal.order_detail', po_id=po_id))


@bp.route('/orders/<int:po_id>/ship-motorbikes', methods=['GET', 'POST'])
@supplier_login_required
def ship_motorbikes(po_id):
    """
    Batch shipping: one VIN and Year per Ordered motorcycle line.
    Validation is all or nothing: if any row has an error nothing is saved.
    """
    client = get_supplier_client()
    po, redir = _get_owned_po_or_redirect(client, po_id)
    if redir:
        return redir

    detail_url = url_for('supplier_portal.order_detail', po_id=po_id)
    if svc.po_stage(po) != svc.STAGE_ACCEPTED:
        flash_error('Accept this order before shipping it.')
        return redirect(url_for('supplier_portal.order_detail', po_id=po_id))
    if po.get('Status') not in svc.OPEN_PO_STATUSES:
        flash_error(f'This purchase order is {po.get("Status")}, so it can no longer be shipped.')
        return redirect(detail_url)

    # The set of lines that may be shipped comes from the database, never the form
    try:
        lines = [b for b in svc.get_po_bikes(client, [po_id]) if svc.bike_awaits_shipment(b)]
        lines = svc.enrich_po_bikes(client, lines)
    except Exception:
        flash_error('Could not load the motorcycle lines. Please try again.')
        return redirect(detail_url)

    if not lines:
        flash_info('There are no motorcycles waiting to be shipped on this order.')
        return redirect(detail_url)

    today = svc.mauritius_today()
    values = {line['POBike_ID']: {'vin': '', 'year': ''} for line in lines}
    row_errors = {}

    def add_error(line_id, message):
        row_errors.setdefault(line_id, [])
        if message not in row_errors[line_id]:
            row_errors[line_id].append(message)

    if request.method == 'POST':
        parsed_vins = {}    # line id -> VIN that passed format validation
        to_ship = {}        # line id -> (vin, year) for rows with no error

        for line in lines:
            line_id = line['POBike_ID']
            vin_raw = request.form.get(f'vin_{line_id}', '').strip()
            year_raw = request.form.get(f'year_{line_id}', '').strip()
            values[line_id] = {'vin': vin_raw, 'year': year_raw}

            if not vin_raw and not year_raw:
                continue    # shipped later

            vin = year = None
            if vin_raw:
                vin, err = svc.validate_shipped_vin(vin_raw)
                if err:
                    add_error(line_id, err)
                else:
                    values[line_id]['vin'] = vin
                    parsed_vins[line_id] = vin
            else:
                add_error(line_id, 'Enter the VIN too, or clear the year to ship this unit later.')

            if year_raw:
                year, err = svc.validate_shipped_year(year_raw, today)
                if err:
                    add_error(line_id, err)
            else:
                add_error(line_id, 'Enter the year too, or clear the VIN to ship this unit later.')

            if line_id not in row_errors:
                to_ship[line_id] = (vin, year)

        # The same VIN may not be used twice in one submission
        lines_by_vin = {}
        for line_id, vin in parsed_vins.items():
            lines_by_vin.setdefault(vin, []).append(line_id)
        for vin, line_ids in lines_by_vin.items():
            if len(line_ids) > 1:
                for line_id in line_ids:
                    add_error(line_id, 'This VIN is entered more than once in this form.')

        # The VIN may not already be in inventory or shipped on another line
        check_failed = False
        for vin, line_ids in lines_by_vin.items():
            if len(line_ids) > 1:
                continue
            try:
                if svc.vin_in_use(client, vin):
                    add_error(line_ids[0], 'This VIN already exists.')
            except Exception:
                check_failed = True
                break

        if check_failed:
            flash_error('The VINs could not be checked right now. Nothing was saved. Please try again.')
        elif row_errors:
            flash_error(
                f'Nothing was saved. Correct the {_plural(len(row_errors), "highlighted row")} '
                f'and submit again.'
            )
        elif not to_ship:
            flash_error('Fill in the VIN and year for at least one motorcycle.')
        else:
            shipped_count = 0
            labels = {line['POBike_ID']: line['_model_label'] for line in lines}
            for line_id, (vin, year) in to_ship.items():
                try:
                    result = (
                        client.table('PO_NewMotorBike').update({
                            'Status':      'Shipped',
                            'ShippedVIN':  vin,
                            'ShippedYear': year,
                            'DateShipped': today.isoformat(),
                        })
                        .eq('POBike_ID', line_id)
                        .eq('PurchaseOrder_ID', po_id)
                        .eq('Status', 'Ordered')
                        .execute()
                    )
                    if result.data:
                        shipped_count += 1
                    else:
                        flash_error(f'{labels[line_id]} ({vin}): this line is no longer waiting to be shipped.')
                except Exception as e:
                    flash_error(f'{labels[line_id]} ({vin}): {svc.friendly_shipping_error(e)}')

            if shipped_count:
                flash_success(f'{_plural(shipped_count, "motorcycle")} marked as shipped.')
            return redirect(detail_url)

    return render_template(
        'supplier_portal/ship_motorbikes.html',
        po=po,
        po_id=po_id,
        lines=lines,
        values=values,
        row_errors=row_errors,
        min_year=svc.MIN_SHIPPED_YEAR,
        max_year=today.year + 1,
    )
