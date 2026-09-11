import re
from flask import render_template, request, redirect, url_for
from app.modules.appointment import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields, is_positive_integer
from datetime import date as date_type


# -- Predefined option lists -----------------------

APPOINTMENT_TYPE_OPTIONS = [
    ('Service',    'Service'),
    ('Repair',     'Repair'),
    ('Inspection', 'Inspection'),
    ('Other',      'Other'),
]

STATUS_OPTIONS = [
    ('Pending',     'Pending'),
    ('Confirmed',   'Confirmed'),
    ('In Progress', 'In Progress'),
    ('Completed',   'Completed'),
    ('Cancelled',   'Cancelled'),
    ('No Show',     'No Show'),
]

VALID_TYPES    = [v for v, _ in APPOINTMENT_TYPE_OPTIONS]
VALID_STATUSES = [v for v, _ in STATUS_OPTIONS]
LOCKED_STATUSES = ('Completed', 'Cancelled')


#  Helpers -------------------------------

def _truncate_time(time_str):
    """Convert HH:MM:SS to HH:MM for HTML time input pre-population."""
    if time_str and len(time_str) >= 5:
        return time_str[:5]
    return time_str or ''


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


def _validate_time(raw_value):
    """Validate a time string in HH:MM format. Returns (time_str_or_None, error_or_None)."""
    value = (raw_value or '').strip()
    if not value:
        return None, 'Appointment time is required.'
    if re.match(r'^\d{2}:\d{2}(:\d{2})?$', value):
        return value, None
    return None, 'Appointment time must be a valid time in HH:MM format.'


def _get_form_options():
    """
    Fetch Customer_bike and Employee dropdown options for appointment forms.

    Customer_bike label: 'RegistrationNumber - FirstName LastName'
    Employee label:      'FirstName LastName'
    """
    bike_options     = []
    employee_options = []

    # Customer lookup for bike labels
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

    try:
        bike_result = (
            supabase.table('Customer_bike')
            .select('BikeID, RegistrationNumber, Customer_CustomerID')
            .order('RegistrationNumber')
            .execute()
        )
        for b in (bike_result.data or []):
            customer_name = customer_lookup.get(
                b.get('Customer_CustomerID'), 'Unknown Customer'
            )
            label = f"{b['RegistrationNumber']} \u2014 {customer_name}"
            bike_options.append((b['BikeID'], label))
    except Exception:
        pass

    try:
        emp_result = (
            supabase.table('Employee')
            .select('EmployeeID, FirstName, LastName')
            .order('LastName')
            .execute()
        )
        employee_options = [
            (r['EmployeeID'], f"{r['FirstName']} {r['LastName']}")
            for r in (emp_result.data or [])
        ]
    except Exception:
        pass

    return bike_options, employee_options


def _get_appointment_or_redirect(appt_id):
    """
    Fetch a single Appointment record.
    Returns (record, None) on success or (None, redirect_response) on failure.
    """
    try:
        result = (
            supabase.table('Appointment')
            .select('*')
            .eq('AppointmentID', appt_id)
            .single()
            .execute()
        )
        return result.data, None
    except Exception:
        flash_error(f'Appointment ID {appt_id} was not found.')
        return None, redirect(url_for('appointment.index'))


def _enrich_appointments(all_records):
    """Build lookup dicts and enrich appointment records for list display."""
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

    bike_lookup = {}
    try:
        bike_result = (
            supabase.table('Customer_bike')
            .select('BikeID, RegistrationNumber, Customer_CustomerID')
            .execute()
        )
        for b in (bike_result.data or []):
            customer_name = customer_lookup.get(
                b.get('Customer_CustomerID'), 'Unknown'
            )
            bike_lookup[b['BikeID']] = (
                f"{b['RegistrationNumber']} \u2014 {customer_name}"
            )
    except Exception:
        pass

    emp_lookup = {}
    try:
        emp_result = (
            supabase.table('Employee')
            .select('EmployeeID, FirstName, LastName')
            .execute()
        )
        emp_lookup = {
            r['EmployeeID']: f"{r['FirstName']} {r['LastName']}"
            for r in (emp_result.data or [])
        }
    except Exception:
        pass

    for appt in all_records:
        appt['_bike_label'] = bike_lookup.get(
            appt.get('Customer_bike_BikeID'), '—'
        )
        appt['_employee_name'] = emp_lookup.get(
            appt.get('Employee_EmployeeID'), '—'
        )

    return all_records


