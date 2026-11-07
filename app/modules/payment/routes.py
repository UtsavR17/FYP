import uuid
from flask import render_template, request, redirect, url_for, jsonify, session
from app.modules.payment import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import is_positive_number
from app.utils.order_ref import format_order_ref, parse_order_query
from app.utils.ids import display_id, legacy_ref, parse_id_query, typed_id
from datetime import date as date_type
from app.utils.text import norm
from app.modules.online_order.routes import today_mauritius


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

TYPE_FULL        = 'Full Payment'
TYPE_DEPOSIT     = 'Deposit'
TYPE_INSTALMENT  = 'Instalment'

# Appointments that can take payments (DEC-6). Pending, Cancelled and No Show never can.
PAYABLE_APPOINTMENT_STATUSES = ('Confirmed', 'In Progress', 'Completed')

# Money is NUMERIC(10,2); amounts closer than half a cent are equal.
CENT = 0.005

PAYMENT_TYPE_HELP = (
    'Full Payment settles the whole remaining balance. Deposit is a first, partial payment. '
    'Instalment is a later payment after a deposit.'
)

# Online payments (Task 40) are created by the Stripe webhook of the Client
# Side. They are system records: they cannot be edited or deleted here.
ONLINE_PAYMENT_LOCKED_MSG = (
    'This is an online payment recorded automatically by Stripe checkout, '
    'so it cannot be edited or deleted here.'
)


def _is_online_payment(record):
    """True for payments created by the online checkout (order link or Stripe intent)."""
    return bool(record and (record.get('Online_Order_OrderID') or record.get('StripePaymentIntentID')))


def _online_order_customers(order_ids):
    """{OrderID: CustomerID} with one .in_() query per 100 ids."""
    ids = sorted({i for i in order_ids if i})
    order_customer = {}
    for start in range(0, len(ids), 100):
        try:
            rows = (
                supabase.table('Online_Order')
                .select('OrderID, Customer_CustomerID')
                .in_('OrderID', ids[start:start + 100])
                .execute()
            ).data or []
            for r in rows:
                order_customer[r['OrderID']] = r.get('Customer_CustomerID')
        except Exception:
            continue
    return order_customer


def _validate_date(raw_value, field_label):
    value = (raw_value or '').strip()
    if not value:
        return None, f'{field_label} is required.'
    try:
        date_type.fromisoformat(value)
        return value, None
    except ValueError:
        return None, f'{field_label} must be a valid date.'


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
        label = f"{typed_id('sale', sid)} - {cname} ({s.get('SaleDate', '?')}) [{balance_str}]"
        options.append((sid, label))

    return options


def _chunks(ids, size=100):
    ids = sorted({i for i in ids if i is not None})
    for start in range(0, len(ids), size):
        yield ids[start:start + size]


def _appointment_totals(appt_ids):
    """
    {AppointmentID: total} for services plus stock used, with batched queries.
    Same calculation as the Appointment view page (service quantity defaults to 1,
    stock quantity to 0). Lookup errors count as 0, as before.
    """
    ids = list({i for i in appt_ids if i is not None})
    totals = {i: 0.0 for i in ids}
    if not ids:
        return totals

    service_rows, stock_rows = [], []
    for chunk in _chunks(ids):
        try:
            service_rows += (
                supabase.table('appointment_service')
                .select('Appointment_AppointmentID, Service_ServiceID, Quantity')
                .in_('Appointment_AppointmentID', chunk)
                .execute()
            ).data or []
        except Exception:
            pass
        try:
            stock_rows += (
                supabase.table('Appointment_Stock')
                .select('Appointment_AppointmentID, Stock_Stock_ID, Quantity')
                .in_('Appointment_AppointmentID', chunk)
                .execute()
            ).data or []
        except Exception:
            pass

    cost_lookup = {}
    if service_rows:
        try:
            all_svc = supabase.table('Service').select('ServiceID, Cost').execute()
            cost_lookup = {r['ServiceID']: float(r.get('Cost') or 0) for r in (all_svc.data or [])}
        except Exception:
            pass
    price_lookup = {}
    for chunk in _chunks(r.get('Stock_Stock_ID') for r in stock_rows):
        try:
            rows = supabase.table('Stock').select('Stock_ID, S_Price').in_('Stock_ID', chunk).execute()
            price_lookup.update({r['Stock_ID']: float(r.get('S_Price') or 0) for r in (rows.data or [])})
        except Exception:
            pass

    for r in service_rows:
        qty = int(r.get('Quantity') or 1)
        totals[r['Appointment_AppointmentID']] += cost_lookup.get(r['Service_ServiceID'], 0.0) * qty
    for r in stock_rows:
        qty = int(r.get('Quantity') or 0)
        totals[r['Appointment_AppointmentID']] += price_lookup.get(r['Stock_Stock_ID'], 0.0) * qty
    return totals


