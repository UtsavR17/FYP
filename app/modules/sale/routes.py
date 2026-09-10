from pydantic_core.core_schema import ExpectedSerializationTypes
from flask import render_template, request, redirect, url_for
from app.modules.sale import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields, is_positive_number
from datetime import date as date_type


# Helpers -----------------------------------

def _validate_date(raw_value, field_label):
    """Validate a date string. Returns (date_str_or_None, error_or_None)."""
    value = (raw_value or '').strip()
    if not value:
        return None, f'{field_label} is required.'
    try:
        date_type.fromisoformat(value)
        return value, None
    except ValueError:
        return None, f'{field_label} must be a valid date.'


def _build_bike_label(nb_id, year, model_desc, brand_name):
    """Build a consistent display label for a New_MotorBike record."""
    return f"NB-{nb_id} \u2014 {brand_name} {model_desc} ({year})"


def _get_brand_model_lookups():
    """Fetch Brand and Model lookups for bike label building."""
    brand_lookup = {}
    model_lookup = {}

    try:
        br = supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
        brand_lookup = {r['Brand_ID']: r['Brand_Name'] for r in (br.data or [])}
    except Exception:
        pass

    try:
        ml = (
            supabase.table('Model')
            .select('Model_No, Brand_Brand_ID, Description')
            .execute()
        )
        for m in (ml.data or []):
            brand_name = brand_lookup.get(m.get('Brand_Brand_ID'), 'Unknown Brand')
            model_lookup[m['Model_No']] = {
                'description': m['Description'],
                'brand_name':  brand_name,
            }
    except Exception:
        pass

    return brand_lookup, model_lookup


def _get_form_options(current_nb_id=None):
    """
    Fetch dropdown options for the Sale Create and Edit forms.

    customer_options: (CustomerID, 'FirstName LastName') ordered by LastName.
    bike_options:     (NB_ID, label) - Available bikes only on Create.
                      On Edit, also includes the currently linked bike.
    employee_options: (EmployeeID, 'FirstName LastName') ordered by LastName.

    Returns:
        customer_options, bike_options, employee_options, has_available_bikes
    """
    customer_options  = []
    bike_options      = []
    employee_options  = []

    try:
        cust = (
            supabase.table('Customer')
            .select('CustomerID, FirstName, LastName')
            .order('LastName')
            .execute()
        )
        customer_options = [
            (r['CustomerID'], f"{r['FirstName']} {r['LastName']}")
            for r in (cust.data or [])
        ]
    except Exception:
        pass

    _, model_lookup = _get_brand_model_lookups()

    # # Fetch Available bikes
    # try:
    #     available_bikes = (
    #         supabase.table('New_MotorBike')
    #         .select('NB_ID, Year, Model_Model_No, Status')
    #         .eq('Status', 'Available')
    #         .order('NB_ID')
    #         .execute()
    #     )
    #     for b in (available_bikes.data or []):
    #         m_info = model_lookup.get(b.get('Model_Model_No'), {})
    #         label  = _build_bike_label(
    #             b['NB_ID'],
    #             b.get('Year', '?'),
    #             m_info.get('description', 'Unknown Model'),
    #             m_info.get('brand_name', 'Unknown Brand')
    #         )
    #         bike_options.append((b['NB_ID'], label))
    # except Exception:
    #     pass



    # Fetch Available bikes
    bike_prices = {}
    try:
        available_bikes = (
            supabase.table('New_MotorBike')
            .select('NB_ID, Year, Model_Model_No, Status, Price')
            .eq('Status', 'Available')
            .order('NB_ID')
            .execute()
        )
        for b in (available_bikes.data or []):
            m_info = model_lookup.get(b.get('Model_Model_No'), {})
            label  = _build_bike_label(
                b['NB_ID'],
                b.get('Year', '?'),
                m_info.get('description', 'Unknown Model'),
                m_info.get('brand_name', 'Unknown Brand')
            )
            bike_options.append((b['NB_ID'], label))
            bike_prices[b['NB_ID']] = float(b.get('Price') or 0)
    except Exception:
        pass

        # On Edit, include the currently linked bike if it is not already in the list
    if current_nb_id is not None:
        ids_in_options = {bid for bid, _ in bike_options}
        if current_nb_id not in ids_in_options:
            try:
                curr = (
                    supabase.table('New_MotorBike')
                    .select('NB_ID, Year, Model_Model_No, Price')
                    .eq('NB_ID', current_nb_id)
                    .single()
                    .execute()
                )
                b      = curr.data
                m_info = model_lookup.get(b.get('Model_Model_No'), {})
                label  = _build_bike_label(
                    b['NB_ID'],
                    b.get('Year', '?'),
                    m_info.get('description', 'Unknown Model'),
                    m_info.get('brand_name', 'Unknown Brand')
                )
                # Insert at the beginning so it is pre-selected easily
                bike_options.insert(0, (b['NB_ID'], label))
                bike_prices[b['NB_ID']] = float(b.get('Price') or 0)
            except Exception:
                pass

    has_available_bikes = len(bike_options) > 0

    try:
        emp = (
            supabase.table('Employee')
            .select('EmployeeID, FirstName, LastName')
            .order('LastName')
            .execute()
        )
        employee_options = [
            (r['EmployeeID'], f"{r['FirstName']} {r['LastName']}")
            for r in (emp.data or [])
        ]
    except Exception:
        pass

    return customer_options, bike_options, employee_options, has_available_bikes, bike_prices