# ----- Appointment CRUD routes -------------------------=-

@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Appointment')
            .select('*')
            .order('AppointmentID', desc=True)
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load appointments: {str(e)}')
        all_records = []

    all_records = _enrich_appointments(all_records)

    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('_bike_label', '').lower()
            or q in r.get('_employee_name', '').lower()
            or q in r.get('AppointmentType', '').lower()
            or q in r.get('Status', '').lower()
            or q in str(r.get('Appointment_Date', '') or '')
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/appointment/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors    = {}
    bike_options, employee_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        bike_id_raw   = form_data.get('Customer_bike_BikeID', '').strip()
        emp_id_raw    = form_data.get('Employee_EmployeeID', '').strip()
        date_raw      = form_data.get('Appointment_Date', '').strip()
        time_raw      = form_data.get('Appointment_time', '').strip()
        appt_type     = form_data.get('AppointmentType', '').strip()
        status_value  = form_data.get('Status', '').strip()

        bike_id = None
        if not bike_id_raw:
            errors['Customer_bike_BikeID'] = 'Customer bike is required.'
        else:
            try:
                bike_id = int(bike_id_raw)
            except ValueError:
                errors['Customer_bike_BikeID'] = 'Please select a valid bike.'

        emp_id = None
        if not emp_id_raw:
            errors['Employee_EmployeeID'] = 'Employee is required.'
        else:
            try:
                emp_id = int(emp_id_raw)
            except ValueError:
                errors['Employee_EmployeeID'] = 'Please select a valid employee.'

        appt_date, date_err = _validate_date(date_raw, 'Appointment Date')
        if date_err:
            errors['Appointment_Date'] = date_err

        appt_time, time_err = _validate_time(time_raw)
        if time_err:
            errors['Appointment_time'] = time_err

        if not appt_type:
            errors['AppointmentType'] = 'Appointment type is required.'
        elif appt_type not in VALID_TYPES:
            errors['AppointmentType'] = 'Please select a valid appointment type.'

        if not status_value:
            errors['Status'] = 'Status is required.'
        elif status_value not in VALID_STATUSES:
            errors['Status'] = 'Please select a valid status.'

        if not errors:
            try:
                supabase.table('Appointment').insert({
                    'Customer_bike_BikeID': bike_id,
                    'Employee_EmployeeID':  emp_id,
                    'Appointment_Date':     appt_date,
                    'Appointment_time':     appt_time,
                    'AppointmentType':      appt_type,
                    'Status':               status_value,
                }).execute()
                flash_success('Appointment was created successfully.')
                return redirect(url_for('appointment.index'))
            except Exception as e:
                flash_error(f'Could not create appointment: {str(e)}')

    return render_template(
        'modules/appointment/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        bike_options=bike_options,
        employee_options=employee_options,
        type_options=APPOINTMENT_TYPE_OPTIONS,
        status_options=STATUS_OPTIONS
    )


