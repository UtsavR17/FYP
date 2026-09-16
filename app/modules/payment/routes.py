import uuid
from flask import render_template, request, redirect, url_for, jsonify, session
from app.modules.payment import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import is_positive_number
from datetime import date as date_type


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


def _validate_date(raw_value, field_label):
    value = (raw_value or '').strip()
    if not value:
        return None, f'{field_label} is required.'
    try:
        date_type.fromisoformat(value)
        return value, None
    except ValueError:
        return None, f'{field_label} must be a valid date.'


def _get_sale_total_paid(sale_id, exclude_payment_id=None):
    try:
        result = (
            supabase.table('Payment')
            .select('PaymentID, AmountPaid')
            .eq('Sale_SaleID', sale_id)
            .execute()
        )
        total = 0.0
        for p in (result.data or []):
            if exclude_payment_id and p.get('PaymentID') == exclude_payment_id:
                continue
            total += float(p.get('AmountPaid') or 0)
        return total
    except Exception:
        return 0.0


def _get_sale_options(exclude_sale_id=None):
    customer_lookup = {}
    try:
        c = supabase.table('Customer').select('CustomerID, FirstName, LastName').execute()
        customer_lookup = {
            r['CustomerID']: f"{r['FirstName']} {r['LastName']}"
            for r in (c.data or [])
        }
    except Exception:
        pass

    sales_data = []
    try:
        s = (
            supabase.table('Sale')
            .select('SaleID, Customer_CustomerID, SaleDate, TotalAmount')
            .order('SaleID', desc=True)
            .execute()
        )
        sales_data = s.data or []
    except Exception:
        pass

    paid_per_sale = {}
    try:
        pays = supabase.table('Payment').select('Sale_SaleID, AmountPaid').execute()
        for p in (pays.data or []):
            sid = p.get('Sale_SaleID')
            if sid:
                paid_per_sale[sid] = paid_per_sale.get(sid, 0.0) + float(p.get('AmountPaid') or 0)
    except Exception:
        pass

    options = []
    for s in sales_data:
        sid       = s['SaleID']
        total     = float(s.get('TotalAmount') or 0)
        paid      = paid_per_sale.get(sid, 0.0)
        remaining = max(0.0, total - paid)

        if remaining <= 0.001 and sid != exclude_sale_id:
            continue

        cname = customer_lookup.get(s.get('Customer_CustomerID'), 'Unknown')
        balance_str = (
            f'Rs. {remaining:,.2f} remaining' if remaining < total - 0.001
            else f'Rs. {total:,.2f}'
        )
        label = f"SALE-{sid} \u2014 {cname} ({s.get('SaleDate', '?')}) [{balance_str}]"
        options.append((sid, label))

    return options


def _get_appointment_total(appt_id):
    """
    Replicates the Appointment cost calculation used in the Appointment
    module's own view page (services + stock used), so Payment balance
    validation stays consistent with the Appointment's cost summary.
    This is a read-only, independent calculation — it does not import or
    modify anything in the appointment module.
    """
    service_total = 0.0
    try:
        svc_rows = (
            supabase.table('appointment_service')
            .select('Service_ServiceID, Quantity')
            .eq('Appointment_AppointmentID', appt_id)
            .execute()
        )
        raw_services = svc_rows.data or []
        if raw_services:
            all_svc = supabase.table('Service').select('ServiceID, Cost').execute()
            cost_lookup = {
                r['ServiceID']: float(r.get('Cost') or 0)
                for r in (all_svc.data or [])
            }
            for r in raw_services:
                qty = int(r.get('Quantity') or 1)
                service_total += cost_lookup.get(r['Service_ServiceID'], 0.0) * qty
    except Exception:
        pass

    stock_total = 0.0
    try:
        stk_rows = (
            supabase.table('Appointment_Stock')
            .select('Stock_Stock_ID, Quantity')
            .eq('Appointment_AppointmentID', appt_id)
            .execute()
        )
        raw_stock = stk_rows.data or []
        if raw_stock:
            all_stk = supabase.table('Stock').select('Stock_ID, S_Price').execute()
            price_lookup = {
                r['Stock_ID']: float(r.get('S_Price') or 0)
                for r in (all_stk.data or [])
            }
            for r in raw_stock:
                qty = int(r.get('Quantity') or 0)
                stock_total += price_lookup.get(r['Stock_Stock_ID'], 0.0) * qty
    except Exception:
        pass

    return service_total + stock_total