def _get_appointment_total(appt_id):
    """Services plus stock used for one appointment (see _appointment_totals)."""
    return _appointment_totals([appt_id]).get(appt_id, 0.0)


def _paid_by(column, ref_ids, exclude_payment_id=None):
    """{reference id: amount paid} for Sale_SaleID or Appointment_AppointmentID, batched."""
    paid = {}
    for chunk in _chunks(ref_ids):
        try:
            rows = (
                supabase.table('Payment')
                .select(f'PaymentID, {column}, AmountPaid')
                .in_(column, chunk)
                .execute()
            ).data or []
        except Exception:
            continue
        for r in rows:
            if exclude_payment_id and r.get('PaymentID') == exclude_payment_id:
                continue
            paid[r[column]] = paid.get(r[column], 0.0) + float(r.get('AmountPaid') or 0)
    return paid


def _get_appointment_total_paid(appt_id, exclude_payment_id=None):
    return _paid_by('Appointment_AppointmentID', [appt_id], exclude_payment_id).get(appt_id, 0.0)


def _get_appointment_options(current_appt_id=None):
    """
    Payable appointments (PAYABLE_APPOINTMENT_STATUSES) with a remaining balance,
    labelled with the amount left. On Edit the payment's own appointment
    (current_appt_id) is always included, marked with its status when it is no
    longer payable, so the record can still be edited.
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
            .select('AppointmentID, Customer_bike_BikeID, Appointment_Date, Status')
            .order('AppointmentID', desc=True)
            .execute()
        )
        appts_data = [
            a for a in (appts.data or [])
            if a.get('Status') in PAYABLE_APPOINTMENT_STATUSES or a['AppointmentID'] == current_appt_id
        ]
    except Exception:
        pass

    ids = [a['AppointmentID'] for a in appts_data]
    totals = _appointment_totals(ids)
    paid = _paid_by('Appointment_AppointmentID', ids)

    options = []
    for a in appts_data:
        aid       = a['AppointmentID']
        total     = totals.get(aid, 0.0)
        remaining = max(0.0, total - paid.get(aid, 0.0))

        if remaining <= 0.001 and aid != current_appt_id:
            continue

        reg = bike_lookup.get(a.get('Customer_bike_BikeID'), 'Unknown')
        balance_str = (
            f'Rs. {remaining:,.2f} remaining' if remaining < total - 0.001
            else f'Rs. {total:,.2f}'
        )
        status = a.get('Status')
        status_note = '' if status in PAYABLE_APPOINTMENT_STATUSES else f' ({status})'
        label = f"{typed_id('appointment', aid)} - {reg} ({a.get('Appointment_Date', '?')}) [{balance_str}]{status_note}"
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
            sale_lookup[s['SaleID']] = f"{display_id(s['SaleID'])} - {cname}"
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
            appt_lookup[a['AppointmentID']] = f"{display_id(a['AppointmentID'])} - {reg} ({a.get('Appointment_Date', '?')})"
    except Exception:
        pass

    order_customer = _online_order_customers(
        p.get('Online_Order_OrderID') for p in all_records
    )

    for pay in all_records:
        sale_id  = pay.get('Sale_SaleID')
        appt_id  = pay.get('Appointment_AppointmentID')
        order_id = pay.get('Online_Order_OrderID')
        pay['_reference_url'] = None
        pay['_locked']        = _is_online_payment(pay)
        if sale_id:
            pay['_reference_type']  = 'Sale'
            pay['_reference_key']   = 'sale'
            pay['_reference_label'] = sale_lookup.get(sale_id, display_id(sale_id))
        elif appt_id:
            pay['_reference_type']  = 'Appointment'
            pay['_reference_key']   = 'appointment'
            pay['_reference_label'] = appt_lookup.get(appt_id, display_id(appt_id))
        elif order_id:
            ref   = format_order_ref(order_id)
            cname = customer_lookup.get(order_customer.get(order_id))
            pay['_reference_type']  = 'Online Order'
            pay['_reference_key']   = 'online'
            pay['_reference_badge'] = 'Online order'
            pay['_reference_label'] = f'{ref} - {cname}' if cname else ref
            pay['_reference_url']   = url_for('online_order.view', order_id=order_id)
        else:
            pay['_reference_type']  = '-'
            pay['_reference_key']   = 'none'
            pay['_reference_label'] = '-'
        # Old display forms (SALE-5, APPT-#3, ORD-000012, PAY-7), searched but never shown
        pay['_search_alias'] = ' '.join(filter(None, (
            legacy_ref('payment', pay.get('PaymentID')),
            legacy_ref('sale', sale_id) if sale_id else '',
            legacy_ref('appointment', appt_id) if appt_id else '',
            legacy_ref('order', order_id) if order_id else '',
        )))

    return all_records


def _payment_history(column, ref_id):
    """
    Payments of one sale or appointment (column = Sale_SaleID or
    Appointment_AppointmentID), oldest first. Raises on a database error so the
    caller can refuse a save instead of guessing the balance.
    """
    return (
        supabase.table('Payment')
        .select('PaymentID, PaymentType, AmountPaid, PaymentDate, PaymentMethod, '
                'Online_Order_OrderID, StripePaymentIntentID')
        .eq(column, ref_id)
        .order('PaymentID')
        .execute()
    ).data or []


def _effective_type(payment):
    """An online (Stripe) payment on a sale is the reservation deposit (DEC-5)."""
    return TYPE_DEPOSIT if _is_online_payment(payment) else payment.get('PaymentType')


def payment_summary(total, payments, exclude_payment_id=None):
    """Total, paid, balance and status (Unpaid / Partially paid / Paid) of a sale or appointment."""
    total = round(float(total or 0), 2)
    paid = round(sum(float(p.get('AmountPaid') or 0) for p in payments
                     if p.get('PaymentID') != exclude_payment_id), 2)
    balance = round(max(0.0, total - paid), 2)
    if balance <= CENT:
        status = 'Paid'
    elif paid > CENT:
        status = 'Partially paid'
    else:
        status = 'Unpaid'
    return {'total': total, 'paid': paid, 'balance': balance, 'status': status}


def check_payment_rules(payment_type, amount, total, history, current_payment=None, noun='sale'):
    """
    DEC-5 payment matrix. Returns (field, message) for the first broken rule, or None.

    history: every payment of this sale or appointment (from _payment_history).
    current_payment: the stored record when editing; it is excluded from the
    balance, and only payments recorded before it count as "earlier".
    """
    current_id = current_payment.get('PaymentID') if current_payment else None
    others = [p for p in history if p.get('PaymentID') != current_id]
    earlier = [p for p in others if current_id is None or (p.get('PaymentID') or 0) < current_id]
    later = [p for p in others if current_id is not None and (p.get('PaymentID') or 0) > current_id]
    total = round(float(total or 0), 2)
    remaining = round(max(0.0, total - sum(float(p.get('AmountPaid') or 0) for p in others)), 2)

    if remaining <= CENT:
        return 'AmountPaid', f'This {noun} is already fully paid (Rs. {total:,.2f}).'

    if (current_payment and current_payment.get('PaymentType') == TYPE_DEPOSIT and later
            and payment_type != TYPE_DEPOSIT):
        return 'PaymentType', 'This deposit already has later payments, so its type cannot be changed.'

    if payment_type == TYPE_FULL:
        if abs(amount - remaining) > CENT:
            return 'AmountPaid', f'A full payment must settle the remaining balance of Rs. {remaining:,.2f}.'
        return None

    if payment_type == TYPE_DEPOSIT:
        if earlier:
            return 'PaymentType', (
                f'A deposit can only be the first payment on this {noun}. '
                f'Choose Instalment or Full Payment.'
            )
        if amount >= total - CENT:
            return 'AmountPaid', (
                f'A deposit must be less than the total of Rs. {total:,.2f}. '
                f'Choose Full Payment to pay everything.'
            )
    elif payment_type == TYPE_INSTALMENT:
        if not any(_effective_type(p) == TYPE_DEPOSIT for p in earlier):
            return 'PaymentType', 'Record the deposit first. Instalments can only follow a deposit.'

    if amount > remaining + CENT:
        return 'AmountPaid', (
            f'Amount paid (Rs. {amount:,.2f}) exceeds the remaining balance of '
            f'Rs. {remaining:,.2f} for this {noun}.'
        )
    return None


def _customer_name(customer_id):
    if not customer_id:
        return None
    rows = (
        supabase.table('Customer').select('FirstName, LastName')
        .eq('CustomerID', customer_id).execute()
    ).data or []
    if not rows:
        return None
    return f"{rows[0].get('FirstName') or ''} {rows[0].get('LastName') or ''}".strip() or None


def _model_and_brand(model_no):
    """(model description, brand name) for a Model_No; None parts when missing."""
    if not model_no:
        return None, None
    rows = (
        supabase.table('Model').select('Description, Brand_Brand_ID')
        .eq('Model_No', model_no).execute()
    ).data or []
    if not rows:
        return None, None
    brand = None
    if rows[0].get('Brand_Brand_ID'):
        b = (
            supabase.table('Brand').select('Brand_Name')
            .eq('Brand_ID', rows[0]['Brand_Brand_ID']).execute()
        ).data or []
        brand = b[0].get('Brand_Name') if b else None
    return rows[0].get('Description'), brand


def _bike_text(brand, model, year=None, colour=None):
    """'Brand Model (Year), Colour' with missing parts left out; '-' when nothing is known."""
    text = ' '.join(x for x in (brand, model) if x)
    if year:
        text = f'{text} ({year})' if text else f'({year})'
    if colour:
        text = f'{text}, {colour}' if text else colour
    return text or '-'


def _sale_context(sale_id, exclude_payment_id=None):
    """
    Read-only context for a sale payment: bike (brand, model, year, colour, VIN),
    customer, sale date and the balance. Raises LookupError when the sale does
    not exist; other database errors are raised as they are.
    """
    rows = (
        supabase.table('Sale')
        .select('SaleID, Customer_CustomerID, New_MotorBike_NB_ID, SaleDate, TotalAmount')
        .eq('SaleID', sale_id).execute()
    ).data or []
    if not rows:
        raise LookupError(sale_id)
    sale = rows[0]
    bike = {}
    if sale.get('New_MotorBike_NB_ID'):
        b = (
            supabase.table('New_MotorBike')
            .select('NB_ID, Model_Model_No, Year, VIN, Color_Color')
            .eq('NB_ID', sale['New_MotorBike_NB_ID']).execute()
        ).data or []
        bike = b[0] if b else {}
    model, brand = _model_and_brand(bike.get('Model_Model_No'))
    summary = payment_summary(sale.get('TotalAmount'), _payment_history('Sale_SaleID', sale_id),
                              exclude_payment_id)
    return {
        'kind':          'sale',
        'sale_id':       sale_id,
        'customer_name': _customer_name(sale.get('Customer_CustomerID')),
        'brand':         brand,
        'model':         model,
        'year':          bike.get('Year'),
        'colour':        bike.get('Color_Color'),
        'vin':           bike.get('VIN'),
        'bike':          _bike_text(brand, model, bike.get('Year'), bike.get('Color_Color')),
        'sale_date':     sale.get('SaleDate'),
        'total_amount':  summary['total'],
        'total_paid':    summary['paid'],
        'remaining':     summary['balance'],
        'status':        summary['status'],
    }


def _appointment_context(appt_id, exclude_payment_id=None):
    """
    Read-only context for an appointment payment: registration, brand and
    model, customer, date, status and the balance. Raises LookupError when the
    appointment does not exist.
    """
    rows = (
        supabase.table('Appointment')
        .select('AppointmentID, Customer_bike_BikeID, Appointment_Date, Status')
        .eq('AppointmentID', appt_id).execute()
    ).data or []
    if not rows:
        raise LookupError(appt_id)
    appt = rows[0]
    bike = {}
    if appt.get('Customer_bike_BikeID'):
        b = (
            supabase.table('Customer_bike')
            .select('BikeID, RegistrationNumber, Model_Model_No, Customer_CustomerID')
            .eq('BikeID', appt['Customer_bike_BikeID']).execute()
        ).data or []
        bike = b[0] if b else {}
    model, brand = _model_and_brand(bike.get('Model_Model_No'))
    summary = payment_summary(_get_appointment_total(appt_id),
                              _payment_history('Appointment_AppointmentID', appt_id), exclude_payment_id)
    return {
        'kind':                'appointment',
        'appointment_id':      appt_id,
        'registration':        bike.get('RegistrationNumber'),
        'bike':                _bike_text(brand, model),
        'brand':               brand,
        'model':               model,
        'customer_name':       _customer_name(bike.get('Customer_CustomerID')),
        'appointment_date':    appt.get('Appointment_Date'),
        'appointment_status':  appt.get('Status'),
        'total_amount':        summary['total'],
        'total_paid':          summary['paid'],
        'remaining':           summary['balance'],
        'status':              summary['status'],
    }


def _int_or_none(raw):
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _validate_form(form_data, mode, context_sale_id=None, current_payment=None):
    """
    Validate a payment form. mode is 'sale' (the sale page path, context_sale_id
    set) or 'appointment' (the standalone page) on Create, and the stored
    reference type on Edit (current_payment set). The reference always comes
    from the mode, never from the posted reference_type.
    """
    errors = {}
    parsed = {'reference_type': mode, 'Sale_SaleID': None, 'Appointment_AppointmentID': None}

    posted_type = (form_data.get('reference_type') or '').strip()
    sale_id_raw = (form_data.get('Sale_SaleID') or '').strip()
    appt_id_raw = (form_data.get('Appointment_AppointmentID') or '').strip()
    is_edit = current_payment is not None

    # Context: a sale payment only from its sale page, an appointment payment never there.
    if not is_edit and mode == 'appointment' and (posted_type == 'sale' or sale_id_raw):
        errors['reference'] = 'Sale payments are recorded from the sale: open the sale and choose Record payment.'
    if not is_edit and mode == 'sale' and (posted_type == 'appointment' or appt_id_raw):
        errors['reference'] = f'This page records a payment for {typed_id("sale", context_sale_id)} only.'

    total, history, noun = None, None, mode
    if mode == 'sale':
        sale_id = _int_or_none(sale_id_raw)
        if not sale_id_raw:
            errors['Sale_SaleID'] = 'Please select a sale.'
        elif sale_id is None:
            errors['Sale_SaleID'] = 'Please select a valid sale.'
        elif not is_edit and sale_id != context_sale_id:
            errors['reference'] = (
                f'This page records a payment for {typed_id("sale", context_sale_id)} only. '
                f'Open the sale you want to pay.'
            )
        else:
            try:
                rows = (
                    supabase.table('Sale').select('SaleID, TotalAmount')
                    .eq('SaleID', sale_id).execute()
                ).data or []
                if not rows:
                    errors['Sale_SaleID'] = 'Please select a valid sale.'
                else:
                    total = float(rows[0].get('TotalAmount') or 0)
                    history = _payment_history('Sale_SaleID', sale_id)
                    parsed['Sale_SaleID'] = sale_id
            except Exception:
                errors['reference'] = 'Could not check this sale\'s payments. Please try again.'
    else:
        noun = 'appointment'
        appt_id = _int_or_none(appt_id_raw)
        if not appt_id_raw:
            errors['Appointment_AppointmentID'] = 'Please select an appointment.'
        elif appt_id is None:
            errors['Appointment_AppointmentID'] = 'Please select a valid appointment.'
        else:
            try:
                rows = (
                    supabase.table('Appointment').select('AppointmentID, Status')
                    .eq('AppointmentID', appt_id).execute()
                ).data or []
                keeps_own = is_edit and appt_id == current_payment.get('Appointment_AppointmentID')
                if not rows:
                    errors['Appointment_AppointmentID'] = 'Please select a valid appointment.'
                elif rows[0].get('Status') not in PAYABLE_APPOINTMENT_STATUSES and not keeps_own:
                    errors['Appointment_AppointmentID'] = (
                        f"Payments can only be recorded for Confirmed, In Progress or Completed "
                        f"appointments. This one is {rows[0].get('Status')}."
                    )
                else:
                    total = _get_appointment_total(appt_id)
                    history = _payment_history('Appointment_AppointmentID', appt_id)
                    parsed['Appointment_AppointmentID'] = appt_id
            except Exception:
                errors['reference'] = 'Could not check this appointment\'s payments. Please try again.'

    date_raw = (form_data.get('PaymentDate') or '').strip()
    pay_date, date_err = _validate_date(date_raw, 'Payment Date')
    if date_err:
        errors['PaymentDate'] = date_err
    elif date_type.fromisoformat(pay_date) > today_mauritius():
        errors['PaymentDate'] = 'Payment date cannot be in the future.'
    else:
        parsed['PaymentDate'] = pay_date

    method_value = (form_data.get('PaymentMethod') or '').strip()
    if not method_value:
        errors['PaymentMethod'] = 'Payment method is required.'
    elif method_value not in VALID_METHODS:
        errors['PaymentMethod'] = 'Please select a valid payment method.'
    else:
        parsed['PaymentMethod'] = method_value

    type_value = (form_data.get('PaymentType') or '').strip()
    if not type_value:
        errors['PaymentType'] = 'Payment type is required.'
    elif type_value not in VALID_TYPES:
        errors['PaymentType'] = 'Please select a valid payment type.'
    else:
        parsed['PaymentType'] = type_value

    amount_raw = (form_data.get('AmountPaid') or '').strip()
    amount_paid = None
    if not amount_raw:
        errors['AmountPaid'] = 'Amount paid is required.'
    elif not is_positive_number(amount_raw) or float(amount_raw) <= 0:
        errors['AmountPaid'] = 'Amount paid must be a number greater than 0.'
    else:
        amount_paid = round(float(amount_raw), 2)
        parsed['AmountPaid'] = amount_paid

    # DEC-5 rules, with balances read fresh at save time.
    if (history is not None and amount_paid is not None and 'PaymentType' not in errors
            and 'reference' not in errors):
        broken = check_payment_rules(type_value, amount_paid, total, history, current_payment, noun)
        if broken:
            errors[broken[0]] = broken[1]

    return errors, parsed


@bp.route('/sale-info/<int:sale_id>')
@login_required
def sale_info(sale_id):
    exclude_payment_id = request.args.get('exclude_payment_id', type=int)
    try:
        return jsonify(_sale_context(sale_id, exclude_payment_id))
    except LookupError:
        return jsonify({'error': 'Sale not found.'}), 404
    except Exception:
        return jsonify({'error': 'Could not load the sale.'}), 500


@bp.route('/appointment-info/<int:appt_id>')
@login_required
def appointment_info(appt_id):
    exclude_payment_id = request.args.get('exclude_payment_id', type=int)
    try:
        return jsonify(_appointment_context(appt_id, exclude_payment_id))
    except LookupError:
        return jsonify({'error': 'Appointment not found.'}), 404
    except Exception:
        return jsonify({'error': 'Could not load the appointment.'}), 500


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
        # A number or an old prefixed form (12, ORD-000012, SALE-5, APPT-#3, PAY-7)
        # finds the payment or its reference; old partial forms match the hidden alias.
        q_order_id = parse_order_query(search_query)
        q_sale_id = parse_id_query(search_query, 'sale')
        q_appt_id = parse_id_query(search_query, 'appointment')
        q_pay_id = parse_id_query(search_query, 'payment')
        all_records = [
            r for r in all_records
            if q in norm(r.get('_reference_label'))
            or q in norm(r.get('_reference_type'))
            or q in r.get('_search_alias', '')
            or (q_sale_id is not None and r.get('Sale_SaleID') == q_sale_id)
            or (q_appt_id is not None and r.get('Appointment_AppointmentID') == q_appt_id)
            or (q_pay_id is not None and r.get('PaymentID') == q_pay_id)
            or q in norm(r.get('PaymentMethod'))
            or q in norm(r.get('PaymentType'))
            or q in str(r.get('PaymentDate', '') or '')
            or (q_order_id is not None and r.get('Online_Order_OrderID') == q_order_id)
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/payment/list.html',
        pagination=pagination,
        search_query=search_query
    )


def _render_form(**ctx):
    return render_template(
        'modules/payment/form.html',
        method_options=PAYMENT_METHOD_OPTIONS,
        type_options=PAYMENT_TYPE_OPTIONS,
        type_help=PAYMENT_TYPE_HELP,
        **ctx
    )


def _safe_appointment_context(appt_id, exclude_payment_id=None):
    appt_id = _int_or_none(appt_id)
    if appt_id is None:
        return None
    try:
        return _appointment_context(appt_id, exclude_payment_id)
    except Exception:
        return None


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    Two contextual modes (ISS-04): /payments/create records an appointment
    payment; /payments/create?sale=<id> records a payment for that sale only
    (opened from the sale page). The mode comes from the URL, on GET and POST.
    """
    sale_ctx_id = None
    if 'sale' in request.args:
        sale_ctx_id = _int_or_none(request.args.get('sale'))
        if sale_ctx_id is None:
            flash_error('That sale link is not valid.')
            return redirect(url_for('sale.index'))
    mode = 'sale' if sale_ctx_id else 'appointment'

    sale_ctx = None
    if mode == 'sale':
        try:
            sale_ctx = _sale_context(sale_ctx_id)
        except LookupError:
            flash_error(f'Sale ID {sale_ctx_id} was not found.')
            return redirect(url_for('sale.index'))
        except Exception:
            flash_error('Could not load the sale. Please try again.')
            return redirect(url_for('sale.view', sale_id=sale_ctx_id))
        if request.method == 'GET' and sale_ctx['remaining'] <= CENT:
            flash_error(f'{typed_id("sale", sale_ctx_id)} is already fully paid.')
            return redirect(url_for('sale.view', sale_id=sale_ctx_id))

    done_url = (url_for('sale.view', sale_id=sale_ctx_id) if mode == 'sale'
                else url_for('payment.index'))
    errors = {}

    if request.method == 'GET':
        form_token = str(uuid.uuid4())
        session['payment_form_token'] = form_token
        form_data = {'reference_type': mode, 'PaymentDate': today_mauritius().isoformat()}
        if mode == 'sale':
            form_data['Sale_SaleID'] = str(sale_ctx_id)
        else:
            prefill_appt = request.args.get('prefill_appt', type=int)
            if prefill_appt:
                form_data['Appointment_AppointmentID'] = str(prefill_appt)
    else:
        submitted_token = request.form.get('form_token', '')
        session_token   = session.pop('payment_form_token', None)

        # One-time token: a resubmitted form (token already used) is refused.
        if not submitted_token or submitted_token != session_token:
            flash_error(
                'This payment appears to have already been submitted. '
                'Please check the payments before trying again.'
            )
            return redirect(done_url)

        form_data      = request.form.to_dict()
        errors, parsed = _validate_form(form_data, mode, context_sale_id=sale_ctx_id)

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
                return redirect(done_url)
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
        if mode == 'sale':
            form_data['Sale_SaleID'] = str(sale_ctx_id)
            try:
                sale_ctx = _sale_context(sale_ctx_id)   # fresh balance after a refused save
            except Exception:
                pass

    if mode == 'sale':
        context = sale_ctx
        appt_options = []
    else:
        context = _safe_appointment_context(form_data.get('Appointment_AppointmentID'))
        appt_options = _get_appointment_options()

    return _render_form(
        form_data=form_data,
        errors=errors,
        is_edit=False,
        record=None,
        mode=mode,
        context=context,
        sale_options=[],
        appt_options=appt_options,
        form_token=form_token,
        cancel_url=done_url,
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

    # Online payments are system records (Task 40): refuse GET and POST alike.
    if _is_online_payment(record):
        flash_error(ONLINE_PAYMENT_LOCKED_MSG)
        return redirect(url_for('payment.index'))

    current_appt_id = record.get('Appointment_AppointmentID')
    current_sale_id = record.get('Sale_SaleID')
    mode = 'appointment' if current_appt_id else 'sale'

    errors    = {}
    form_data = record.copy()
    form_data['reference_type'] = mode

    if request.method == 'POST':
        form_data      = request.form.to_dict()
        form_data['reference_type'] = mode
        errors, parsed = _validate_form(form_data, mode, current_payment=record)

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
                flash_success(f'Payment {payment_id} was updated successfully.')
                return redirect(url_for('payment.index'))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['Appointment_AppointmentID'] = (
                        'This appointment already has a conflicting payment record.'
                    )
                else:
                    flash_error(f'Could not update payment: {error_msg}')

    context = None
    if mode == 'sale':
        sale_id = _int_or_none(form_data.get('Sale_SaleID'))
        if sale_id is not None:
            try:
                context = _sale_context(sale_id, exclude_payment_id=payment_id)
            except Exception:
                context = None
    else:
        context = _safe_appointment_context(form_data.get('Appointment_AppointmentID'), payment_id)

    return _render_form(
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        mode=mode,
        context=context,
        sale_options=_get_sale_options(exclude_sale_id=current_sale_id) if mode == 'sale' else [],
        appt_options=_get_appointment_options(current_appt_id=current_appt_id) if mode == 'appointment' else [],
        form_token=None,
        cancel_url=url_for('payment.index'),
    )


@bp.route('/delete/<int:payment_id>', methods=['POST'])
@login_required
def delete(payment_id):
    # Online payments are system records (Task 40): check before deleting.
    try:
        rows = (
            supabase.table('Payment')
            .select('PaymentID, Online_Order_OrderID, StripePaymentIntentID')
            .eq('PaymentID', payment_id)
            .execute()
        ).data or []
    except Exception as e:
        flash_error(f'Could not delete payment: {str(e)}')
        return redirect(url_for('payment.index'))
    if rows and _is_online_payment(rows[0]):
        flash_error(ONLINE_PAYMENT_LOCKED_MSG)
        return redirect(url_for('payment.index'))

    try:
        supabase.table('Payment').delete().eq('PaymentID', payment_id).execute()
        flash_success(f'Payment {payment_id} was deleted successfully.')
    except Exception as e:
        flash_error(f'Could not delete payment: {str(e)}')

    return redirect(url_for('payment.index'))