@bp.route('/edit/<int:appt_id>', methods=['GET', 'POST'])
@login_required
def edit(appt_id):
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir

    errors    = {}
    form_data = record.copy()
    # Truncate time for HTML time input pre-population
    form_data['Appointment_time'] = _truncate_time(
        form_data.get('Appointment_time', '')
    )
    bike_options, employee_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        bike_id_raw  = form_data.get('Customer_bike_BikeID', '').strip()
        emp_id_raw   = form_data.get('Employee_EmployeeID', '').strip()
        date_raw     = form_data.get('Appointment_Date', '').strip()
        time_raw     = form_data.get('Appointment_time', '').strip()
        appt_type    = form_data.get('AppointmentType', '').strip()
        status_value = form_data.get('Status', '').strip()

        bike_id = None
        if not bike_id_raw:
            errors['Customer_bike_BikeID'] = 'Customer bike is required.'
        else:
            try:
                bike_id = int(bike_id_raw)
            except ValueError:
                errors['Customer_bike_BikeID'] = 'Please select a valid bike.'

        emp_id = None
        if not emp_id_raw:
            errors['Employee_EmployeeID'] = 'Employee is required.'
        else:
            try:
                emp_id = int(emp_id_raw)
            except ValueError:
                errors['Employee_EmployeeID'] = 'Please select a valid employee.'

        appt_date, date_err = _validate_date(date_raw, 'Appointment Date')
        if date_err:
            errors['Appointment_Date'] = date_err

        appt_time, time_err = _validate_time(time_raw)
        if time_err:
            errors['Appointment_time'] = time_err

        if not appt_type:
            errors['AppointmentType'] = 'Appointment type is required.'
        elif appt_type not in VALID_TYPES:
            errors['AppointmentType'] = 'Please select a valid appointment type.'

        if not status_value:
            errors['Status'] = 'Status is required.'
        elif status_value not in VALID_STATUSES:
            errors['Status'] = 'Please select a valid status.'

        if not errors:
            try:
                supabase.table('Appointment').update({
                    'Customer_bike_BikeID': bike_id,
                    'Employee_EmployeeID':  emp_id,
                    'Appointment_Date':     appt_date,
                    'Appointment_time':     appt_time,
                    'AppointmentType':      appt_type,
                    'Status':               status_value,
                }).eq('AppointmentID', appt_id).execute()
                flash_success(
                    f'Appointment #{appt_id} was updated successfully.'
                )
                return redirect(url_for('appointment.index'))
            except Exception as e:
                flash_error(f'Could not update appointment: {str(e)}')

    return render_template(
        'modules/appointment/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        bike_options=bike_options,
        employee_options=employee_options,
        type_options=APPOINTMENT_TYPE_OPTIONS,
        status_options=STATUS_OPTIONS
    )