def _set_bike_status(nb_id, status):
    """
    Update a New_MotorBike record's Status field.
    Called after sale create, edit, or delete to keep bike availability current.
    Non-fatal: logs silently if it fails so the sale operation still completes.
    """
    try:
        supabase.table('New_MotorBike').update(
            {'Status': status}
        ).eq('NB_ID', nb_id).execute()
    except Exception:
        pass


def _enrich_sales(all_records):
    """Enrich sale records with resolved Customer, Bike, and Employee names."""
    customer_lookup = {}
    try:
        cust = (
            supabase.table('Customer')
            .select('CustomerID, FirstName, LastName')
            .execute()
        )
        customer_lookup = {
            r['CustomerID']: f"{r['FirstName']} {r['LastName']}"
            for r in (cust.data or [])
        }
    except Exception:
        pass

    emp_lookup = {}
    try:
        emp = (
            supabase.table('Employee')
            .select('EmployeeID, FirstName, LastName')
            .execute()
        )
        emp_lookup = {
            r['EmployeeID']: f"{r['FirstName']} {r['LastName']}"
            for r in (emp.data or [])
        }
    except Exception:
        pass

    _, model_lookup = _get_brand_model_lookups()

    bike_lookup = {}
    try:
        bikes = (
            supabase.table('New_MotorBike')
            .select('NB_ID, Year, Model_Model_No')
            .execute()
        )
        for b in (bikes.data or []):
            m_info = model_lookup.get(b.get('Model_Model_No'), {})
            bike_lookup[b['NB_ID']] = _build_bike_label(
                b['NB_ID'],
                b.get('Year', '?'),
                m_info.get('description', 'Unknown Model'),
                m_info.get('brand_name', 'Unknown Brand')
            )
    except Exception:
        pass

    for sale in all_records:
        sale['_customer_name'] = customer_lookup.get(
            sale.get('Customer_CustomerID'), '-'
        )
        sale['_bike_label'] = bike_lookup.get(
            sale.get('New_MotorBike_NB_ID'), '-'
        )
        emp_id = sale.get('Employee_EmployeeID')
        sale['_employee_name'] = emp_lookup.get(emp_id, '-') if emp_id else '-'

    return all_records


# ─── Routes ──────────────────────────────────────────────────────────────────

