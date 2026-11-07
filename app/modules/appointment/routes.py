import re
from flask import render_template, request, redirect, url_for
from app.modules.appointment import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields, is_positive_integer
from datetime import date as date_type
from app.utils.text import norm
from app.modules.payment.routes import PAYABLE_APPOINTMENT_STATUSES


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
LOCKED_STATUSES = ('Completed', 'Cancelled', 'No Show')

# Allowed status changes (DEC-12). Used by the Edit form (only these targets
# are offered) and enforced on every save, confirm and cancel.
ALLOWED_TRANSITIONS = {
    'Pending':     ('Confirmed', 'Cancelled'),
    'Confirmed':   ('In Progress', 'Completed', 'Cancelled', 'No Show'),
    'In Progress': ('Completed', 'Cancelled'),
    'Completed':   (),
    'Cancelled':   (),
    'No Show':     (),
}
TRANSITION_REFUSED_MSG = 'This status change is not allowed.'

# Services, parts (stock) and their changes only once confirmed (DEC-7).
LINE_EDIT_STATUSES = ('Confirmed', 'In Progress')
CONFIRM_FIRST_MSG = 'Confirm the appointment first.'

# Online bookings (Task 44) are created Pending with no employee. An employee must be
# assigned before the appointment is confirmed or moves further; Pending and Cancelled
# appointments may stay unassigned.
EMPLOYEE_REQUIRED_STATUSES = ('Confirmed', 'In Progress', 'Completed', 'No Show')
EMPLOYEE_REQUIRED_MSG = 'Assign an employee before confirming or progressing this appointment.'
UNASSIGNED_LABEL = 'Unassigned'
APPOINTMENT_CHANGED_MSG = 'This appointment has changed. Refresh and try again.'

# List filters (whitelisted).
FILTER_NEEDS_CONFIRMATION = 'needs_confirmation'
LIST_FILTERS = {FILTER_NEEDS_CONFIRMATION: 'Needs confirmation'}


#  Helpers -------------------------------

def employee_required(status):
    """True when an appointment with this status must have an employee."""
    return status in EMPLOYEE_REQUIRED_STATUSES


def can_transition(current, target):
    """True when the status may change from current to target (unchanged is always allowed)."""
    return target == current or target in ALLOWED_TRANSITIONS.get(current, ())


def status_choices(current):
    """Edit form options: the current status first, then the allowed targets."""
    allowed = set(ALLOWED_TRANSITIONS.get(current, ()))
    return [(v, l) for v, l in STATUS_OPTIONS if v == current or v in allowed]


def _lines_refusal(record):
    """Why services or parts of this appointment cannot be changed, or None."""
    status = record.get('Status')
    if status in LINE_EDIT_STATUSES:
        return None
    if status == 'Pending':
        return CONFIRM_FIRST_MSG
    return f'Services and parts cannot be changed on a {status} appointment.'


def needs_confirmation(appt):
    """A booking still waiting for the workshop: Pending with no employee."""
    return appt.get('Status') == 'Pending' and not appt.get('Employee_EmployeeID')


def _employee_names(employee_ids):
    """{EmployeeID: 'First Last'} for the given ids; None ids are skipped, never queried."""
    ids = sorted({i for i in employee_ids if i is not None})
    if not ids:
        return {}
    try:
        result = (
            supabase.table('Employee')
            .select('EmployeeID, FirstName, LastName')
            .in_('EmployeeID', ids)
            .execute()
        )
    except Exception:
        return {}
    return {
        r['EmployeeID']: f"{r['FirstName']} {r['LastName']}"
        for r in (result.data or [])
    }


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


def _chunks(ids, size=100):
    ids = sorted({i for i in ids if i is not None})
    for start in range(0, len(ids), size):
        yield ids[start:start + size]


def _rows_in(table, columns, key, ids):
    """Rows of table whose key is in ids, with one query per 100 ids; errors give no rows."""
    rows = []
    for chunk in _chunks(ids):
        try:
            rows += supabase.table(table).select(columns).in_(key, chunk).execute().data or []
        except Exception:
            continue
    return rows