def _get_appointment_total_paid(appt_id, exclude_payment_id=None):
    try:
        result = (
            supabase.table('Payment')
            .select('PaymentID, AmountPaid')
            .eq('Appointment_AppointmentID', appt_id)
            .execute()
        )
        total = 0.0
        for p in (result.data or []):
            if exclude_payment_id and p.get('PaymentID') == exclude_payment_id:
                continue
            total += float(p.get('AmountPaid') or 0)
        return total
    except Exception:
        return 0.0


def _get_appointment_options(exclude_appt_id=None):
    """
    Appointments that still have a remaining balance greater than 0,
    labelled with the remaining amount — mirrors _get_sale_options().
    The currently-linked appointment (exclude_appt_id) is always included
    so the edit form can pre-select it.
    """
    bike_lookup = {}
    try:
        bikes = supabase.table('Customer_bike').select('BikeID, RegistrationNumber').execute()
        bike_lookup = {r['BikeID']: r['RegistrationNumber'] for r in (bikes.data or [])}
    except Exception:
        pass

    appts_data = []
    try:
        appts = (
            supabase.table('Appointment')
            .select('AppointmentID, Customer_bike_BikeID, Appointment_Date')
            .order('AppointmentID', desc=True)
            .execute()
        )
        appts_data = appts.data or []
    except Exception:
        pass

    options = []
    for a in appts_data:
        aid       = a['AppointmentID']
        total     = _get_appointment_total(aid)
        paid      = _get_appointment_total_paid(aid)
        remaining = max(0.0, total - paid)

        if remaining <= 0.001 and aid != exclude_appt_id:
            continue

        reg = bike_lookup.get(a.get('Customer_bike_BikeID'), 'Unknown')
        balance_str = (
            f'Rs. {remaining:,.2f} remaining' if remaining < total - 0.001
            else f'Rs. {total:,.2f}'
        )
        label = f"APPT-#{aid} \u2014 {reg} ({a.get('Appointment_Date', '?')}) [{balance_str}]"
        options.append((aid, label))

    return options


def _enrich_payments(all_records):
    customer_lookup = {}
    try:
        c = supabase.table('Customer').select('CustomerID, FirstName, LastName').execute()
        customer_lookup = {
            r['CustomerID']: f"{r['FirstName']} {r['LastName']}"
            for r in (c.data or [])
        }
    except Exception:
        pass

    sale_lookup = {}
    try:
        sales = supabase.table('Sale').select('SaleID, Customer_CustomerID').execute()
        for s in (sales.data or []):
            cname = customer_lookup.get(s.get('Customer_CustomerID'), 'Unknown')
            sale_lookup[s['SaleID']] = f"SALE-{s['SaleID']} \u2014 {cname}"
    except Exception:
        pass

    bike_lookup = {}
    try:
        bikes = supabase.table('Customer_bike').select('BikeID, RegistrationNumber').execute()
        bike_lookup = {r['BikeID']: r['RegistrationNumber'] for r in (bikes.data or [])}
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
            appt_lookup[a['AppointmentID']] = f"APPT-#{a['AppointmentID']} \u2014 {reg} ({a.get('Appointment_Date', '?')})"
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
            pay['_reference_type']  = '-'
            pay['_reference_label'] = '-'

    return all_records