@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Sale')
            .select('*')
            .order('SaleID', desc=True)
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load sales: {str(e)}')
        all_records = []

    all_records = _enrich_sales(all_records)

    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('_customer_name', '').lower()
            or q in r.get('_bike_label', '').lower()
            or q in r.get('_employee_name', '').lower()
            or q in str(r.get('SaleDate', '') or '')
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/sale/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors    = {}


    customer_options, bike_options, employee_options, has_available_bikes, bike_prices = (
        _get_form_options()
    )

    if request.method == 'POST':
        form_data = request.form.to_dict()

        cust_id_raw = form_data.get('Customer_CustomerID', '').strip()
        nb_id_raw   = form_data.get('New_MotorBike_NB_ID', '').strip()
        emp_id_raw  = form_data.get('Employee_EmployeeID', '').strip()
        date_raw    = form_data.get('SaleDate', '').strip()
        amount_raw  = form_data.get('TotalAmount', '').strip()

        customer_id = None
        if not cust_id_raw:
            errors['Customer_CustomerID'] = 'Customer is required.'
        else:
            try:
                customer_id = int(cust_id_raw)
            except ValueError:
                errors['Customer_CustomerID'] = 'Please select a valid customer.'

        nb_id = None
        if not nb_id_raw:
            errors['New_MotorBike_NB_ID'] = 'Motorbike is required.'
        else:
            try:
                nb_id = int(nb_id_raw)
            except ValueError:
                errors['New_MotorBike_NB_ID'] = 'Please select a valid motorbike.'

        sale_date, date_err = _validate_date(date_raw, 'Sale Date')
        if date_err:
            errors['SaleDate'] = date_err

        total_amount = None
        if not amount_raw:
            errors['TotalAmount'] = 'Total amount is required.'
        elif not is_positive_number(amount_raw):
            errors['TotalAmount'] = 'Total amount must be a valid number of 0 or more.'
        else:
            total_amount = float(amount_raw)

        employee_id = None
        if emp_id_raw:
            try:
                employee_id = int(emp_id_raw)
            except ValueError:
                errors['Employee_EmployeeID'] = 'Invalid salesperson selection.'

        if not errors:
            try:
                supabase.table('Sale').insert({
                    'Customer_CustomerID': customer_id,
                    'New_MotorBike_NB_ID': nb_id,
                    'Employee_EmployeeID': employee_id,
                    'SaleDate':            sale_date,
                    'TotalAmount':         total_amount,
                }).execute()

                # Mark the bike as Sold
                _set_bike_status(nb_id, 'Sold')

                flash_success('Sale was recorded successfully.')
                return redirect(url_for('sale.index'))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['New_MotorBike_NB_ID'] = (
                        'This motorbike is already linked to another sale. '
                        'Each bike can only be sold once.'
                    )
                else:
                    flash_error(f'Could not record sale: {error_msg}')

    return render_template(
        'modules/sale/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        customer_options=customer_options,
        bike_options=bike_options,
        employee_options=employee_options,
        has_available_bikes=has_available_bikes,
        bike_prices=bike_prices
    )