@bp.route('/view/<int:appt_id>')
@login_required
def view(appt_id):
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir

    # Resolve bike label
    bike_label = '—'
    try:
        bike_result = (
            supabase.table('Customer_bike')
            .select('RegistrationNumber, Customer_CustomerID')
            .eq('BikeID', record.get('Customer_bike_BikeID'))
            .single()
            .execute()
        )
        bike_data = bike_result.data
        cust_result = (
            supabase.table('Customer')
            .select('FirstName, LastName')
            .eq('CustomerID', bike_data.get('Customer_CustomerID'))
            .single()
            .execute()
        )
        cust = cust_result.data
        bike_label = (
            f"{bike_data['RegistrationNumber']} \u2014 "
            f"{cust['FirstName']} {cust['LastName']}"
        )
    except Exception:
        pass

    # Resolve employee name
    employee_name = '—'
    try:
        emp_result = (
            supabase.table('Employee')
            .select('FirstName, LastName')
            .eq('EmployeeID', record.get('Employee_EmployeeID'))
            .single()
            .execute()
        )
        emp = emp_result.data
        employee_name = f"{emp['FirstName']} {emp['LastName']}"
    except Exception:
        pass

    # Fetch appointment services with enrichment
    appt_services = []
    try:
        svc_rows = (
            supabase.table('appointment_service')
            .select('*')
            .eq('Appointment_AppointmentID', appt_id)
            .execute()
        )
        raw_services = svc_rows.data or []
        # Build service lookup
        svc_lookup = {}
        if raw_services:
            all_svc = (
                supabase.table('Service')
                .select('ServiceID, Service_Name, Cost')
                .execute()
            )
            svc_lookup = {
                r['ServiceID']: r for r in (all_svc.data or [])
            }
        for s in raw_services:
            svc = svc_lookup.get(s['Service_ServiceID'], {})
            s['_service_name'] = svc.get(
                'Service_Name', f"Service #{s['Service_ServiceID']}"
            )
            s['_service_cost'] = svc.get('Cost', 0)
        appt_services = raw_services
    except Exception:
        pass

    # Fetch appointment stock with enrichment
    appt_stock = []
    try:
        stk_rows = (
            supabase.table('Appointment_Stock')
            .select('*')
            .eq('Appointment_AppointmentID', appt_id)
            .execute()
        )
        raw_stock = stk_rows.data or []

        if raw_stock:
            sp_lookup = {}
            brand_lookup = {}
            try:
                sp_res = (
                    supabase.table('Spare_Parts')
                    .select('SP_id, SP_name')
                    .execute()
                )
                sp_lookup = {
                    r['SP_id']: r['SP_name'] for r in (sp_res.data or [])
                }
                br_res = (
                    supabase.table('Brand')
                    .select('Brand_ID, Brand_Name')
                    .execute()
                )
                brand_lookup = {
                    r['Brand_ID']: r['Brand_Name'] for r in (br_res.data or [])
                }
            except Exception:
                pass

            stk_lookup = {}
            try:
                all_stk = (
                    supabase.table('Stock')
                    .select('Stock_ID, Spare_Parts_SP_id, Brand_Brand_ID, Size')
                    .execute()
                )
                for s in (all_stk.data or []):
                    sp_name    = sp_lookup.get(s.get('Spare_Parts_SP_id'), 'Unknown Part')
                    brand_name = brand_lookup.get(s.get('Brand_Brand_ID'), 'Unknown Brand')
                    size       = s.get('Size') or ''
                    if size:
                        label = f"{sp_name} [{size}] \u2014 {brand_name}"
                    else:
                        label = f"{sp_name} \u2014 {brand_name}"
                    stk_lookup[s['Stock_ID']] = label
            except Exception:
                pass

            for s in raw_stock:
                s['_stock_label'] = stk_lookup.get(
                    s.get('Stock_Stock_ID'),
                    f"Stock #{s.get('Stock_Stock_ID')}"
                )
        appt_stock = raw_stock
    except Exception:
        pass

    appt_status = record.get('Status', '')
    is_locked   = appt_status in LOCKED_STATUSES

    # return render_template(
    #     'modules/appointment/view.html',
    #     record=record,
    #     appt_id=appt_id,
    #     bike_label=bike_label,
    #     employee_name=employee_name,
    #     appt_services=appt_services,
    #     appt_stock=appt_stock,
    #     appt_status=appt_status,
    #     is_locked=is_locked
    # )


        # Fetch linked payment (at most one per appointment due to UNIQUE constraint)
    appt_payment = None
    try:
        pay_result = (
            supabase.table('Payment')
            .select('*')
            .eq('Appointment_AppointmentID', appt_id)
            .execute()
        )
        pay_list = pay_result.data or []
        if pay_list:
            appt_payment = pay_list[0]
    except Exception:
        pass

    return render_template(
        'modules/appointment/view.html',
        record=record,
        appt_id=appt_id,
        bike_label=bike_label,
        employee_name=employee_name,
        appt_services=appt_services,
        appt_stock=appt_stock,
        appt_status=appt_status,
        is_locked=is_locked,
        appt_payment=appt_payment
    )


@bp.route('/delete/<int:appt_id>', methods=['POST'])
@login_required
def delete(appt_id):
    try:
        supabase.table('Appointment').delete().eq('AppointmentID', appt_id).execute()
        flash_success(f'Appointment #{appt_id} was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete Appointment #{appt_id} because it has an '
                f'associated payment record. '
                f'Remove the payment record first before deleting this appointment.'
            )
        else:
            flash_error(f'Could not delete appointment: {error_msg}')

    return redirect(url_for('appointment.index'))


# ------------------------=appointment_service routes =----------------------------------