def _bike_labels(bike_ids=None):
    """
    {BikeID: {'label': 'REG, Brand Model (Year)', 'customer': 'First Last' or None,
    'full': label plus ', Customer'}} with batched lookups (Customer_bike, Model,
    Brand, Customer), null-safe. bike_ids=None loads every bike (create dropdown).
    """
    try:
        query = supabase.table('Customer_bike').select(
            'BikeID, RegistrationNumber, Year, Model_Model_No, Customer_CustomerID')
        if bike_ids is None:
            bikes = query.order('RegistrationNumber').execute().data or []
        else:
            bikes = []
            for chunk in _chunks(bike_ids):
                bikes += supabase.table('Customer_bike').select(
                    'BikeID, RegistrationNumber, Year, Model_Model_No, Customer_CustomerID'
                ).in_('BikeID', chunk).execute().data or []
    except Exception:
        return {}

    models = {m['Model_No']: m for m in _rows_in(
        'Model', 'Model_No, Description, Brand_Brand_ID', 'Model_No', (b.get('Model_Model_No') for b in bikes))}
    brands = {r['Brand_ID']: r.get('Brand_Name') for r in _rows_in(
        'Brand', 'Brand_ID, Brand_Name', 'Brand_ID', (m.get('Brand_Brand_ID') for m in models.values()))}
    customers = {r['CustomerID']: f"{r.get('FirstName') or ''} {r.get('LastName') or ''}".strip() or None
                 for r in _rows_in('Customer', 'CustomerID, FirstName, LastName', 'CustomerID',
                                   (b.get('Customer_CustomerID') for b in bikes))}

    labels = {}
    for b in bikes:
        model = models.get(b.get('Model_Model_No')) or {}
        name = ' '.join(x for x in (brands.get(model.get('Brand_Brand_ID')), model.get('Description')) if x)
        if b.get('Year'):
            name = f"{name} ({b['Year']})" if name else f"({b['Year']})"
        label = ', '.join(x for x in (b.get('RegistrationNumber') or 'No registration', name) if x)
        customer = customers.get(b.get('Customer_CustomerID'))
        labels[b['BikeID']] = {
            'label': label,
            'customer': customer,
            'full': f'{label}, {customer}' if customer else label,
        }
    return labels


def _employee_options():
    """(EmployeeID, 'First Last') ordered by last name."""
    try:
        emp_result = (
            supabase.table('Employee')
            .select('EmployeeID, FirstName, LastName')
            .order('LastName')
            .execute()
        )
    except Exception:
        return []
    return [
        (r['EmployeeID'], f"{r['FirstName']} {r['LastName']}")
        for r in (emp_result.data or [])
    ]


def _get_form_options():
    """
    Customer bike and employee dropdown options for the appointment forms.
    Bike label: 'REG, Brand Model (Year), Customer'.
    """
    bike_options = [(bid, info['full']) for bid, info in _bike_labels().items()]
    return bike_options, _employee_options()


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
    bike_lookup = {bid: info['full'] for bid, info in
                   _bike_labels(a.get('Customer_bike_BikeID') for a in all_records).items()}

    emp_lookup = _employee_names(a.get('Employee_EmployeeID') for a in all_records)

    for appt in all_records:
        appt['_bike_label'] = bike_lookup.get(
            appt.get('Customer_bike_BikeID'), '—'
        )
        emp_id = appt.get('Employee_EmployeeID')
        appt['_unassigned'] = emp_id is None
        appt['_employee_name'] = (
            UNASSIGNED_LABEL if emp_id is None else emp_lookup.get(emp_id, '-')
        )
        appt['_needs_confirmation'] = needs_confirmation(appt)

    return all_records


# ----- Appointment CRUD routes -------------------------=-