def _validate_form(form_data, current_appt_id=None, current_payment_id=None, locked_ref_type=None):
    errors = {}
    parsed = {}

    reference_type = locked_ref_type or form_data.get('reference_type', 'sale')
    parsed['reference_type'] = reference_type

    sale_id_raw = form_data.get('Sale_SaleID', '').strip()
    appt_id_raw = form_data.get('Appointment_AppointmentID', '').strip()

    sale_id    = None
    sale_total = None
    appt_id    = None
    appt_total = None

    if reference_type == 'sale':
        if not sale_id_raw:
            errors['Sale_SaleID'] = 'Please select a sale.'
        else:
            try:
                sale_id = int(sale_id_raw)
                parsed['Sale_SaleID']               = sale_id
                parsed['Appointment_AppointmentID'] = None
                sale_r = (
                    supabase.table('Sale')
                    .select('TotalAmount')
                    .eq('SaleID', sale_id)
                    .single()
                    .execute()
                )
                sale_total = float(sale_r.data.get('TotalAmount') or 0)
            except ValueError:
                errors['Sale_SaleID'] = 'Please select a valid sale.'
            except Exception:
                pass
    else:
        if not appt_id_raw:
            errors['Appointment_AppointmentID'] = 'Please select an appointment.'
        else:
            try:
                appt_id = int(appt_id_raw)
                parsed['Appointment_AppointmentID'] = appt_id
                parsed['Sale_SaleID']               = None
                appt_total = _get_appointment_total(appt_id)
            except ValueError:
                errors['Appointment_AppointmentID'] = 'Please select a valid appointment.'

    date_raw = form_data.get('PaymentDate', '').strip()
    pay_date, date_err = _validate_date(date_raw, 'Payment Date')
    if date_err:
        errors['PaymentDate'] = date_err
    else:
        parsed['PaymentDate'] = pay_date

    amount_raw = form_data.get('AmountPaid', '').strip()
    if not amount_raw:
        errors['AmountPaid'] = 'Amount paid is required.'
    elif not is_positive_number(amount_raw) or float(amount_raw) <= 0:
        errors['AmountPaid'] = 'Amount paid must be a number greater than 0.'
    else:
        amount_paid = float(amount_raw)

        if (reference_type == 'sale' and sale_id and sale_total is not None
                and 'Sale_SaleID' not in errors):
            total_paid_so_far = _get_sale_total_paid(sale_id, exclude_payment_id=current_payment_id)
            remaining = max(0.0, sale_total - total_paid_so_far)
            if amount_paid > remaining + 0.001:
                errors['AmountPaid'] = (
                    f'Amount paid (Rs. {amount_paid:,.2f}) exceeds the remaining '
                    f'balance of Rs. {remaining:,.2f} for this sale. '
                    f'The sale total is Rs. {sale_total:,.2f} and '
                    f'Rs. {total_paid_so_far:,.2f} has already been paid.'
                )
            else:
                parsed['AmountPaid'] = amount_paid

        elif (reference_type == 'appointment' and appt_id and appt_total is not None
                and 'Appointment_AppointmentID' not in errors):
            total_paid_so_far = _get_appointment_total_paid(appt_id, exclude_payment_id=current_payment_id)
            remaining = max(0.0, appt_total - total_paid_so_far)
            if remaining <= 0.001:
                errors['AmountPaid'] = (
                    f'This appointment has already been fully paid '
                    f'(Rs. {appt_total:,.2f} total, Rs. {total_paid_so_far:,.2f} paid).'
                )
            elif amount_paid > remaining + 0.001:
                errors['AmountPaid'] = (
                    f'Amount paid (Rs. {amount_paid:,.2f}) exceeds the remaining '
                    f'balance of Rs. {remaining:,.2f} for this appointment. '
                    f'The appointment total is Rs. {appt_total:,.2f} and '
                    f'Rs. {total_paid_so_far:,.2f} has already been paid.'
                )
            else:
                parsed['AmountPaid'] = amount_paid
        else:
            parsed['AmountPaid'] = amount_paid

    method_value = form_data.get('PaymentMethod', '').strip()
    if not method_value:
        errors['PaymentMethod'] = 'Payment method is required.'
    elif method_value not in VALID_METHODS:
        errors['PaymentMethod'] = 'Please select a valid payment method.'
    else:
        parsed['PaymentMethod'] = method_value

    type_value = form_data.get('PaymentType', '').strip()
    if not type_value:
        errors['PaymentType'] = 'Payment type is required.'
    elif type_value not in VALID_TYPES:
        errors['PaymentType'] = 'Please select a valid payment type.'
    else:
        parsed['PaymentType'] = type_value

    return errors, parsed