@bp.route('/<int:appt_id>/services/add', methods=['GET', 'POST'])
@login_required
def add_service(appt_id):
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir

    if record.get('Status') in LOCKED_STATUSES:
        flash_error(
            f'Cannot add services to a {record.get("Status")} appointment.'
        )
        return redirect(url_for('appointment.view', appt_id=appt_id))

    # Get services already in this appointment
    existing_ids = set()
    try:
        existing = (
            supabase.table('appointment_service')
            .select('Service_ServiceID')
            .eq('Appointment_AppointmentID', appt_id)
            .execute()
        )
        existing_ids = {r['Service_ServiceID'] for r in (existing.data or [])}
    except Exception:
        pass

    # Build service options excluding already-added ones
    service_options = []
    try:
        all_svc = (
            supabase.table('Service')
            .select('ServiceID, Service_Name, Cost')
            .order('Service_Name')
            .execute()
        )
        service_options = [
            (
                r['ServiceID'],
                f"{r['Service_Name']} (Rs. {float(r['Cost']):.2f})"
            )
            for r in (all_svc.data or [])
            if r['ServiceID'] not in existing_ids
        ]
    except Exception:
        pass

    form_data = {}
    errors    = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        svc_id_raw = form_data.get('Service_ServiceID', '').strip()
        qty_raw    = form_data.get('Quantity', '').strip()

        svc_id = None
        if not svc_id_raw:
            errors['Service_ServiceID'] = 'Service is required.'
        else:
            try:
                svc_id = int(svc_id_raw)
            except ValueError:
                errors['Service_ServiceID'] = 'Please select a valid service.'

        qty = None
        if qty_raw:
            if not is_positive_integer(qty_raw) or int(qty_raw) < 1:
                errors['Quantity'] = 'Quantity must be a whole number of at least 1.'
            else:
                qty = int(qty_raw)

        if not errors:
            try:
                supabase.table('appointment_service').insert({
                    'Appointment_AppointmentID': appt_id,
                    'Service_ServiceID':         svc_id,
                    'Quantity':                  qty,
                }).execute()
                flash_success('Service was added to the appointment.')
                return redirect(url_for('appointment.view', appt_id=appt_id))
            except Exception as e:
                flash_error(f'Could not add service: {str(e)}')

    return render_template(
        'modules/appointment/service_form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        service_options=service_options,
        appt_id=appt_id,
        record=record
    )


@bp.route(
    '/<int:appt_id>/services/<int:service_id>/edit',
    methods=['GET', 'POST']
)
@login_required
def edit_service(appt_id, service_id):
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir

    if record.get('Status') in LOCKED_STATUSES:
        flash_error(
            f'Cannot edit services on a {record.get("Status")} appointment.'
        )
        return redirect(url_for('appointment.view', appt_id=appt_id))

    # Fetch existing appointment_service row
    try:
        row_result = (
            supabase.table('appointment_service')
            .select('*')
            .eq('Appointment_AppointmentID', appt_id)
            .eq('Service_ServiceID', service_id)
            .single()
            .execute()
        )
        row = row_result.data
    except Exception:
        flash_error('Service record not found.')
        return redirect(url_for('appointment.view', appt_id=appt_id))

    # Resolve service name for display
    service_name = f'Service #{service_id}'
    try:
        svc_res = (
            supabase.table('Service')
            .select('Service_Name')
            .eq('ServiceID', service_id)
            .single()
            .execute()
        )
        service_name = svc_res.data.get('Service_Name', service_name)
    except Exception:
        pass

    form_data = {'Quantity': row.get('Quantity', '') or ''}
    errors    = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        qty_raw   = form_data.get('Quantity', '').strip()

        qty = None
        if qty_raw:
            if not is_positive_integer(qty_raw) or int(qty_raw) < 1:
                errors['Quantity'] = 'Quantity must be a whole number of at least 1.'
            else:
                qty = int(qty_raw)

        if not errors:
            try:
                supabase.table('appointment_service').update(
                    {'Quantity': qty}
                ).eq('Appointment_AppointmentID', appt_id).eq(
                    'Service_ServiceID', service_id
                ).execute()
                flash_success(f'Service quantity updated.')
                return redirect(url_for('appointment.view', appt_id=appt_id))
            except Exception as e:
                flash_error(f'Could not update service: {str(e)}')

    return render_template(
        'modules/appointment/service_form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        service_options=[],
        service_name=service_name,
        appt_id=appt_id,
        record=record
    )


