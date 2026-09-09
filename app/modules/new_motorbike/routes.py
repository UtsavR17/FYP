from flask import render_template, request, redirect, url_for
from app.modules.new_motorbike import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import (
    required_fields, is_positive_number, is_positive_integer
)


# ---------Predefined option lists -0------------------------------------

FUEL_TYPE_OPTIONS = [
    ('Petrol',   'Petrol'),
    # ('Diesel',   'Diesel'),
    ('Electric', 'Electric'),
    ('Hybrid',   'Hybrid'),
]

TRANSMISSION_OPTIONS = [
    ('Manual',         'Manual'),
    ('Automatic',      'Automatic'),
    # ('Semi-Automatic', 'Semi-Automatic'),
]

STATUS_OPTIONS = [
    ('Available', 'Available'),
    ('Sold',      'Sold'),
]

VALID_FUEL_TYPES     = [v for v, _ in FUEL_TYPE_OPTIONS]
VALID_TRANSMISSIONS  = [v for v, _ in TRANSMISSION_OPTIONS]
VALID_STATUSES       = [v for v, _ in STATUS_OPTIONS]


# -------Helpers -----------------------------------------------

def _validate_year(raw_value):
    """Validate manufacture year. Returns (year_int_or_None, error_or_None)."""
    value = (raw_value or '').strip()
    if not value:
        return None, 'Year is required.'
    try:
        year = int(value)
        if year < 1900 or year > 2100:
            return None, 'Year must be between 1900 and 2100.'
        return year, None
    except ValueError:
        return None, 'Year must be a valid 4-digit number.'


def _get_form_options():
    """
    Fetch Model and Color dropdown options.

    Model options: (Model_No, 'Brand_Name - Description') ordered by Description.
    Color options: (Color, Color) ordered by Color.

    Returns:
        model_options: list of (Model_No, label) tuples
        color_options: list of (Color, Color) tuples
    """
    model_options = []
    color_options = []

    # Brand lookup for model labels
    brand_lookup = {}
    try:
        brand_result = (
            supabase.table('Brand')
            .select('Brand_ID, Brand_Name')
            .execute()
        )
        brand_lookup = {
            r['Brand_ID']: r['Brand_Name']
            for r in (brand_result.data or [])
        }
    except Exception:
        pass

    try:
        model_result = (
            supabase.table('Model')
            .select('Model_No, Brand_Brand_ID, Description')
            .order('Description')
            .execute()
        )
        for m in (model_result.data or []):
            brand_name = brand_lookup.get(m.get('Brand_Brand_ID'), 'Unknown Brand')
            label      = f"{brand_name} \u2014 {m['Description']}"
            model_options.append((m['Model_No'], label))
    except Exception:
        pass

    try:
        color_result = (
            supabase.table('Color')
            .select('Color')
            .order('Color')
            .execute()
        )
        color_options = [
            (r['Color'], r['Color'])
            for r in (color_result.data or [])
        ]
    except Exception:
        pass

    return model_options, color_options


def _validate_form(form_data):
    """
    Validate all 11 New_MotorBike form fields.
    Returns (errors_dict, parsed_values_dict).
    parsed_values contains the correctly typed values for database insertion.
    """
    errors = {}
    parsed = {}

    # FK dropdowns
    model_no_raw = form_data.get('Model_Model_No', '').strip()
    color_raw    = form_data.get('Color_Color', '').strip()

    if not model_no_raw:
        errors['Model_Model_No'] = 'Motorbike model is required.'
    else:
        try:
            parsed['Model_Model_No'] = int(model_no_raw)
        except ValueError:
            errors['Model_Model_No'] = 'Please select a valid model.'

    if not color_raw:
        errors['Color_Color'] = 'Color is required.'
    else:
        parsed['Color_Color'] = color_raw

    # Year
    year, year_err = _validate_year(form_data.get('Year', ''))
    if year_err:
        errors['Year'] = year_err
    else:
        parsed['Year'] = year

    # VIN
    vin_value = form_data.get('VIN', '').strip()
    if not vin_value:
        errors['VIN'] = 'VIN is required.'
    elif len(vin_value) > 50:
        errors['VIN'] = 'VIN must not exceed 50 characters.'
    else:
        parsed['VIN'] = vin_value

    # Price
    price_raw = form_data.get('Price', '').strip()
    if not price_raw:
        errors['Price'] = 'Price is required.'
    elif not is_positive_number(price_raw):
        errors['Price'] = 'Price must be a valid number of 0 or more.'
    else:
        parsed['Price'] = float(price_raw)

    # Status
    status_value = form_data.get('Status', '').strip()
    if not status_value:
        errors['Status'] = 'Status is required.'
    elif status_value not in VALID_STATUSES:
        errors['Status'] = 'Please select a valid status.'
    else:
        parsed['Status'] = status_value

    # Warranty_Months
    warranty_raw = form_data.get('Warranty_Months', '').strip()
    if not warranty_raw:
        errors['Warranty_Months'] = 'Warranty months is required.'
    elif not is_positive_integer(warranty_raw):
        errors['Warranty_Months'] = 'Warranty must be a whole number of 0 or more.'
    else:
        parsed['Warranty_Months'] = int(warranty_raw)

    # EngineCC - must be >= 1
    engine_raw = form_data.get('EngineCC', '').strip()
    if not engine_raw:
        errors['EngineCC'] = 'Engine CC is required.'
    elif not is_positive_integer(engine_raw) or int(engine_raw) < 1:
        errors['EngineCC'] = 'Engine CC must be a whole number of at least 1.'
    else:
        parsed['EngineCC'] = int(engine_raw)

    # FuelType
    fuel_value = form_data.get('FuelType', '').strip()
    if not fuel_value:
        errors['FuelType'] = 'Fuel type is required.'
    elif fuel_value not in VALID_FUEL_TYPES:
        errors['FuelType'] = 'Please select a valid fuel type.'
    else:
        parsed['FuelType'] = fuel_value

    # Transmission
    transmission_value = form_data.get('Transmission', '').strip()
    if not transmission_value:
        errors['Transmission'] = 'Transmission type is required.'
    elif transmission_value not in VALID_TRANSMISSIONS:
        errors['Transmission'] = 'Please select a valid transmission type.'
    else:
        parsed['Transmission'] = transmission_value

    # FuelTankCapacity — must be > 0
    tank_raw = form_data.get('FuelTankCapacity', '').strip()
    if not tank_raw:
        errors['FuelTankCapacity'] = 'Fuel tank capacity is required.'
    elif not is_positive_number(tank_raw) or float(tank_raw) <= 0:
        errors['FuelTankCapacity'] = (
            'Fuel tank capacity must be a number greater than 0.'
        )
    else:
        parsed['FuelTankCapacity'] = float(tank_raw)

    return errors, parsed


