from flask import render_template, request, redirect, url_for
from app.modules.payment import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import is_positive_number
from datetime import date as date_type


# -- Predefined option lists ----------------------------------------------------

PAYMENT_METHOD_OPTIONS = [
    ('Cash',          'Cash'),
    ('Card',          'Card'),
    ('Bank Transfer', 'Bank Transfer'),
    ('Online',        'Online'),
]

PAYMENT_TYPE_OPTIONS = [
    ('Full Payment', 'Full Payment'),
    ('Deposit',      'Deposit'),
    ('Instalment',   'Instalment'),
]

VALID_METHODS = [v for v, _ in PAYMENT_METHOD_OPTIONS]
VALID_TYPES   = [v for v, _ in PAYMENT_TYPE_OPTIONS]


# --------Helpers ------------------------------------------------------------------

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


def _get_sale_options():
    """All Sales as (SaleID, enriched label) tuples ordered by SaleID desc."""
    options         = []
    customer_lookup = {}

    try:
        c = (
            supabase.table('Customer')
            .select('CustomerID, FirstName, LastName')
            .execute()
        )
        customer_lookup = {
            r['CustomerID']: f"{r['FirstName']} {r['LastName']}"
            for r in (c.data or [])
        }
    except Exception:
        pass

    try:
        sales = (
            supabase.table('Sale')
            .select('SaleID, Customer_CustomerID, SaleDate')
            .order('SaleID', desc=True)
            .execute()
        )
        for s in (sales.data or []):
            cname = customer_lookup.get(s.get('Customer_CustomerID'), 'Unknown')
            label = f"SALE-{s['SaleID']} \u2014 {cname} ({s.get('SaleDate', '?')})"
            options.append((s['SaleID'], label))
    except Exception:
        pass

    return options


def _get_appointment_options(exclude_appt_id=None):
    """
    Appointments that do not already have a payment, as enriched tuples.
    On Edit, exclude_appt_id keeps the currently linked appointment in the list.
    """
    options = []

    # IDs of appointments that already have a payment
    paid_appt_ids = set()
    try:
        paid = (
            supabase.table('Payment')
            .select('Appointment_AppointmentID')
            .execute()
        )
        paid_appt_ids = {
            r['Appointment_AppointmentID']
            for r in (paid.data or [])
            if r.get('Appointment_AppointmentID') is not None
        }
        if exclude_appt_id is not None:
            paid_appt_ids.discard(exclude_appt_id)
    except Exception:
        pass

    # Bike registration lookup for appointment labels
    bike_lookup = {}
    try:
        bikes = (
            supabase.table('Customer_bike')
            .select('BikeID, RegistrationNumber')
            .execute()
        )
        bike_lookup = {
            r['BikeID']: r['RegistrationNumber']
            for r in (bikes.data or [])
        }
    except Exception:
        pass

    try:
        appts = (
            supabase.table('Appointment')
            .select('AppointmentID, Customer_bike_BikeID, Appointment_Date')
            .order('AppointmentID', desc=True)
            .execute()
        )
        for a in (appts.data or []):
            if a['AppointmentID'] in paid_appt_ids:
                continue
            reg   = bike_lookup.get(a.get('Customer_bike_BikeID'), 'Unknown Bike')
            label = (
                f"APPT-#{a['AppointmentID']} \u2014 "
                f"{reg} ({a.get('Appointment_Date', '?')})"
            )
            options.append((a['AppointmentID'], label))
    except Exception:
        pass

    return options


