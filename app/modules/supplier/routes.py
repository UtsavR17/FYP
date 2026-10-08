import re
import secrets
from markupsafe import Markup
from app.utils.validators import is_positive_number
from flask import render_template, request, redirect, url_for
from app.modules.supplier import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error, flash_warning, flash_info
from app.utils.validators import required_fields, is_valid_email

# BRN (Task 46): optional, 5 to 30 letters, digits, hyphens or slashes, stored uppercase.
BRN_PATTERN = re.compile(r'^[A-Z0-9/-]{5,30}$')
BRN_DUPLICATE_MSG = 'This BRN is already registered to another supplier or application.'


def normalise_brn(raw):
    """(value or None, error or None). Empty means no BRN (stored as NULL)."""
    value = (raw or '').strip().upper()
    if not value:
        return None, None
    if not BRN_PATTERN.match(value):
        return None, 'BRN must be 5 to 30 letters, digits, hyphens or slashes.'
    return value, None


def _is_brn_conflict(error_msg):
    """True when a unique violation comes from the BRN index (its name or key mentions BRN)."""
    text = error_msg.lower()
    return ('duplicate' in text or 'unique' in text) and 'brn' in text


from app.modules.new_motorbike.routes import (
    FUEL_TYPE_OPTIONS as NB_FUEL_TYPE_OPTIONS,
    TRANSMISSION_OPTIONS as NB_TRANSMISSION_OPTIONS,
)