# --Routes -------------------------------------

@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('New_MotorBike')
            .select('*')
            .order('NB_ID', desc=True)
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load motorbike inventory: {str(e)}')
        all_records = []

    # Build Model label lookup
    brand_lookup = {}
    try:
        brand_result = (
            supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
        )
        brand_lookup = {
            r['Brand_ID']: r['Brand_Name']
            for r in (brand_result.data or [])
        }
    except Exception:
        pass

    model_lookup = {}
    try:
        model_result = (
            supabase.table('Model')
            .select('Model_No, Brand_Brand_ID, Description')
            .execute()
        )
        for m in (model_result.data or []):
            brand_name = brand_lookup.get(m.get('Brand_Brand_ID'), 'Unknown Brand')
            model_lookup[m['Model_No']] = (
                f"{brand_name} \u2014 {m['Description']}"
            )
    except Exception:
        pass

    # Enrich records
    for bike in all_records:
        bike['_model_label'] = model_lookup.get(
            bike.get('Model_Model_No'), '—'
        )

    # Search
    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('_model_label', '').lower()
            or q in r.get('Color_Color', '').lower()
            or q in str(r.get('Year', '') or '')
            or q in r.get('VIN', '').lower()
            or q in r.get('Status', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/new_motorbike/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors = {}
    model_options, color_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        errors, parsed = _validate_form(form_data)

        if not errors:
            try:
                supabase.table('New_MotorBike').insert(parsed).execute()
                flash_success(
                    f'Motorbike VIN "{parsed["VIN"]}" was added to inventory.'
                )
                return redirect(url_for('new_motorbike.index'))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['VIN'] = 'A motorbike with this VIN already exists.'
                else:
                    flash_error(f'Could not add motorbike: {error_msg}')

    return render_template(
        'modules/new_motorbike/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        model_options=model_options,
        color_options=color_options,
        fuel_type_options=FUEL_TYPE_OPTIONS,
        transmission_options=TRANSMISSION_OPTIONS,
        status_options=STATUS_OPTIONS
    )


@bp.route('/edit/<int:nb_id>', methods=['GET', 'POST'])
@login_required
def edit(nb_id):
    try:
        result = (
            supabase.table('New_MotorBike')
            .select('*')
            .eq('NB_ID', nb_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Motorbike ID {nb_id} was not found.')
        return redirect(url_for('new_motorbike.index'))

    errors    = {}
    form_data = record.copy()
    model_options, color_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        errors, parsed = _validate_form(form_data)

        if not errors:
            try:
                supabase.table('New_MotorBike').update(
                    parsed
                ).eq('NB_ID', nb_id).execute()
                flash_success(
                    f'Motorbike NB-{nb_id} was updated successfully.'
                )
                return redirect(url_for('new_motorbike.index'))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['VIN'] = 'A motorbike with this VIN already exists.'
                else:
                    flash_error(f'Could not update motorbike: {error_msg}')

    return render_template(
        'modules/new_motorbike/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        model_options=model_options,
        color_options=color_options,
        fuel_type_options=FUEL_TYPE_OPTIONS,
        transmission_options=TRANSMISSION_OPTIONS,
        status_options=STATUS_OPTIONS
    )


@bp.route('/delete/<int:nb_id>', methods=['POST'])
@login_required
def delete(nb_id):
    try:
        result = (
            supabase.table('New_MotorBike')
            .select('VIN')
            .eq('NB_ID', nb_id)
            .single()
            .execute()
        )
        vin_value = result.data.get('VIN', f'ID {nb_id}')
    except Exception:
        vin_value = f'ID {nb_id}'

    try:
        supabase.table('New_MotorBike').delete().eq('NB_ID', nb_id).execute()
        flash_success(f'Motorbike "{vin_value}" was removed from inventory.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete motorbike "{vin_value}" because it is linked to a sales record.'
                f'Remove the associated sale before deleting this motorbike.'
            )
        else:
            flash_error(f'Could not delete motorbike: {error_msg}')

    return redirect(url_for('new_motorbike.index'))