def _enrich_payments(all_records):
    """Resolve Sale and Appointment reference labels for list display."""
    customer_lookup = {}
    try:
        c = (
            supabase.table('Customer')
            .select('CustomerID, FirstName, LastName')
            .execute()
        )
        customer_lookup = {
            r['CustomerID']: f"{r['FirstName']} {r['LastName']}"
            for r in (c.data or [])
        }
    except Exception:
        pass

    sale_lookup = {}
    try:
        sales = (
            supabase.table('Sale')
            .select('SaleID, Customer_CustomerID')
            .execute()
        )
        for s in (sales.data or []):
            cname = customer_lookup.get(s.get('Customer_CustomerID'), 'Unknown')
            sale_lookup[s['SaleID']] = f"SALE-{s['SaleID']} \u2014 {cname}"
    except Exception:
        pass

    bike_lookup = {}
    try:
        bikes = (
            supabase.table('Customer_bike')
            .select('BikeID, RegistrationNumber')
            .execute()
        )
        bike_lookup = {
            r['BikeID']: r['RegistrationNumber']
            for r in (bikes.data or [])
        }
    except Exception:
        pass

    appt_lookup = {}
    try:
        appts = (
            supabase.table('Appointment')
            .select('AppointmentID, Customer_bike_BikeID, Appointment_Date')
            .execute()
        )
        for a in (appts.data or []):
            reg = bike_lookup.get(a.get('Customer_bike_BikeID'), 'Unknown')
            appt_lookup[a['AppointmentID']] = (
                f"APPT-#{a['AppointmentID']} \u2014 "
                f"{reg} ({a.get('Appointment_Date', '?')})"
            )
    except Exception:
        pass

    for pay in all_records:
        sale_id = pay.get('Sale_SaleID')
        appt_id = pay.get('Appointment_AppointmentID')

        if sale_id:
            pay['_reference_type']  = 'Sale'
            pay['_reference_label'] = sale_lookup.get(sale_id, f'SALE-{sale_id}')
        elif appt_id:
            pay['_reference_type']  = 'Appointment'
            pay['_reference_label'] = appt_lookup.get(appt_id, f'APPT-#{appt_id}')
        else:
            pay['_reference_type']  = '—'
            pay['_reference_label'] = '—'

    return all_records


def _validate_form(form_data, current_appt_id=None):
    """
    Validate all payment form fields.
    Returns (errors, parsed) where parsed contains correctly typed values.
    current_appt_id is passed on Edit to allow the same appointment to remain linked.
    """
    errors = {}
    parsed = {}

    reference_type = form_data.get('reference_type', 'sale')
    parsed['reference_type'] = reference_type

    sale_id_raw = form_data.get('Sale_SaleID', '').strip()
    appt_id_raw = form_data.get('Appointment_AppointmentID', '').strip()

    sale_id = None
    appt_id = None

    if reference_type == 'sale':
        if not sale_id_raw:
            errors['Sale_SaleID'] = 'Please select a sale.'
        else:
            try:
                sale_id = int(sale_id_raw)
                parsed['Sale_SaleID'] = sale_id
                parsed['Appointment_AppointmentID'] = None
            except ValueError:
                errors['Sale_SaleID'] = 'Please select a valid sale.'
    else:
        if not appt_id_raw:
            errors['Appointment_AppointmentID'] = 'Please select an appointment.'
        else:
            try:
                appt_id = int(appt_id_raw)
                # Check for duplicate payment on this appointment
                if appt_id != current_appt_id:
                    try:
                        existing = (
                            supabase.table('Payment')
                            .select('PaymentID')
                            .eq('Appointment_AppointmentID', appt_id)
                            .execute()
                        )
                        if existing.data:
                            errors['Appointment_AppointmentID'] = (
                                'This appointment already has a payment record. '
                                'Each appointment can only have one payment.'
                            )
                    except Exception:
                        pass
                if 'Appointment_AppointmentID' not in errors:
                    parsed['Appointment_AppointmentID'] = appt_id
                    parsed['Sale_SaleID'] = None
            except ValueError:
                errors['Appointment_AppointmentID'] = 'Please select a valid appointment.'

    # PaymentDate
    date_raw = form_data.get('PaymentDate', '').strip()
    pay_date, date_err = _validate_date(date_raw, 'Payment Date')
    if date_err:
        errors['PaymentDate'] = date_err
    else:
        parsed['PaymentDate'] = pay_date

    # AmountPaid
    amount_raw = form_data.get('AmountPaid', '').strip()
    if not amount_raw:
        errors['AmountPaid'] = 'Amount paid is required.'
    elif not is_positive_number(amount_raw):
        errors['AmountPaid'] = 'Amount must be a valid number of 0 or more.'
    else:
        parsed['AmountPaid'] = float(amount_raw)

    # PaymentMethod
    method_value = form_data.get('PaymentMethod', '').strip()
    if not method_value:
        errors['PaymentMethod'] = 'Payment method is required.'
    elif method_value not in VALID_METHODS:
        errors['PaymentMethod'] = 'Please select a valid payment method.'
    else:
        parsed['PaymentMethod'] = method_value

    # PaymentType
    type_value = form_data.get('PaymentType', '').strip()
    if not type_value:
        errors['PaymentType'] = 'Payment type is required.'
    elif type_value not in VALID_TYPES:
        errors['PaymentType'] = 'Please select a valid payment type.'
    else:
        parsed['PaymentType'] = type_value

    return errors, parsed


