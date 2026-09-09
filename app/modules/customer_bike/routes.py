from flask import render_template, request, redirect, url_for
from app.modules.customer_bike import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields


def _get_form_options():
    """
    Fetch dropdown options for the Customer Bike Create and Edit forms.

    Customer options: (CustomerID, 'FirstName LastName') ordered by LastName.
    Model options:    (Model_No, 'Brand_Name — Description') ordered by Description.

    Returns:
        customer_options: list of (CustomerID, full_name) tuples
        model_options:    list of (Model_No, label) tuples
    """
    customer_options = []
    model_options    = []

    try:
        cust_result = (
            supabase.table('Customer')
            .select('CustomerID, FirstName, LastName')
            .order('LastName')
            .execute()
        )
        customer_options = [
            (r['CustomerID'], f"{r['FirstName']} {r['LastName']}")
            for r in (cust_result.data or [])
        ]
    except Exception:
        pass

    # Brand lookup needed to build model labels
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

    return customer_options, model_options


def _validate_year(raw_value):
    """
    Validate the Year field.
    Returns (year_int_or_None, error_string_or_None).
    """
    value = (raw_value or '').strip()
    if not value:
        return None, 'Year of manufacture is required.'
    try:
        year = int(value)
        if year < 1900 or year > 2100:
            return None, 'Year must be between 1900 and 2100.'
        return year, None
    except ValueError:
        return None, 'Year must be a valid 4-digit number.'


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Customer_bike')
            .select('*')
            .order('BikeID', desc=True)
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load bike registrations: {str(e)}')
        all_records = []

    # Build Customer lookup dict
    customer_lookup = {}
    try:
        cust_result = (
            supabase.table('Customer')
            .select('CustomerID, FirstName, LastName')
            .execute()
        )
        customer_lookup = {
            r['CustomerID']: f"{r['FirstName']} {r['LastName']}"
            for r in (cust_result.data or [])
        }
    except Exception:
        pass

    # Build Brand lookup and Model label lookup
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
            model_lookup[m['Model_No']] = f"{brand_name} \u2014 {m['Description']}"
    except Exception:
        pass

    # Enrich each record
    for bike in all_records:
        bike['_customer_name'] = customer_lookup.get(
            bike.get('Customer_CustomerID'), '—'
        )
        bike['_model_label'] = model_lookup.get(
            bike.get('Model_Model_No'), '—'
        )

    # Search
    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('RegistrationNumber', '').lower()
            or q in r.get('VIN', '').lower()
            or q in r.get('_customer_name', '').lower()
            or q in r.get('_model_label', '').lower()
            or q in str(r.get('Year', '') or '')
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/customer_bike/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors    = {}
    customer_options, model_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        cust_id_raw  = form_data.get('Customer_CustomerID', '').strip()
        model_no_raw = form_data.get('Model_Model_No', '').strip()
        reg_value    = form_data.get('RegistrationNumber', '').strip()
        year_raw     = form_data.get('Year', '')
        vin_value    = form_data.get('VIN', '').strip()

        # Customer validation
        customer_id = None
        if not cust_id_raw:
            errors['Customer_CustomerID'] = 'Customer is required.'
        else:
            try:
                customer_id = int(cust_id_raw)
            except ValueError:
                errors['Customer_CustomerID'] = 'Please select a valid customer.'

        # Model validation
        model_no = None
        if not model_no_raw:
            errors['Model_Model_No'] = 'Motorbike model is required.'
        else:
            try:
                model_no = int(model_no_raw)
            except ValueError:
                errors['Model_Model_No'] = 'Please select a valid model.'

        # Registration Number
        if not reg_value:
            errors['RegistrationNumber'] = 'Registration number is required.'
        elif len(reg_value) > 6:
            errors['RegistrationNumber'] = (
                'Registration number must not exceed 6 characters.'
            )

        # Year
        year, year_err = _validate_year(year_raw)
        if year_err:
            errors['Year'] = year_err

        # VIN
        if not vin_value:
            errors['VIN'] = 'VIN is required.'
        elif len(vin_value) > 50:
            errors['VIN'] = 'VIN must not exceed 50 characters.'

        if not errors:
            try:
                supabase.table('Customer_bike').insert({
                    'Customer_CustomerID': customer_id,
                    'Model_Model_No':      model_no,
                    'RegistrationNumber':  reg_value,
                    'Year':               year,
                    'VIN':                vin_value,
                }).execute()
                flash_success(
                    f'Bike registration "{reg_value}" was added successfully.'
                )
                return redirect(url_for('customer_bike.index'))
                
            # except Exception as e:
            #     flash_error(f'Could not add bike registration: {str(e)}')
                        
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    if 'vin' in error_msg.lower():
                        flash_error(
                            'A bike with this VIN already exists in the system. '
                            'If ownership has changed, edit the existing record et update Customer field to new owner.'
                        )
                    elif 'registration' in error_msg.lower():
                        flash_error(
                            'A bike with this registration number already exists. '
                            'If ownership has changed, edit the existing record et update Customer field to new owner.'
                        )
                    else:
                        flash_error(
                            'A duplicate VIN or registration number was detected.'
                        )
                else:
                    flash_error(f'Could not add bike registration: {error_msg}')

    return render_template(
        'modules/customer_bike/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        customer_options=customer_options,
        model_options=model_options
    )