@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    list_filter = request.args.get('filter', '').strip()
    if list_filter not in LIST_FILTERS:
        list_filter = ''

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
            if q in norm(r.get('_bike_label'))
            or q in norm(r.get('_employee_name'))
            or q in norm(r.get('AppointmentType'))
            or q in norm(r.get('Status'))
            or q in str(r.get('Appointment_Date', '') or '')
        ]

    if list_filter == FILTER_NEEDS_CONFIRMATION:
        all_records = [r for r in all_records if r['_needs_confirmation']]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/appointment/list.html',
        pagination=pagination,
        search_query=search_query,
        list_filter=list_filter,
        list_filters=LIST_FILTERS,
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

    previous_status = record.get('Status')
    # A Pending booking is confirmed (or cancelled) from the panel on its view page,
    # so no path saves it as "updated" without confirming it (ISS-13).
    if previous_status == 'Pending':
        return redirect(url_for('appointment.view', appt_id=appt_id, _anchor='confirm'))
    if previous_status in LOCKED_STATUSES:
        flash_error(f'A {previous_status} appointment cannot be edited.')
        return redirect(url_for('appointment.view', appt_id=appt_id))

    errors    = {}
    form_data = record.copy()
    # Truncate time for HTML time input pre-population
    form_data['Appointment_time'] = _truncate_time(
        form_data.get('Appointment_time', '')
    )
    employee_options = _employee_options()
    bike_id = record.get('Customer_bike_BikeID')     # locked on edit (DEC-9)
    bike_label = _bike_labels([bike_id]).get(bike_id, {}).get('full', '-')

    if request.method == 'POST':
        form_data = request.form.to_dict()

        emp_id_raw   = form_data.get('Employee_EmployeeID', '').strip()
        date_raw     = form_data.get('Appointment_Date', '').strip()
        time_raw     = form_data.get('Appointment_time', '').strip()
        appt_type    = form_data.get('AppointmentType', '').strip()
        status_value = form_data.get('Status', '').strip()

        emp_id = None
        if emp_id_raw:
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
        elif not can_transition(previous_status, status_value):
            errors['Status'] = TRANSITION_REFUSED_MSG

        # Online bookings start unassigned: an employee is optional only while the
        # appointment is Pending or Cancelled (server-side rule, not just the form).
        if (employee_required(status_value) and emp_id is None
                and 'Employee_EmployeeID' not in errors):
            errors['Employee_EmployeeID'] = EMPLOYEE_REQUIRED_MSG

        # The customer may have cancelled the booking since this form was opened.
        expected_status = form_data.get('expected_status', '').strip()
        if not errors and expected_status and expected_status != previous_status:
            flash_error(APPOINTMENT_CHANGED_MSG)
            return redirect(url_for('appointment.view', appt_id=appt_id))

        if not errors:
            try:
                updated = supabase.table('Appointment').update({
                    'Customer_bike_BikeID': bike_id,
                    'Employee_EmployeeID':  emp_id,
                    'Appointment_Date':     appt_date,
                    'Appointment_time':     appt_time,
                    'AppointmentType':      appt_type,
                    'Status':               status_value,
                }).eq('AppointmentID', appt_id).eq('Status', previous_status).execute()

                if not updated.data:
                    flash_error(APPOINTMENT_CHANGED_MSG)
                    return redirect(url_for('appointment.view', appt_id=appt_id))

                # Deduct used stock exactly once:  only on the transition  into Completed.
                #  Re-saving an already-Completed appointment  will not trigger this again, since previous_status will  already be 'Completed'.
                if status_value == 'Completed' and previous_status != 'Completed':
                    _deduct_stock_for_appointment(appt_id)
                    flash_success(
                        f'Appointment #{appt_id} was marked Completed and '
                        f'stock quantities have been updated.'
                    )
                else:
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
        bike_options=[],
        bike_label=bike_label,
        employee_options=employee_options,
        type_options=APPOINTMENT_TYPE_OPTIONS,
        status_options=status_choices(previous_status),
        employee_required_statuses=EMPLOYEE_REQUIRED_STATUSES,
    )


@bp.route('/view/<int:appt_id>')
@login_required
def view(appt_id):
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir
    return _render_view(appt_id, record)


def _confirm_defaults(record):
    return {
        'Employee_EmployeeID': record.get('Employee_EmployeeID') or '',
        'AppointmentType':     record.get('AppointmentType') or '',
        'Appointment_Date':    record.get('Appointment_Date') or '',
        'Appointment_time':    _truncate_time(record.get('Appointment_time') or ''),
    }