# ---Routes ----------------------------------------

@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Payment')
            .select('*')
            .order('PaymentID', desc=True)
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load payments: {str(e)}')
        all_records = []

    all_records = _enrich_payments(all_records)

    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('_reference_label', '').lower()
            or q in r.get('PaymentMethod', '').lower()
            or q in r.get('PaymentType', '').lower()
            or q in str(r.get('PaymentDate', '') or '')
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/payment/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data    = {}
    errors       = {}
    sale_options = _get_sale_options()
    appt_options = _get_appointment_options()

    if request.method == 'POST':
        form_data       = request.form.to_dict()
        errors, parsed  = _validate_form(form_data)

        if not errors:
            try:
                supabase.table('Payment').insert({
                    'Sale_SaleID':               parsed.get('Sale_SaleID'),
                    'Appointment_AppointmentID': parsed.get('Appointment_AppointmentID'),
                    'PaymentDate':               parsed['PaymentDate'],
                    'AmountPaid':                parsed['AmountPaid'],
                    'PaymentMethod':             parsed['PaymentMethod'],
                    'PaymentType':               parsed['PaymentType'],
                }).execute()
                flash_success('Payment was recorded successfully.')
                return redirect(url_for('payment.index'))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['Appointment_AppointmentID'] = (
                        'This appointment already has a payment record.'
                    )
                else:
                    flash_error(f'Could not record payment: {error_msg}')

    return render_template(
        'modules/payment/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        sale_options=sale_options,
        appt_options=appt_options,
        method_options=PAYMENT_METHOD_OPTIONS,
        type_options=PAYMENT_TYPE_OPTIONS
    )


@bp.route('/edit/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def edit(payment_id):
    try:
        result = (
            supabase.table('Payment')
            .select('*')
            .eq('PaymentID', payment_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Payment ID {payment_id} was not found.')
        return redirect(url_for('payment.index'))

    current_appt_id = record.get('Appointment_AppointmentID')
    current_ref_type = 'appointment' if current_appt_id else 'sale'

    errors    = {}
    form_data = record.copy()
    form_data['reference_type'] = current_ref_type

    sale_options = _get_sale_options()
    appt_options = _get_appointment_options(exclude_appt_id=current_appt_id)

    if request.method == 'POST':
        form_data      = request.form.to_dict()
        errors, parsed = _validate_form(
            form_data, current_appt_id=current_appt_id
        )

        if not errors:
            try:
                supabase.table('Payment').update({
                    'Sale_SaleID':               parsed.get('Sale_SaleID'),
                    'Appointment_AppointmentID': parsed.get('Appointment_AppointmentID'),
                    'PaymentDate':               parsed['PaymentDate'],
                    'AmountPaid':                parsed['AmountPaid'],
                    'PaymentMethod':             parsed['PaymentMethod'],
                    'PaymentType':               parsed['PaymentType'],
                }).eq('PaymentID', payment_id).execute()
                flash_success(f'Payment PAY-{payment_id} was updated successfully.')
                return redirect(url_for('payment.index'))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['Appointment_AppointmentID'] = (
                        'This appointment already has a payment record.'
                    )
                else:
                    flash_error(f'Could not update payment: {error_msg}')

    return render_template(
        'modules/payment/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        sale_options=sale_options,
        appt_options=appt_options,
        method_options=PAYMENT_METHOD_OPTIONS,
        type_options=PAYMENT_TYPE_OPTIONS
    )


@bp.route('/delete/<int:payment_id>', methods=['POST'])
@login_required
def delete(payment_id):
    try:
        supabase.table('Payment').delete().eq('PaymentID', payment_id).execute()
        flash_success(f'Payment PAY-{payment_id} was deleted successfully.')
    except Exception as e:
        flash_error(f'Could not delete payment: {str(e)}')

    return redirect(url_for('payment.index'))