@bp.route(
    '/<int:appt_id>/services/<int:service_id>/delete',
    methods=['POST']
)
@login_required
def delete_service(appt_id, service_id):
    try:
        supabase.table('appointment_service').delete(
        ).eq('Appointment_AppointmentID', appt_id).eq(
            'Service_ServiceID', service_id
        ).execute()
        flash_success('Service was removed from the appointment.')
    except Exception as e:
        flash_error(f'Could not remove service: {str(e)}')

    return redirect(url_for('appointment.view', appt_id=appt_id))


# --------------------------------Appointment_Stock routes ------------------------------

def _build_stock_options(exclude_ids=None):
    """Build enriched Stock dropdown options for appointment stock forms."""
    exclude_ids = exclude_ids or set()
    stock_options = []

    sp_lookup    = {}
    brand_lookup = {}
    try:
        sp_res = supabase.table('Spare_Parts').select('SP_id, SP_name').execute()
        sp_lookup = {r['SP_id']: r['SP_name'] for r in (sp_res.data or [])}
        br_res = supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
        brand_lookup = {r['Brand_ID']: r['Brand_Name'] for r in (br_res.data or [])}
    except Exception:
        pass

    try:
        stk_res = (
            supabase.table('Stock')
            .select('Stock_ID, Spare_Parts_SP_id, Brand_Brand_ID, Size, QOH')
            .order('Stock_ID')
            .execute()
        )
        for s in (stk_res.data or []):
            if s['Stock_ID'] in exclude_ids:
                continue
            sp_name    = sp_lookup.get(s.get('Spare_Parts_SP_id'), 'Unknown Part')
            brand_name = brand_lookup.get(s.get('Brand_Brand_ID'), 'Unknown Brand')
            size       = s.get('Size') or ''
            if size:
                label = f"{sp_name} [{size}] \u2014 {brand_name} (QOH: {s.get('QOH', 0)})"
            else:
                label = f"{sp_name} \u2014 {brand_name} (QOH: {s.get('QOH', 0)})"
            stock_options.append((s['Stock_ID'], label))
    except Exception:
        pass

    return stock_options


@bp.route('/<int:appt_id>/stock/add', methods=['GET', 'POST'])
@login_required
def add_stock(appt_id):
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir

    if record.get('Status') in LOCKED_STATUSES:
        flash_error(
            f'Cannot add stock to a {record.get("Status")} appointment.'
        )
        return redirect(url_for('appointment.view', appt_id=appt_id))

    # Get stock already in this appointment
    existing_stock_ids = set()
    try:
        existing = (
            supabase.table('Appointment_Stock')
            .select('Stock_Stock_ID')
            .eq('Appointment_AppointmentID', appt_id)
            .execute()
        )
        existing_stock_ids = {
            r['Stock_Stock_ID'] for r in (existing.data or [])
        }
    except Exception:
        pass

    stock_options = _build_stock_options(exclude_ids=existing_stock_ids)
    form_data     = {}
    errors        = {}

    if request.method == 'POST':
        form_data    = request.form.to_dict()
        stk_id_raw   = form_data.get('Stock_Stock_ID', '').strip()
        qty_raw      = form_data.get('Quantity', '').strip()

        stk_id = None
        if not stk_id_raw:
            errors['Stock_Stock_ID'] = 'Stock item is required.'
        else:
            try:
                stk_id = int(stk_id_raw)
            except ValueError:
                errors['Stock_Stock_ID'] = 'Please select a valid stock item.'

        qty = None
        if not qty_raw:
            errors['Quantity'] = 'Quantity is required.'
        elif not is_positive_integer(qty_raw) or int(qty_raw) < 1:
            errors['Quantity'] = 'Quantity must be a whole number of at least 1.'
        else:
            qty = int(qty_raw)

        if not errors:
            try:
                supabase.table('Appointment_Stock').insert({
                    'Appointment_AppointmentID': appt_id,
                    'Stock_Stock_ID':            stk_id,
                    'Quantity':                  qty,
                }).execute()
                flash_success('Stock item was added to the appointment.')
                return redirect(url_for('appointment.view', appt_id=appt_id))
            except Exception as e:
                flash_error(f'Could not add stock item: {str(e)}')

    return render_template(
        'modules/appointment/stock_form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        stock_options=stock_options,
        appt_id=appt_id,
        record=record
    )