@bp.route('/<int:appt_id>/confirm', methods=['POST'])
@login_required
def confirm(appt_id):
    """
    Confirm a Pending booking (ISS-13): employee required, type, date and time
    editable, bike unchanged. One conditional update (expected status Pending).
    """
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir
    if record.get('Status') != 'Pending':
        flash_error(APPOINTMENT_CHANGED_MSG)
        return redirect(url_for('appointment.view', appt_id=appt_id))

    form = request.form.to_dict()
    errors = {}

    emp_id, employee_name = None, None
    emp_raw = (form.get('Employee_EmployeeID') or '').strip()
    if not emp_raw:
        errors['Employee_EmployeeID'] = 'Choose the employee who will handle this appointment.'
    else:
        try:
            emp_id = int(emp_raw)
        except ValueError:
            errors['Employee_EmployeeID'] = 'Please select a valid employee.'
        else:
            employee_name = _employee_names([emp_id]).get(emp_id)
            if not employee_name:
                errors['Employee_EmployeeID'] = 'Please select a valid employee.'

    appt_type = (form.get('AppointmentType') or '').strip()
    if appt_type not in VALID_TYPES:
        errors['AppointmentType'] = 'Please select a valid appointment type.'
    appt_date, date_err = _validate_date(form.get('Appointment_Date'), 'Appointment Date')
    if date_err:
        errors['Appointment_Date'] = date_err
    appt_time, time_err = _validate_time(form.get('Appointment_time'))
    if time_err:
        errors['Appointment_time'] = time_err

    if errors:
        return _render_view(appt_id, record, confirm_form=form, confirm_errors=errors)

    try:
        updated = supabase.table('Appointment').update({
            'Employee_EmployeeID': emp_id,
            'AppointmentType':     appt_type,
            'Appointment_Date':    appt_date,
            'Appointment_time':    appt_time,
            'Status':              'Confirmed',
        }).eq('AppointmentID', appt_id).eq('Status', 'Pending').execute()
    except Exception as e:
        flash_error(f'Could not confirm the appointment: {str(e)}')
        return _render_view(appt_id, record, confirm_form=form, confirm_errors={})
    if not updated.data:
        flash_error(APPOINTMENT_CHANGED_MSG)          # e.g. the customer cancelled meanwhile
        return redirect(url_for('appointment.view', appt_id=appt_id))
    flash_success(f'Appointment #{appt_id} confirmed with {employee_name}.')
    return redirect(url_for('appointment.view', appt_id=appt_id))


@bp.route('/<int:appt_id>/cancel', methods=['POST'])
@login_required
def cancel(appt_id):
    """Cancel an appointment when the transition table allows it (no employee needed)."""
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir
    current = record.get('Status')
    if 'Cancelled' not in ALLOWED_TRANSITIONS.get(current, ()):
        flash_error(TRANSITION_REFUSED_MSG)
        return redirect(url_for('appointment.view', appt_id=appt_id))
    try:
        updated = (
            supabase.table('Appointment').update({'Status': 'Cancelled'})
            .eq('AppointmentID', appt_id).eq('Status', current).execute()
        )
    except Exception as e:
        flash_error(f'Could not cancel the appointment: {str(e)}')
        return redirect(url_for('appointment.view', appt_id=appt_id))
    if not updated.data:
        flash_error(APPOINTMENT_CHANGED_MSG)
        return redirect(url_for('appointment.view', appt_id=appt_id))
    flash_success(f'Appointment #{appt_id} was cancelled.')
    return redirect(url_for('appointment.view', appt_id=appt_id))