@bp.route('/sale-info/<int:sale_id>')
@login_required
def sale_info(sale_id):
    exclude_payment_id = request.args.get('exclude_payment_id', type=int)
    try:
        sale_r = (
            supabase.table('Sale')
            .select('SaleDate, TotalAmount')
            .eq('SaleID', sale_id)
            .single()
            .execute()
        )
        total      = float(sale_r.data.get('TotalAmount') or 0)
        total_paid = _get_sale_total_paid(sale_id, exclude_payment_id=exclude_payment_id)
        remaining  = max(0.0, total - total_paid)
        return jsonify({
            'sale_date':    sale_r.data.get('SaleDate', ''),
            'total_amount': total,
            'total_paid':   total_paid,
            'remaining':    remaining,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@bp.route('/appointment-info/<int:appt_id>')
@login_required
def appointment_info(appt_id):
    exclude_payment_id = request.args.get('exclude_payment_id', type=int)
    try:
        total      = _get_appointment_total(appt_id)
        total_paid = _get_appointment_total_paid(appt_id, exclude_payment_id=exclude_payment_id)
        remaining  = max(0.0, total - total_paid)
        return jsonify({
            'total_amount': total,
            'total_paid':   total_paid,
            'remaining':    remaining,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = supabase.table('Payment').select('*').order('PaymentID', desc=True).execute()
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

    prefill_appt = request.args.get('prefill_appt', type=int)

    if request.method == 'GET':
        form_token = str(uuid.uuid4())
        session['payment_form_token'] = form_token
        if prefill_appt:
            form_data = {
                'reference_type': 'appointment',
                'Appointment_AppointmentID': str(prefill_appt),
            }
    else:
        form_token = ''

    if request.method == 'POST':
        submitted_token = request.form.get('form_token', '')
        session_token   = session.get('payment_form_token')

        if session_token is not None and (
            not submitted_token or submitted_token != session_token
        ):
            flash_error(
                'This payment appears to have already been submitted. '
                'Please check the Payments list before trying again.'
            )
            return redirect(url_for('payment.index'))

        if session_token is not None:
            session.pop('payment_form_token', None)

        form_data      = request.form.to_dict()
        errors, parsed = _validate_form(form_data)

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
                        'This appointment already has a conflicting payment record.'
                    )
                else:
                    flash_error(f'Could not record payment: {error_msg}')

        form_token = str(uuid.uuid4())
        session['payment_form_token'] = form_token

    return render_template(
        'modules/payment/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        record=None,
        sale_options=sale_options,
        appt_options=appt_options,
        method_options=PAYMENT_METHOD_OPTIONS,
        type_options=PAYMENT_TYPE_OPTIONS,
        form_token=form_token,
        locked_ref_type=None
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
    current_sale_id = record.get('Sale_SaleID')
    locked_ref_type  = 'appointment' if current_appt_id else 'sale'

    errors    = {}
    form_data = record.copy()
    form_data['reference_type'] = locked_ref_type

    sale_options = _get_sale_options(exclude_sale_id=current_sale_id)
    appt_options = _get_appointment_options(exclude_appt_id=current_appt_id)

    if request.method == 'POST':
        form_data      = request.form.to_dict()
        errors, parsed = _validate_form(
            form_data,
            current_appt_id=current_appt_id,
            current_payment_id=payment_id,
            locked_ref_type=locked_ref_type
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
                        'This appointment already has a conflicting payment record.'
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
        type_options=PAYMENT_TYPE_OPTIONS,
        form_token=None,
        locked_ref_type=locked_ref_type
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