@bp.route(
    '/<int:appt_id>/stock/<int:stock_id>/edit',
    methods=['GET', 'POST']
)
@login_required
def edit_stock(appt_id, stock_id):
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir

    if record.get('Status') in LOCKED_STATUSES:
        flash_error(
            f'Cannot edit stock on a {record.get("Status")} appointment.'
        )
        return redirect(url_for('appointment.view', appt_id=appt_id))

    try:
        row_result = (
            supabase.table('Appointment_Stock')
            .select('*')
            .eq('Appointment_AppointmentID', appt_id)
            .eq('Stock_Stock_ID', stock_id)
            .single()
            .execute()
        )
        row = row_result.data
    except Exception:
        flash_error('Stock record not found.')
        return redirect(url_for('appointment.view', appt_id=appt_id))

    # Resolve stock label for display
    stock_label = f'Stock #{stock_id}'
    try:
        stk_res = (
            supabase.table('Stock')
            .select('Spare_Parts_SP_id, Brand_Brand_ID, Size')
            .eq('Stock_ID', stock_id)
            .single()
            .execute()
        )
        stk = stk_res.data
        sp_res = (
            supabase.table('Spare_Parts')
            .select('SP_name')
            .eq('SP_id', stk.get('Spare_Parts_SP_id'))
            .single()
            .execute()
        )
        br_res = (
            supabase.table('Brand')
            .select('Brand_Name')
            .eq('Brand_ID', stk.get('Brand_Brand_ID'))
            .single()
            .execute()
        )
        sp_name    = sp_res.data.get('SP_name', 'Unknown')
        brand_name = br_res.data.get('Brand_Name', 'Unknown')
        size       = stk.get('Size') or ''
        stock_label = (
            f"{sp_name} [{size}] \u2014 {brand_name}"
            if size else f"{sp_name} \u2014 {brand_name}"
        )
    except Exception:
        pass

    form_data = {'Quantity': str(row.get('Quantity', ''))}
    errors    = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        qty_raw   = form_data.get('Quantity', '').strip()

        qty = None
        if not qty_raw:
            errors['Quantity'] = 'Quantity is required.'
        elif not is_positive_integer(qty_raw) or int(qty_raw) < 1:
            errors['Quantity'] = 'Quantity must be a whole number of at least 1.'
        else:
            qty = int(qty_raw)

        if not errors:
            try:
                supabase.table('Appointment_Stock').update(
                    {'Quantity': qty}
                ).eq('Appointment_AppointmentID', appt_id).eq(
                    'Stock_Stock_ID', stock_id
                ).execute()
                flash_success('Stock quantity updated.')
                return redirect(url_for('appointment.view', appt_id=appt_id))
            except Exception as e:
                flash_error(f'Could not update stock quantity: {str(e)}')

    return render_template(
        'modules/appointment/stock_form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        stock_options=[],
        stock_label=stock_label,
        appt_id=appt_id,
        record=record
    )


@bp.route(
    '/<int:appt_id>/stock/<int:stock_id>/delete',
    methods=['POST']
)
@login_required
def delete_stock(appt_id, stock_id):
    try:
        supabase.table('Appointment_Stock').delete(
        ).eq('Appointment_AppointmentID', appt_id).eq(
            'Stock_Stock_ID', stock_id
        ).execute()
        flash_success('Stock item was removed from the appointment.')
    except Exception as e:
        flash_error(f'Could not remove stock item: {str(e)}')

    return redirect(url_for('appointment.view', appt_id=appt_id))