def _render_view(appt_id, record, confirm_form=None, confirm_errors=None):
    bike_id = record.get('Customer_bike_BikeID')
    bike_label = _bike_labels([bike_id]).get(bike_id, {}).get('full', '-')

    # Resolve employee name (online bookings start unassigned)
    emp_id = record.get('Employee_EmployeeID')
    if emp_id is None:
        employee_name = UNASSIGNED_LABEL
    else:
        employee_name = _employee_names([emp_id]).get(emp_id, '-')

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
                    .select('Stock_ID, Spare_Parts_SP_id, Brand_Brand_ID, Size, S_Price')
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
                    stk_lookup[s['Stock_ID']] = {
                        'label': label,
                        'price': float(s.get('S_Price') or 0),
                    }
            except Exception:
                pass

            for s in raw_stock:
                info = stk_lookup.get(s.get('Stock_Stock_ID'), {})
                if isinstance(info, dict):
                    s['_stock_label'] = info.get(
                        'label', f"Stock #{s.get('Stock_Stock_ID')}"
                    )
                    s['_stock_price'] = info.get('price', 0.0)
                else:
                    s['_stock_label'] = f"Stock #{s.get('Stock_Stock_ID')}"
                    s['_stock_price'] = 0.0
        appt_stock = raw_stock
    except Exception:
        pass

    appt_status = record.get('Status', '')
    is_locked   = appt_status in LOCKED_STATUSES
    lines_refusal = _lines_refusal(record)

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


    # Calculate appointment estimated total from saved services and stock
    service_total = sum(
        float(svc.get('_service_cost') or 0) * int(svc.get('Quantity') or 1)
        for svc in appt_services
    )
    stock_total = sum(
        float(stk.get('_stock_price') or 0) * int(stk.get('Quantity') or 0)
        for stk in appt_stock
    )
    appt_total = service_total + stock_total

    # Fetch ALL payments linked to this appointment. The uniqueness constraint that previously limited an appointment to one payment
    # only has been removed so that appointments can be paid in partial/deposit instalments the same
    # way Sales already work.
    appt_payments = []
    try:
        pay_result = (
            supabase.table('Payment')
            .select('*')
            .eq('Appointment_AppointmentID', appt_id)
            .order('PaymentID')
            .execute()
        )
        appt_payments = pay_result.data or []
    except Exception:
        pass

    appt_total_paid = sum(float(p.get('AmountPaid') or 0) for p in appt_payments)
    appt_remaining  = max(0.0, appt_total - appt_total_paid)

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
        lines_editable=lines_refusal is None,
        lines_refusal=lines_refusal,
        can_pay=appt_status in PAYABLE_APPOINTMENT_STATUSES,
        can_cancel='Cancelled' in ALLOWED_TRANSITIONS.get(appt_status, ()),
        can_edit=appt_status in ('Confirmed', 'In Progress'),
        is_pending=appt_status == 'Pending',
        confirm_form=confirm_form or _confirm_defaults(record),
        confirm_errors=confirm_errors or {},
        employee_options=_employee_options() if appt_status == 'Pending' else [],
        type_options=APPOINTMENT_TYPE_OPTIONS,
        is_unassigned=emp_id is None,
        needs_confirmation=needs_confirmation(record),
        appt_payments=appt_payments,
        appt_total_paid=appt_total_paid,
        appt_remaining=appt_remaining,
        service_total=service_total,
        stock_total=stock_total,
        appt_total=appt_total
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

    refusal = _lines_refusal(record)
    if refusal:
        flash_error(refusal)
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

    refusal = _lines_refusal(record)
    if refusal:
        flash_error(refusal)
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
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir
    refusal = _lines_refusal(record)
    if refusal:
        flash_error(refusal)
        return redirect(url_for('appointment.view', appt_id=appt_id))
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

    refusal = _lines_refusal(record)
    if refusal:
        flash_error(refusal)
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

def _deduct_stock_for_appointment(appt_id):
    """
    Decrease Stock.QOH for every stock item used in this appointment.
    Called exactly once — only at the moment an appointment's Status
    transitions INTO 'Completed' — so inventory reflects parts actually
    consumed. Appointment_Stock rows are locked once Completed, so this
    cannot double-fire on a later re-save of the same appointment.
    """
    try:
        used_rows = (
            supabase.table('Appointment_Stock')
            .select('Stock_Stock_ID, Quantity')
            .eq('Appointment_AppointmentID', appt_id)
            .execute()
        )
        for row in (used_rows.data or []):
            stock_id = row.get('Stock_Stock_ID')
            qty_used = int(row.get('Quantity') or 0)
            if not stock_id or qty_used <= 0:
                continue
            try:
                current = (
                    supabase.table('Stock')
                    .select('QOH')
                    .eq('Stock_ID', stock_id)
                    .single()
                    .execute()
                )
                current_qoh = int(current.data.get('QOH') or 0)
                new_qoh = max(0, current_qoh - qty_used)
                supabase.table('Stock').update(
                    {'QOH': new_qoh}
                ).eq('Stock_ID', stock_id).execute()
            except Exception:
                continue
    except Exception:
        pass



@bp.route(
    '/<int:appt_id>/stock/<int:stock_id>/edit',
    methods=['GET', 'POST']
)
@login_required
def edit_stock(appt_id, stock_id):
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir

    refusal = _lines_refusal(record)
    if refusal:
        flash_error(refusal)
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
    record, redir = _get_appointment_or_redirect(appt_id)
    if redir:
        return redir
    refusal = _lines_refusal(record)
    if refusal:
        flash_error(refusal)
        return redirect(url_for('appointment.view', appt_id=appt_id))
    try:
        supabase.table('Appointment_Stock').delete(
        ).eq('Appointment_AppointmentID', appt_id).eq(
            'Stock_Stock_ID', stock_id
        ).execute()
        flash_success('Stock item was removed from the appointment.')
    except Exception as e:
        flash_error(f'Could not remove stock item: {str(e)}')

    return redirect(url_for('appointment.view', appt_id=appt_id))