@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Supplier')
            .select('*')
            .order('SupplierName')
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load suppliers: {str(e)}')
        all_records = []

    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('SupplierName', '').lower()
            or q in r.get('Email', '').lower()
            or q in r.get('Country', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/supplier/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()

        name_value    = form_data.get('SupplierName', '').strip()
        phone_value   = form_data.get('Phone', '').strip()
        email_value   = form_data.get('Email', '').strip()
        address_value = form_data.get('Address', '').strip()
        country_value = form_data.get('Country', '').strip()

        # Required field checks
        missing = required_fields(
            form_data,
            ['SupplierName', 'Phone', 'Email', 'Address', 'Country']
        )

        if 'SupplierName' in missing:
            errors['SupplierName'] = 'Supplier name is required.'
        elif len(name_value) > 100:
            errors['SupplierName'] = 'Supplier name must not exceed 100 characters.'

        if 'Phone' in missing:
            errors['Phone'] = 'Phone number is required.'
        elif len(phone_value) > 20:
            errors['Phone'] = 'Phone number must not exceed 20 characters.'

        if 'Email' in missing:
            errors['Email'] = 'Email address is required.'
        elif len(email_value) > 100:
            errors['Email'] = 'Email address must not exceed 100 characters.'
        elif not is_valid_email(email_value):
            errors['Email'] = 'Please enter a valid email address.'

        if 'Address' in missing:
            errors['Address'] = 'Address is required.'
        elif len(address_value) > 255:
            errors['Address'] = 'Address must not exceed 255 characters.'

        if 'Country' in missing:
            errors['Country'] = 'Country is required.'
        elif len(country_value) > 100:
            errors['Country'] = 'Country must not exceed 100 characters.'

        brn_value, brn_error = normalise_brn(form_data.get('BRN'))
        if brn_error:
            errors['BRN'] = brn_error

        if not errors:
            try:
                supabase.table('Supplier').insert({
                    'SupplierName': name_value,
                    'Phone':        phone_value,
                    'Email':        email_value,
                    'Address':      address_value,
                    'Country':      country_value,
                    'BRN':          brn_value,
                }).execute()
                flash_success(f'Supplier "{name_value}" was added successfully.')
                return redirect(url_for('supplier.index'))
            # except Exception as e:
            #     flash_error(f'Could not add supplier: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if _is_brn_conflict(error_msg):
                    errors['BRN'] = BRN_DUPLICATE_MSG
                elif 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A supplier with this name already exists.')
                else:
                    flash_error(f'Could not add supplier: {error_msg}')

    return render_template(
        'modules/supplier/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False
    )


@bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit(supplier_id):
    try:
        result = (
            supabase.table('Supplier')
            .select('*')
            .eq('SupplierID', supplier_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Supplier ID {supplier_id} was not found.')
        return redirect(url_for('supplier.index'))

    errors = {}
    form_data = record.copy()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        name_value    = form_data.get('SupplierName', '').strip()
        phone_value   = form_data.get('Phone', '').strip()
        email_value   = form_data.get('Email', '').strip()
        address_value = form_data.get('Address', '').strip()
        country_value = form_data.get('Country', '').strip()

        missing = required_fields(
            form_data,
            ['SupplierName', 'Phone', 'Email', 'Address', 'Country']
        )

        if 'SupplierName' in missing:
            errors['SupplierName'] = 'Supplier name is required.'
        elif len(name_value) > 100:
            errors['SupplierName'] = 'Supplier name must not exceed 100 characters.'

        if 'Phone' in missing:
            errors['Phone'] = 'Phone number is required.'
        elif len(phone_value) > 20:
            errors['Phone'] = 'Phone number must not exceed 20 characters.'

        if 'Email' in missing:
            errors['Email'] = 'Email address is required.'
        elif len(email_value) > 100:
            errors['Email'] = 'Email address must not exceed 100 characters.'
        elif not is_valid_email(email_value):
            errors['Email'] = 'Please enter a valid email address.'

        if 'Address' in missing:
            errors['Address'] = 'Address is required.'
        elif len(address_value) > 255:
            errors['Address'] = 'Address must not exceed 255 characters.'

        if 'Country' in missing:
            errors['Country'] = 'Country is required.'
        elif len(country_value) > 100:
            errors['Country'] = 'Country must not exceed 100 characters.'

        brn_value, brn_error = normalise_brn(form_data.get('BRN'))
        if brn_error:
            errors['BRN'] = brn_error

        if not errors:
            try:
                supabase.table('Supplier').update({
                    'SupplierName': name_value,
                    'Phone':        phone_value,
                    'Email':        email_value,
                    'Address':      address_value,
                    'Country':      country_value,
                    'BRN':          brn_value,
                }).eq('SupplierID', supplier_id).execute()
                flash_success(f'Supplier "{name_value}" was updated successfully.')
                return redirect(url_for('supplier.index'))
            except Exception as e:
                error_msg = str(e)
                if _is_brn_conflict(error_msg):
                    errors['BRN'] = BRN_DUPLICATE_MSG
                elif 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A supplier with this name already exists.')
                else:
                    flash_error(f'Could not update supplier: {error_msg}')

    return render_template(
        'modules/supplier/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record
    )


@bp.route('/delete/<int:supplier_id>', methods=['POST'])
@login_required
def delete(supplier_id):
    auth_user_id = None
    try:
        result = (
            supabase.table('Supplier')
            .select('SupplierName, AuthUserID')
            .eq('SupplierID', supplier_id)
            .single()
            .execute()
        )
        name_value = result.data.get('SupplierName', f'ID {supplier_id}')
        auth_user_id = result.data.get('AuthUserID')
    except Exception:
        name_value = f'ID {supplier_id}'

    # Decided before the row is deleted: a shared login is the person's shop account
    # and must survive (Task 47).
    login_shared = _login_is_shared(auth_user_id) if auth_user_id else False

    try:
        deleted = supabase.table('Supplier').delete().eq('SupplierID', supplier_id).execute()
        flash_success(f'Supplier "{name_value}" was deleted successfully.')
        if auth_user_id and deleted.data:
            if login_shared:
                flash_info(SHARED_LOGIN_KEPT_MSG)
            else:
                # Portal-only login: the supplier row is gone, so it has nothing left to open
                _delete_portal_user(auth_user_id, name_value)
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{name_value}" because it is referenced by one or '
                f'more purchase orders or catalogue entries (products or models). '
                f'Remove those first.'
            )
        else:
            flash_error(f'Could not delete supplier: {error_msg}')

    return redirect(url_for('supplier.index'))





# =============================================================================
# SUPPLIER CATALOG — Supplier_Product and Supplier_Model
# What a Supplier actually sells, with the Supplier's own buying price.
# Managed entirely from the Supplier detail (view) page, the same way
# PurchaseOrderItem/PO_NewMotorBike live inside the Purchase Order view.
# =============================================================================

def _get_supplier_or_redirect(supplier_id):
    """Fetch a single Supplier record. Returns (record, None) or (None, redirect)."""
    try:
        result = (
            supabase.table('Supplier')
            .select('*')
            .eq('SupplierID', supplier_id)
            .single()
            .execute()
        )
        return result.data, None
    except Exception:
        flash_error(f'Supplier ID {supplier_id} was not found.')
        return None, redirect(url_for('supplier.index'))


def _get_spare_part_options():
    """(SP_id, SP_name) tuples ordered by SP_name."""
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
    """(Brand_ID, Brand_Name) tuples ordered by Brand_Name."""
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


def _get_model_options(exclude_model_nos=None):
    """
    (Model_No, 'Brand_Name — Description') tuples ordered by Description.
    exclude_model_nos filters out models already added for this supplier.
    """
    exclude_model_nos = exclude_model_nos or set()
    brand_lookup = {}
    try:
        br = supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
        brand_lookup = {r['Brand_ID']: r['Brand_Name'] for r in (br.data or [])}
    except Exception:
        pass

    options = []
    try:
        result = (
            supabase.table('Model')
            .select('Model_No, Brand_Brand_ID, Description')
            .order('Description')
            .execute()
        )
        for m in (result.data or []):
            if m['Model_No'] in exclude_model_nos:
                continue
            brand_name = brand_lookup.get(m.get('Brand_Brand_ID'), 'Unknown Brand')
            label = f"{brand_name} \u2014 {m['Description']}"
            options.append((m['Model_No'], label))
    except Exception:
        pass

    return options


def _enrich_supplier_products(rows):
    """Attach _sp_name and _brand_name to each Supplier_Product row."""
    sp_lookup, brand_lookup = {}, {}
    try:
        sp = supabase.table('Spare_Parts').select('SP_id, SP_name').execute()
        sp_lookup = {r['SP_id']: r['SP_name'] for r in (sp.data or [])}
        br = supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
        brand_lookup = {r['Brand_ID']: r['Brand_Name'] for r in (br.data or [])}
    except Exception:
        pass

    for r in rows:
        r['_sp_name'] = sp_lookup.get(r.get('SP_id'), f"SP-{r.get('SP_id')}")
        r['_brand_name'] = brand_lookup.get(r.get('Brand_Brand_ID'), 'Unknown Brand')
    return rows


def _enrich_supplier_models(rows):
    """Attach _model_label to each Supplier_Model row."""
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
        r['_model_label'] = model_lookup.get(
            r.get('Model_Model_No'), f"Model #{r.get('Model_Model_No')}"
        )
    return rows


@bp.route('/view/<int:supplier_id>')
@login_required
def view(supplier_id):
    record, redir = _get_supplier_or_redirect(supplier_id)
    if redir:
        return redir

    products = []
    try:
        result = (
            supabase.table('Supplier_Product')
            .select('*')
            .eq('Supplier_SupplierID', supplier_id)
            .order('SupplierProduct_ID')
            .execute()
        )
        products = _enrich_supplier_products(result.data or [])
    except Exception:
        pass

    models = []
    try:
        result = (
            supabase.table('Supplier_Model')
            .select('*')
            .eq('Supplier_SupplierID', supplier_id)
            .order('SupplierModel_ID')
            .execute()
        )
        models = _enrich_supplier_models(result.data or [])
    except Exception:
        pass

    return render_template(
        'modules/supplier/view.html',
        record=record,
        supplier_id=supplier_id,
        products=products,
        models=models,
        login_shared=_login_is_shared(record.get('AuthUserID')),
        shared_login_msg=SHARED_LOGIN_MSG,
    )


# --- Supplier_Product routes -------------------------------------------------

@bp.route('/<int:supplier_id>/products/add', methods=['GET', 'POST'])
@login_required
def add_product(supplier_id):
    record, redir = _get_supplier_or_redirect(supplier_id)
    if redir:
        return redir

    sp_options = _get_spare_part_options()
    brand_options = _get_brand_options()
    form_data, errors = {}, {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        sp_id_raw = form_data.get('SP_id', '').strip()
        brand_id_raw = form_data.get('Brand_Brand_ID', '').strip()
        price_raw = form_data.get('BuyingPrice', '').strip()

        sp_id = None
        if not sp_id_raw:
            errors['SP_id'] = 'Spare part is required.'
        else:
            try:
                sp_id = int(sp_id_raw)
            except ValueError:
                errors['SP_id'] = 'Please select a valid spare part.'

        brand_id = None
        if not brand_id_raw:
            errors['Brand_Brand_ID'] = 'Brand is required.'
        else:
            try:
                brand_id = int(brand_id_raw)
            except ValueError:
                errors['Brand_Brand_ID'] = 'Please select a valid brand.'

        price = None
        if not price_raw:
            errors['BuyingPrice'] = 'Buying price is required.'
        elif not is_positive_number(price_raw):
            errors['BuyingPrice'] = 'Buying price must be a valid number of 0 or more.'
        else:
            price = float(price_raw)

        if not errors:
            try:
                supabase.table('Supplier_Product').insert({
                    'Supplier_SupplierID': supplier_id,
                    'SP_id':               sp_id,
                    'Brand_Brand_ID':      brand_id,
                    'BuyingPrice':         price,
                }).execute()
                flash_success('Product was added to this supplier\'s catalogue.')
                return redirect(url_for('supplier.view', supplier_id=supplier_id))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['SP_id'] = (
                        'This supplier already has a buying price listed for '
                        'this exact part and brand combination. Edit the '
                        'existing entry instead of adding it again.'
                    )
                else:
                    flash_error(f'Could not add product: {error_msg}')

    return render_template(
        'modules/supplier/product_form.html',
        form_data=form_data, errors=errors, is_edit=False,
        supplier_id=supplier_id, supplier_name=record.get('SupplierName', ''),
        sp_options=sp_options, brand_options=brand_options
    )


@bp.route('/<int:supplier_id>/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(supplier_id, product_id):
    record, redir = _get_supplier_or_redirect(supplier_id)
    if redir:
        return redir

    try:
        row = (
            supabase.table('Supplier_Product').select('*')
            .eq('SupplierProduct_ID', product_id)
            .eq('Supplier_SupplierID', supplier_id)
            .single().execute()
        ).data
    except Exception:
        flash_error('Product listing not found.')
        return redirect(url_for('supplier.view', supplier_id=supplier_id))

    enriched = _enrich_supplier_products([dict(row)])[0]
    product_label = f"{enriched['_sp_name']} \u2014 {enriched['_brand_name']}"

    form_data = {'BuyingPrice': str(row.get('BuyingPrice', '') or '')}
    errors = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        price_raw = form_data.get('BuyingPrice', '').strip()

        price = None
        if not price_raw:
            errors['BuyingPrice'] = 'Buying price is required.'
        elif not is_positive_number(price_raw):
            errors['BuyingPrice'] = 'Buying price must be a valid number of 0 or more.'
        else:
            price = float(price_raw)

        if not errors:
            try:
                supabase.table('Supplier_Product').update(
                    {'BuyingPrice': price}
                ).eq('SupplierProduct_ID', product_id).execute()
                flash_success('Buying price updated.')
                return redirect(url_for('supplier.view', supplier_id=supplier_id))
            except Exception as e:
                flash_error(f'Could not update product: {str(e)}')

    return render_template(
        'modules/supplier/product_form.html',
        form_data=form_data, errors=errors, is_edit=True,
        supplier_id=supplier_id, supplier_name=record.get('SupplierName', ''),
        product_label=product_label
    )


@bp.route('/<int:supplier_id>/products/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(supplier_id, product_id):
    try:
        supabase.table('Supplier_Product').delete().eq('SupplierProduct_ID', product_id).execute()
        flash_success('Product removed from this supplier\'s catalogue.')
    except Exception as e:
        flash_error(f'Could not remove product: {str(e)}')
    return redirect(url_for('supplier.view', supplier_id=supplier_id))


# --- Supplier_Model routes ----------------------------------------------------
def _option_values(options):
    """Allowed values from a list of (value, label) tuples or plain strings."""
    return {o[0] if isinstance(o, (tuple, list)) else o for o in options}


def _validate_model_specs(form_data):
    """Validate the four model-level specs. Returns (errors, parsed_specs)."""
    errors, specs = {}, {}

    cc_raw = form_data.get('EngineCC', '').strip()
    if not cc_raw:
        errors['EngineCC'] = 'Engine CC is required.'
    elif not cc_raw.isdigit() or int(cc_raw) < 1:
        errors['EngineCC'] = 'Engine CC must be a whole number of at least 1.'
    else:
        specs['EngineCC'] = int(cc_raw)

    fuel = form_data.get('FuelType', '').strip()
    if not fuel:
        errors['FuelType'] = 'Fuel type is required.'
    elif fuel not in _option_values(NB_FUEL_TYPE_OPTIONS):
        errors['FuelType'] = 'Please select a valid fuel type.'
    else:
        specs['FuelType'] = fuel

    trans = form_data.get('Transmission', '').strip()
    if not trans:
        errors['Transmission'] = 'Transmission is required.'
    elif trans not in _option_values(NB_TRANSMISSION_OPTIONS):
        errors['Transmission'] = 'Please select a valid transmission.'
    else:
        specs['Transmission'] = trans

    tank_raw = form_data.get('FuelTankCapacity', '').strip()
    if not tank_raw:
        errors['FuelTankCapacity'] = 'Fuel tank capacity is required.'
    else:
        try:
            tank = float(tank_raw)
            if tank <= 0 or tank > 999.99:
                errors['FuelTankCapacity'] = 'Tank capacity must be greater than 0 and at most 999.99.'
            else:
                specs['FuelTankCapacity'] = tank
        except ValueError:
            errors['FuelTankCapacity'] = 'Tank capacity must be a valid number.'

    return errors, specs


@bp.route('/<int:supplier_id>/models/add', methods=['GET', 'POST'])
@login_required
def add_model(supplier_id):
    record, redir = _get_supplier_or_redirect(supplier_id)
    if redir:
        return redir

    existing_ids = set()
    try:
        existing = (
            supabase.table('Supplier_Model').select('Model_Model_No')
            .eq('Supplier_SupplierID', supplier_id).execute()
        )
        existing_ids = {r['Model_Model_No'] for r in (existing.data or [])}
    except Exception:
        pass

    model_options = _get_model_options(exclude_model_nos=existing_ids)
    form_data, errors = {}, {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        model_no_raw = form_data.get('Model_Model_No', '').strip()
        price_raw = form_data.get('BuyingPrice', '').strip()

        model_no = None
        if not model_no_raw:
            errors['Model_Model_No'] = 'Motorbike model is required.'
        else:
            try:
                model_no = int(model_no_raw)
            except ValueError:
                errors['Model_Model_No'] = 'Please select a valid model.'

        price = None
        if not price_raw:
            errors['BuyingPrice'] = 'Buying price is required.'
        elif not is_positive_number(price_raw):
            errors['BuyingPrice'] = 'Buying price must be a valid number of 0 or more.'
        else:
            price = float(price_raw)

        spec_errors, specs = _validate_model_specs(form_data)
        errors.update(spec_errors)

        if not errors:
            try:
                supabase.table('Supplier_Model').insert({
                    'Supplier_SupplierID': supplier_id,
                    'Model_Model_No':      model_no,
                    'BuyingPrice':         price,
                    **specs,
                }).execute()
                flash_success("Model was added to this supplier's catalogue.")
                return redirect(url_for('supplier.view', supplier_id=supplier_id))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['Model_Model_No'] = 'This supplier already has this model listed.'
                else:
                    flash_error(f'Could not add model: {error_msg}')

    return render_template(
        'modules/supplier/model_form.html',
        form_data=form_data, errors=errors, is_edit=False,
        supplier_id=supplier_id, supplier_name=record.get('SupplierName', ''),
        model_options=model_options,
        fuel_type_options=NB_FUEL_TYPE_OPTIONS,
        transmission_options=NB_TRANSMISSION_OPTIONS
    )


@bp.route('/<int:supplier_id>/models/<int:model_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_model(supplier_id, model_id):
    record, redir = _get_supplier_or_redirect(supplier_id)
    if redir:
        return redir

    try:
        row = (
            supabase.table('Supplier_Model').select('*')
            .eq('SupplierModel_ID', model_id)
            .eq('Supplier_SupplierID', supplier_id)
            .single().execute()
        ).data
    except Exception:
        flash_error('Model listing not found.')
        return redirect(url_for('supplier.view', supplier_id=supplier_id))

    model_label = _enrich_supplier_models([dict(row)])[0]['_model_label']
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
        price_raw = form_data.get('BuyingPrice', '').strip()

        price = None
        if not price_raw:
            errors['BuyingPrice'] = 'Buying price is required.'
        elif not is_positive_number(price_raw):
            errors['BuyingPrice'] = 'Buying price must be a valid number of 0 or more.'
        else:
            price = float(price_raw)

        spec_errors, specs = _validate_model_specs(form_data)
        errors.update(spec_errors)

        if not errors:
            try:
                supabase.table('Supplier_Model').update(
                    {'BuyingPrice': price, **specs}
                ).eq('SupplierModel_ID', model_id).execute()
                flash_success('Model listing updated.')
                return redirect(url_for('supplier.view', supplier_id=supplier_id))
            except Exception as e:
                flash_error(f'Could not update model: {str(e)}')

    return render_template(
        'modules/supplier/model_form.html',
        form_data=form_data, errors=errors, is_edit=True,
        supplier_id=supplier_id, supplier_name=record.get('SupplierName', ''),
        model_label=model_label,
        fuel_type_options=NB_FUEL_TYPE_OPTIONS,
        transmission_options=NB_TRANSMISSION_OPTIONS
    )


@bp.route('/<int:supplier_id>/models/<int:model_id>/delete', methods=['POST'])
@login_required
def delete_model(supplier_id, model_id):
    try:
        supabase.table('Supplier_Model').delete().eq('SupplierModel_ID', model_id).execute()
        flash_success('Model removed from this supplier\'s catalogue.')
    except Exception as e:
        flash_error(f'Could not remove model: {str(e)}')
    return redirect(url_for('supplier.view', supplier_id=supplier_id))


# =============================================================================
# SUPPLIER PORTAL LOGIN (Task 35)
# The admin creates the supplier's Supabase Auth user and links it through
# Supplier.AuthUserID. Only these routes use the service-role client.
# =============================================================================

def _get_service_client():
    """
    Lazily import the service-role client so it is only loaded by the portal
    login routes. Returns (client, None) or (None, error_message).
    """
    try:
        from app.supabase_admin_client import supabase_admin
        return supabase_admin, None
    except Exception:
        return None, (
            'Portal logins are not configured on this server. '
            'Add SUPABASE_SERVICE_KEY to the .env file and restart the app.'
        )


def _auth_error_reason(error):
    """Short, safe reason text from a Supabase Auth API error (never a stack trace)."""
    message = getattr(error, 'message', None)
    if getattr(error, 'status', None) and message:
        return message
    return 'the authentication service did not respond as expected'


def _is_email_taken_error(error):
    code = str(getattr(error, 'code', '') or '').lower()
    message = str(getattr(error, 'message', '') or error).lower()
    return code in ('email_exists', 'user_already_exists') or 'already' in message


def _flash_temporary_password(intro, password):
    """
    Show the temporary password once. It is never stored or logged; the
    data-sp-keep-open marker stops this alert from auto-dismissing.
    """
    flash_success(Markup(
        '{intro} Give this temporary password to the supplier now, it will not be '
        'shown again: <code class="sp-temp-password" data-sp-keep-open>{pw}</code>'
    ).format(intro=intro, pw=password))


SHARED_LOGIN_MSG = (
    'This supplier signs in with their online shop account. '
    'To reset the password, they use Forgot password in the shop.'
)
SHARED_LOGIN_KEPT_MSG = 'Supplier deleted. The linked online shop account was kept.'


def _login_is_shared(auth_user_id):
    """
    True when this login is also the person's online shop account (Task 47): a Customer
    profile or a supplier application uses the same AuthUserID. Logins made with
    "Create Portal Login" have neither and are portal-only. Any lookup failure counts as
    shared, so a password reset or user deletion is never risked on a shop account.
    """
    if not auth_user_id:
        return False
    try:
        customers = (
            supabase.table('Customer')
            .select('CustomerID')
            .eq('AuthUserID', auth_user_id)
            .limit(1)
            .execute()
        ).data or []
        applications = (
            supabase.table('Supplier_Application')
            .select('ApplicationID')
            .eq('AuthUserID', auth_user_id)
            .limit(1)
            .execute()
        ).data or []
    except Exception:
        return True
    return bool(customers or applications)


def _delete_portal_user(auth_user_id, supplier_name):
    """Remove the Auth user of a deleted supplier. Failure only produces a warning."""
    admin_client, config_error = _get_service_client()
    if not config_error:
        try:
            admin_client.auth.admin.delete_user(auth_user_id)
            return
        except Exception:
            pass
    flash_warning(
        f'Supplier "{supplier_name}" was deleted, but its portal login could not be '
        f'removed. Delete that user from Supabase Authentication manually.'
    )


@bp.route('/<int:supplier_id>/create-login', methods=['GET', 'POST'])
@login_required
def create_login(supplier_id):
    record, redir = _get_supplier_or_redirect(supplier_id)
    if redir:
        return redir

    if record.get('AuthUserID'):
        flash_error(f'Supplier "{record.get("SupplierName")}" already has a portal login.')
        return redirect(url_for('supplier.view', supplier_id=supplier_id))

    form_data = {'Email': record.get('Email') or ''}
    errors = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        email_value = form_data.get('Email', '').strip()

        if not email_value:
            errors['Email'] = 'Email address is required.'
        elif len(email_value) > 255:
            errors['Email'] = 'Email address must not exceed 255 characters.'
        elif not is_valid_email(email_value):
            errors['Email'] = 'Please enter a valid email address.'

        admin_client = None
        if not errors:
            admin_client, config_error = _get_service_client()
            if config_error:
                flash_error(config_error)

        if not errors and admin_client:
            temp_password = secrets.token_urlsafe(10)
            new_user_id = None
            try:
                created = admin_client.auth.admin.create_user({
                    'email':         email_value,
                    'password':      temp_password,
                    'email_confirm': True,
                })
                new_user_id = created.user.id
            except Exception as e:
                if _is_email_taken_error(e):
                    errors['Email'] = (
                        'This email address is already registered. '
                        'Please use a different email for the portal login.'
                    )
                else:
                    flash_error(f'Could not create the portal login: {_auth_error_reason(e)}.')

            if new_user_id:
                # Link only while the supplier still has no login (protects
                # against two admins creating a login at the same time)
                linked = False
                try:
                    result = (
                        supabase.table('Supplier')
                        .update({'AuthUserID': new_user_id})
                        .eq('SupplierID', supplier_id)
                        .is_('AuthUserID', None)
                        .execute()
                    )
                    linked = bool(result.data)
                except Exception:
                    linked = False

                if linked:
                    _flash_temporary_password(
                        f'Portal login created for {email_value}.', temp_password
                    )
                    return redirect(url_for('supplier.view', supplier_id=supplier_id))

                # Never leave an Auth user that no supplier points to
                try:
                    admin_client.auth.admin.delete_user(new_user_id)
                except Exception:
                    pass
                flash_error(
                    'The login could not be linked to this supplier, so it was removed '
                    'again. Reload the supplier and try again.'
                )

    return render_template(
        'modules/supplier/create_login.html',
        record=record,
        supplier_id=supplier_id,
        form_data=form_data,
        errors=errors
    )


@bp.route('/<int:supplier_id>/reset-password', methods=['POST'])
@login_required
def reset_portal_password(supplier_id):
    record, redir = _get_supplier_or_redirect(supplier_id)
    if redir:
        return redir

    auth_user_id = record.get('AuthUserID')
    if not auth_user_id:
        flash_error('This supplier does not have a portal login yet.')
        return redirect(url_for('supplier.view', supplier_id=supplier_id))

    # Never change the password of a shop account (the button is hidden too, but a
    # forged POST must be refused here).
    if _login_is_shared(auth_user_id):
        flash_error(SHARED_LOGIN_MSG)
        return redirect(url_for('supplier.view', supplier_id=supplier_id))

    admin_client, config_error = _get_service_client()
    if config_error:
        flash_error(config_error)
        return redirect(url_for('supplier.view', supplier_id=supplier_id))

    temp_password = secrets.token_urlsafe(10)
    try:
        admin_client.auth.admin.update_user_by_id(auth_user_id, {'password': temp_password})
    except Exception as e:
        flash_error(f'Could not reset the portal password: {_auth_error_reason(e)}.')
        return redirect(url_for('supplier.view', supplier_id=supplier_id))

    _flash_temporary_password(
        f'Portal password reset for "{record.get("SupplierName")}".', temp_password
    )
    return redirect(url_for('supplier.view', supplier_id=supplier_id))