@bp.route('/edit/<int:sale_id>', methods=['GET', 'POST'])
@login_required
def edit(sale_id):
    try:
        result = (
            supabase.table('Sale')
            .select('*')
            .eq('SaleID', sale_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Sale ID {sale_id} was not found.')
        return redirect(url_for('sale.index'))

    original_nb_id = record.get('New_MotorBike_NB_ID')
    errors         = {}
    form_data      = record.copy()

    customer_options, bike_options, employee_options, has_available_bikes, bike_prices = (
        _get_form_options(current_nb_id=original_nb_id)
    )

    if request.method == 'POST':
        form_data = request.form.to_dict()

        cust_id_raw = form_data.get('Customer_CustomerID', '').strip()
        nb_id_raw   = form_data.get('New_MotorBike_NB_ID', '').strip()
        emp_id_raw  = form_data.get('Employee_EmployeeID', '').strip()
        date_raw    = form_data.get('SaleDate', '').strip()
        amount_raw  = form_data.get('TotalAmount', '').strip()

        customer_id = None
        if not cust_id_raw:
            errors['Customer_CustomerID'] = 'Customer is required.'
        else:
            try:
                customer_id = int(cust_id_raw)
            except ValueError:
                errors['Customer_CustomerID'] = 'Please select a valid customer.'

        nb_id = None
        if not nb_id_raw:
            errors['New_MotorBike_NB_ID'] = 'Motorbike is required.'
        else:
            try:
                nb_id = int(nb_id_raw)
            except ValueError:
                errors['New_MotorBike_NB_ID'] = 'Please select a valid motorbike.'

        sale_date, date_err = _validate_date(date_raw, 'Sale Date')
        if date_err:
            errors['SaleDate'] = date_err

        total_amount = None
        if not amount_raw:
            errors['TotalAmount'] = 'Total amount is required.'
        elif not is_positive_number(amount_raw):
            errors['TotalAmount'] = 'Total amount must be a valid number of 0 or more.'
        else:
            total_amount = float(amount_raw)

        employee_id = None
        if emp_id_raw:
            try:
                employee_id = int(emp_id_raw)
            except ValueError:
                errors['Employee_EmployeeID'] = 'Invalid salesperson selection.'

        if not errors:
            try:
                supabase.table('Sale').update({
                    'Customer_CustomerID': customer_id,
                    'New_MotorBike_NB_ID': nb_id,
                    'Employee_EmployeeID': employee_id,
                    'SaleDate':            sale_date,
                    'TotalAmount':         total_amount,
                }).eq('SaleID', sale_id).execute()

                # Handle bike status change
                if nb_id != original_nb_id:
                    # Reset the old bike to Available
                    _set_bike_status(original_nb_id, 'Available')
                    # Mark the new bike as Sold
                    _set_bike_status(nb_id, 'Sold')

                flash_success(f'Sale SALE-{sale_id} was updated successfully.')
                return redirect(url_for('sale.index'))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['New_MotorBike_NB_ID'] = (
                        'This motorbike is already linked to another sale. '
                        'Each bike can only be sold once.'
                    )
                else:
                    flash_error(f'Could not update sale: {error_msg}')

    return render_template(
        'modules/sale/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        customer_options=customer_options,
        bike_options=bike_options,
        employee_options=employee_options,
        has_available_bikes=True,  
        bike_prices=bike_prices
    )


@bp.route('/view/<int:sale_id>')
@login_required
def view(sale_id):
    try:
        result = (
            supabase.table('Sale')
            .select('*')
            .eq('SaleID', sale_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Sale ID {sale_id} was not found.')
        return redirect(url_for('sale.index'))

    # Resolve Customer name
    customer_name = '—'
    try:
        c = (
            supabase.table('Customer')
            .select('FirstName, LastName')
            .eq('CustomerID', record.get('Customer_CustomerID'))
            .single()
            .execute()
        )
        customer_name = f"{c.data['FirstName']} {c.data['LastName']}"
    except Exception:
        pass

    # Resolve Bike label
    bike_label = '—'
    _, model_lookup = _get_brand_model_lookups()
    try:
        b = (
            supabase.table('New_MotorBike')
            .select('NB_ID, Year, Model_Model_No, Status')
            .eq('NB_ID', record.get('New_MotorBike_NB_ID'))
            .single()
            .execute()
        )
        bdata  = b.data
        m_info = model_lookup.get(bdata.get('Model_Model_No'), {})
        bike_label = _build_bike_label(
            bdata['NB_ID'],
            bdata.get('Year', '?'),
            m_info.get('description', 'Unknown Model'),
            m_info.get('brand_name', 'Unknown Brand')
        )
    except Exception:
        pass

    # Resolve Employee name
    employee_name = '—'
    emp_id = record.get('Employee_EmployeeID')
    if emp_id:
        try:
            e = (
                supabase.table('Employee')
                .select('FirstName, LastName')
                .eq('EmployeeID', emp_id)
                .single()
                .execute()
            )
            employee_name = f"{e.data['FirstName']} {e.data['LastName']}"
        except Exception:
            pass

    # Check for linked payment (Task 26 will expand this)
    payment = None
    try:
        pay_result = (
            supabase.table('Payment')
            .select('*')
            .eq('Sale_SaleID', sale_id)
            .execute()
        )
        payments = pay_result.data or []
        if payments:
            payment = payments[0]
    except Exception:
        pass

    return render_template(
        'modules/sale/view.html',
        record=record,
        sale_id=sale_id,
        customer_name=customer_name,
        bike_label=bike_label,
        employee_name=employee_name,
        payment=payment
    )


@bp.route('/delete/<int:sale_id>', methods=['POST'])
@login_required
def delete(sale_id):
    # Fetch the linked bike ID before deleting
    nb_id = None
    try:
        result = (
            supabase.table('Sale')
            .select('New_MotorBike_NB_ID')
            .eq('SaleID', sale_id)
            .single()
            .execute()
        )
        nb_id = result.data.get('New_MotorBike_NB_ID')
    except Exception:
        pass

    try:
        supabase.table('Sale').delete().eq('SaleID', sale_id).execute()

        # Reset the bike to Available
        if nb_id:
            _set_bike_status(nb_id, 'Available')

        flash_success(f'Sale SALE-{sale_id} was deleted and the motorbike has been reset to Available.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete SALE-{sale_id} because it has an associated payment record. '
                f'Remove the payment record first before deleting this sale.'
            )
        else:
            flash_error(f'Could not delete sale: {error_msg}')

    return redirect(url_for('sale.index'))