@bp.route('/edit/<int:bike_id>', methods=['GET', 'POST'])
@login_required
def edit(bike_id):
    try:
        result = (
            supabase.table('Customer_bike')
            .select('*')
            .eq('BikeID', bike_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Bike registration ID {bike_id} was not found.')
        return redirect(url_for('customer_bike.index'))

    errors    = {}
    form_data = record.copy()
    customer_options, model_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        cust_id_raw  = form_data.get('Customer_CustomerID', '').strip()
        model_no_raw = form_data.get('Model_Model_No', '').strip()
        reg_value    = form_data.get('RegistrationNumber', '').strip()
        year_raw     = form_data.get('Year', '')
        vin_value    = form_data.get('VIN', '').strip()

        customer_id = None
        if not cust_id_raw:
            errors['Customer_CustomerID'] = 'Customer is required.'
        else:
            try:
                customer_id = int(cust_id_raw)
            except ValueError:
                errors['Customer_CustomerID'] = 'Please select a valid customer.'

        model_no = None
        if not model_no_raw:
            errors['Model_Model_No'] = 'Motorbike model is required.'
        else:
            try:
                model_no = int(model_no_raw)
            except ValueError:
                errors['Model_Model_No'] = 'Please select a valid model.'

        if not reg_value:
            errors['RegistrationNumber'] = 'Registration number is required.'
        elif len(reg_value) > 6:
            errors['RegistrationNumber'] = (
                'Registration number must not exceed 6 characters.'
            )

        year, year_err = _validate_year(year_raw)
        if year_err:
            errors['Year'] = year_err

        if not vin_value:
            errors['VIN'] = 'VIN is required.'
        elif len(vin_value) > 50:
            errors['VIN'] = 'VIN must not exceed 50 characters.'

        if not errors:
            try:
                supabase.table('Customer_bike').update({
                    'Customer_CustomerID': customer_id,
                    'Model_Model_No':      model_no,
                    'RegistrationNumber':  reg_value,
                    'Year':               year,
                    'VIN':                vin_value,
                }).eq('BikeID', bike_id).execute()
                flash_success(
                    f'Bike registration "{reg_value}" was updated successfully.'
                )
                return redirect(url_for('customer_bike.index'))


            # except Exception as e:
            #     flash_error(f'Could not update bike registration: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    if 'vin' in error_msg.lower():
                        flash_error(
                            'A bike with this VIN already exists in the system.'
                        )
                    elif 'registration' in error_msg.lower():
                        flash_error(
                            'A bike with this registration number already exists.'
                        )
                    else:
                        flash_error(
                            'A duplicate VIN or registration number was detected.'
                        )
                else:
                    flash_error(f'Could not update bike registration: {error_msg}')

                    

    return render_template(
        'modules/customer_bike/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        customer_options=customer_options,
        model_options=model_options
    )


@bp.route('/delete/<int:bike_id>', methods=['POST'])
@login_required
def delete(bike_id):
    try:
        result = (
            supabase.table('Customer_bike')
            .select('RegistrationNumber')
            .eq('BikeID', bike_id)
            .single()
            .execute()
        )
        reg_value = result.data.get('RegistrationNumber', f'ID {bike_id}')
    except Exception:
        reg_value = f'ID {bike_id}'

    try:
        supabase.table('Customer_bike').delete().eq('BikeID', bike_id).execute()
        flash_success(
            f'Bike registration "{reg_value}" was deleted successfully.'
        )
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete bike "{reg_value}" because it has one or more associated appointments. '
                f'Remove those appointment records first before deleting this bike registration.'
            )
        else:
            flash_error(f'Could not delete bike registration: {error_msg}')

    return redirect(url_for('customer_bike.index'))