"""
Online Orders (Task 40, bike reservations Task 42).

Orders are created and paid by customers on the Client Side (Next.js + Stripe).
Staff can only view them, move them through the fulfilment workflow and cancel
them. There are no create, edit or delete routes, and audit columns are never
selected or shown.

Two order types share the table:
- Parts: spare parts with items, delivered or picked up (Task 40 workflow).
- Reservation: a 10% online deposit for one motorbike. The database creates a
  Sale (no employee) and a Deposit payment when Stripe confirms; the customer
  pays the balance and collects the bike at the dealership.
"""
from datetime import date, datetime, timedelta, timezone

from flask import render_template, request, redirect, url_for
from app.modules.online_order import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.order_ref import format_order_ref, parse_order_query


# Mauritius is UTC+4 all year (no DST).
MU_TZ = timezone(timedelta(hours=4))

STATUS_PENDING    = 'Pending Payment'
STATUS_PAID       = 'Paid'
STATUS_PROCESSING = 'Processing'
STATUS_READY      = 'Ready for Pickup'
STATUS_DELIVERY   = 'Out for Delivery'
STATUS_COMPLETED  = 'Completed'
STATUS_CANCELLED  = 'Cancelled'

STATUSES = [
    STATUS_PENDING, STATUS_PAID, STATUS_PROCESSING, STATUS_READY,
    STATUS_DELIVERY, STATUS_COMPLETED, STATUS_CANCELLED,
]
FULFILMENTS = ['Delivery', 'Pickup']

TYPE_PARTS       = 'Parts'
TYPE_RESERVATION = 'Reservation'
ORDER_TYPES = [TYPE_PARTS, TYPE_RESERVATION]
TYPE_LABELS = {TYPE_PARTS: 'Parts', TYPE_RESERVATION: 'Bike reservation'}

# Allowed status changes. Anything not listed here is refused.
TRANSITIONS = {
    STATUS_PAID:       [STATUS_PROCESSING],
    STATUS_PROCESSING: [STATUS_READY, STATUS_DELIVERY],
    STATUS_READY:      [STATUS_COMPLETED],
    STATUS_DELIVERY:   [STATUS_COMPLETED],
}

# Reservations: the customer collects the bike once the balance is paid.
RESERVATION_TRANSITIONS = {
    STATUS_PAID: [STATUS_COMPLETED],
}

# Targets that only make sense for one fulfilment method.
FULFILMENT_FOR_TARGET = {
    STATUS_READY:    'Pickup',
    STATUS_DELIVERY: 'Delivery',
}

# Statuses that mean the customer paid (a Payment row is expected).
PAID_OR_LATER = [STATUS_PAID, STATUS_PROCESSING, STATUS_READY, STATUS_DELIVERY, STATUS_COMPLETED]

# Cancellable without touching stock / with stock restored by the database.
CANCEL_UNPAID   = [STATUS_PENDING]
CANCEL_WITH_RPC = [STATUS_PAID, STATUS_PROCESSING]
# Reservations: a paid one is cancelled by cancel_bike_reservation.
RESERVATION_CANCEL_WITH_RPC = [STATUS_PAID]

# CSS class suffix per status (.oo-status-*)
STATUS_CSS = {
    STATUS_PENDING:    'pending',
    STATUS_PAID:       'paid',
    STATUS_PROCESSING: 'processing',
    STATUS_READY:      'ready',
    STATUS_DELIVERY:   'delivery',
    STATUS_COMPLETED:  'completed',
    STATUS_CANCELLED:  'cancelled',
}

# Button labels for each target status.
ACTION_LABELS = {
    STATUS_PROCESSING: ('Start Processing', 'fa-gears'),
    STATUS_READY:      ('Mark Ready for Pickup', 'fa-store'),
    STATUS_DELIVERY:   ('Mark Out for Delivery', 'fa-truck'),
    STATUS_COMPLETED:  ('Mark Completed', 'fa-circle-check'),
}
RESERVATION_COMPLETE_LABEL = ('Mark Collected (Completed)', 'fa-motorcycle')

# A Pending Payment order older than this has an expired Stripe session (30 min),
# so a still-pending order may hide a payment the webhook never confirmed.
STALE_PENDING_MINUTES = 60
CHECK_STRIPE_TOOLTIP = (
    'The checkout session has expired. If the customer was charged, the payment '
    'was not confirmed automatically; check the Stripe Dashboard.'
)

ORDER_CHANGED_MSG = 'This order has changed. Refresh and try again.'
STRIPE_REFUND_MSG = (
    'Order cancelled and stock restored. If the customer was charged, '
    'refund the payment in the Stripe Dashboard.'
)
BALANCE_DUE_MSG = 'Record the remaining payment on the Sale first.'
BALANCE_UNKNOWN_MSG = (
    'The balance due could not be worked out because the linked sale was not found. '
    'Check the Sale before completing this reservation.'
)
COLLECT_CONFIRM_TEXT = 'Confirm the customer has collected the motorcycle and the balance is paid.'
RESERVATION_CANCEL_WARNING = (
    'This frees the motorcycle and deletes the sale and the online deposit record. '
    'Refund the customer in the Stripe Dashboard.'
)

# Explicit column lists (no audit columns, no select *).
# Date_Created is the only audit column read, and only to work out the
# "Check Stripe" flag; it is stripped from every row before rendering.
ORDER_LIST_COLUMNS = (
    'OrderID, OrderDate, Customer_CustomerID, Status, FulfilmentMethod, '
    'EstimatedDate, TotalAmount, OrderType, BikeDescription, ReservedUntil, Date_Created'
)
ORDER_VIEW_COLUMNS = (
    'OrderID, OrderDate, Customer_CustomerID, Status, FulfilmentMethod, '
    'DeliveryStreet, DeliveryTown, DeliveryPostCode, DeliveryPhone, '
    'EstimatedDate, TotalAmount, PaidAt, OrderType, New_MotorBike_NB_ID, Sale_SaleID, '
    'BikeDescription, BikePrice, ReservedUntil, StripePaymentIntentID, Date_Created'
)
PAYMENT_COLUMNS = 'PaymentID, PaymentDate, AmountPaid, PaymentMethod, PaymentType, StripePaymentIntentID'

CUSTOMER_COLUMNS = 'CustomerID, FirstName, LastName, PhoneNumber, Email'

IN_CHUNK_SIZE = 100
PAGE_SIZE = 1000


# -- Pure helpers (unit tested) ------------------------------------------------

def order_type_of(order):
    """The order's type; rows without one are treated as parts orders."""
    return TYPE_RESERVATION if (order or {}).get('OrderType') == TYPE_RESERVATION else TYPE_PARTS


def allowed_next_statuses(status, fulfilment, order_type=TYPE_PARTS):
    """Statuses this order may move to next, given its type and fulfilment method."""
    if order_type == TYPE_RESERVATION:
        return list(RESERVATION_TRANSITIONS.get(status, []))
    return [
        target for target in TRANSITIONS.get(status, [])
        if FULFILMENT_FOR_TARGET.get(target, fulfilment) == fulfilment
    ]


def reservation_transition_error(status, new_status, balance_due):
    """
    Reason a reservation cannot move to new_status, or None. Completing needs the
    sale's balance due to be zero or less (balance_due None = unknown = refused).
    """
    if new_status not in STATUSES:
        return 'Please choose a valid status.'
    if new_status in RESERVATION_TRANSITIONS.get(status, []):
        if balance_due is None:
            return BALANCE_UNKNOWN_MSG
        if balance_due > 0.005:
            return BALANCE_DUE_MSG
        return None
    if status in (STATUS_COMPLETED, STATUS_CANCELLED):
        return f'This reservation is {status.lower()} and its status can no longer change.'
    if status == STATUS_PENDING:
        return 'The customer has not paid the deposit yet, so this reservation cannot change status.'
    return (f'A bike reservation cannot be marked "{new_status}". '
            'It can only be marked Completed once the customer has paid the balance and collected the motorcycle.')


def transition_error(status, fulfilment, new_status, order_type=TYPE_PARTS, balance_due=None):
    """Friendly reason why a status change is refused, or None if it is allowed."""
    if order_type == TYPE_RESERVATION:
        return reservation_transition_error(status, new_status, balance_due)
    if new_status not in STATUSES:
        return 'Please choose a valid status.'
    if new_status in allowed_next_statuses(status, fulfilment):
        return None
    needed = FULFILMENT_FOR_TARGET.get(new_status)
    if needed and needed != fulfilment and new_status in TRANSITIONS.get(status, []):
        method = 'store pickup' if needed == 'Pickup' else 'home delivery'
        return f'Only an order for {method} can be marked "{new_status}".'
    if status in (STATUS_COMPLETED, STATUS_CANCELLED):
        return f'This order is {status.lower()} and its status can no longer change.'
    return f'An order that is "{status}" cannot be moved to "{new_status}".'


def can_cancel(status, order_type=TYPE_PARTS):
    if order_type == TYPE_RESERVATION:
        return status in CANCEL_UNPAID or status in RESERVATION_CANCEL_WITH_RPC
    return status in CANCEL_UNPAID or status in CANCEL_WITH_RPC


def balance_due(sale_total, payments):
    """Sale total minus every payment recorded on the sale, rounded to cents."""
    paid = sum(float(p.get('AmountPaid') or 0) for p in payments)
    return round(float(sale_total or 0) - paid, 2)


def today_mauritius(now=None):
    return (now or datetime.now(MU_TZ)).astimezone(MU_TZ).date()


def _parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def is_overdue(order_type, status, reserved_until, today=None):
    """A paid reservation whose ReservedUntil date is before today (Mauritius)."""
    if order_type != TYPE_RESERVATION or status != STATUS_PAID:
        return False
    until = _parse_date(reserved_until)
    return until is not None and until < (today or today_mauritius())


def stripe_intent_for(order, payments):
    """The order's own StripePaymentIntentID, falling back to its payment rows."""
    if order.get('StripePaymentIntentID'):
        return order['StripePaymentIntentID']
    for p in payments:
        if p.get('StripePaymentIntentID'):
            return p['StripePaymentIntentID']
    return None


def lines_total(items):
    return round(sum(float(i.get('UnitPrice') or 0) * int(i.get('Quantity') or 0) for i in items), 2)


def to_mauritius_time(value):
    """ISO timestamp (any offset) -> 'YYYY-MM-DD HH:MM' in Mauritius time; None if missing."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return str(value)[:16].replace('T', ' ')
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(MU_TZ).strftime('%Y-%m-%d %H:%M')


def _parse_timestamp_utc(value):
    """ISO timestamp -> aware datetime (naive values are treated as UTC); None if unusable."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def needs_stripe_check(status, date_created, now=None):
    """
    True for a Pending Payment order created more than STALE_PENDING_MINUTES ago.
    Date_Created (UTC) is converted to Mauritius time and compared with the
    current Mauritius time. Every other status is never flagged.
    """
    if status != STATUS_PENDING:
        return False
    created = _parse_timestamp_utc(date_created)
    if created is None:
        return False
    created_mu = created.astimezone(MU_TZ)
    now_mu = (now or datetime.now(MU_TZ)).astimezone(MU_TZ)
    return now_mu - created_mu > timedelta(minutes=STALE_PENDING_MINUTES)


def _apply_stripe_flag(order, now=None):
    """Set order['_check_stripe'] and drop Date_Created so it can never be rendered."""
    order['_check_stripe'] = needs_stripe_check(order.get('Status'), order.get('Date_Created'), now)
    order.pop('Date_Created', None)
    return order


def reservation_rpc_error_message(error_text):
    """Map cancel_bike_reservation errors to friendly messages."""
    text = error_text or ''
    if 'SALE_HAS_PAYMENTS' in text:
        return 'Other payments were recorded on this sale. Resolve them manually before cancelling.'
    if 'NOT_CANCELLABLE' in text:
        return ('This reservation can no longer be cancelled here. Only reservations awaiting '
                'the deposit or paid (not yet collected) can be cancelled.')
    if 'ORDER_NOT_FOUND' in text:
        return 'This reservation was not found. It may have been removed.'
    if 'NOT_STAFF' in text:
        return 'Only staff members can cancel reservations. Sign in with a staff account.'
    return 'Could not cancel the reservation. Please try again.'


def rpc_error_message(error_text):
    """Map cancel_paid_online_order errors to friendly messages."""
    text = error_text or ''
    if 'NOT_CANCELLABLE' in text:
        return ('This order can no longer be cancelled here. Only paid or processing '
                'orders can be cancelled with a stock refund.')
    if 'ORDER_NOT_FOUND' in text:
        return 'This order was not found. It may have been removed.'
    if 'NOT_STAFF' in text:
        return 'Only staff members can cancel paid orders. Sign in with a staff account.'
    return 'Could not cancel the order. Please try again.'


# -- Data helpers ------------------------------------------------------------

def _chunks(values, size=IN_CHUNK_SIZE):
    values = list(values)
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _customer_lookup(customer_ids):
    """{CustomerID: row} with one .in_() query per 100 ids."""
    ids = sorted({i for i in customer_ids if i is not None})
    found = {}
    for chunk in _chunks(ids):
        try:
            result = (
                supabase.table('Customer')
                .select(CUSTOMER_COLUMNS)
                .in_('CustomerID', chunk)
                .execute()
            )
            for row in (result.data or []):
                found[row['CustomerID']] = row
        except Exception:
            continue
    return found


def _full_name(customer):
    if not customer:
        return 'Unknown customer'
    return f"{customer.get('FirstName') or ''} {customer.get('LastName') or ''}".strip() or 'Unknown customer'


def _fetch_orders(status_filter, fulfilment_filter, type_filter=''):
    """All orders matching the (whitelisted) filters, newest first, paged past the row cap."""
    rows = []
    start = 0
    while True:
        query = supabase.table('Online_Order').select(ORDER_LIST_COLUMNS)
        if status_filter:
            query = query.eq('Status', status_filter)
        if fulfilment_filter:
            query = query.eq('FulfilmentMethod', fulfilment_filter)
        if type_filter:
            query = query.eq('OrderType', type_filter)
        batch = (
            query.order('OrderDate', desc=True)
            .order('OrderID', desc=True)
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        ).data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def _matches_search(order, query_text, query_order_id):
    """Order number, customer first or last name, or phone (case-insensitive)."""
    if query_order_id is not None and order.get('OrderID') == query_order_id:
        return True
    needle = query_text.lower()
    customer = order.get('_customer') or {}
    for field in ('FirstName', 'LastName'):
        if needle in str(customer.get(field) or '').lower():
            return True
    if needle in _full_name(customer).lower():
        return True
    digits = ''.join(ch for ch in query_text if ch.isdigit())
    phone = ''.join(ch for ch in str(customer.get('PhoneNumber') or '') if ch.isdigit())
    return len(digits) >= 3 and digits in phone


def _get_order(order_id):
    """The order row, or None when it does not exist."""
    result = (
        supabase.table('Online_Order')
        .select(ORDER_VIEW_COLUMNS)
        .eq('OrderID', order_id)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def _view_url(order_id):
    return url_for('online_order.view', order_id=order_id)


def _get_sale(sale_id):
    """(sale row or None, payments on the sale). Raises on a database error."""
    if not sale_id:
        return None, []
    rows = (
        supabase.table('Sale')
        .select('SaleID, SaleDate, TotalAmount')
        .eq('SaleID', sale_id)
        .limit(1)
        .execute()
    ).data or []
    payments = (
        supabase.table('Payment')
        .select(PAYMENT_COLUMNS)
        .eq('Sale_SaleID', sale_id)
        .order('PaymentID')
        .execute()
    ).data or []
    return (rows[0] if rows else None), payments


def _reservation_balance(order):
    """Balance due on the reservation's sale, or None when it cannot be worked out."""
    try:
        sale, payments = _get_sale(order.get('Sale_SaleID'))
    except Exception:
        return None
    if sale is None:
        return None
    return balance_due(sale.get('TotalAmount'), payments)


# -- Routes ---------------------------------------------------------------------

@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()[:60]
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '').strip()
    fulfilment_filter = request.args.get('fulfilment', '').strip()
    type_filter = request.args.get('type', '').strip()
    if status_filter not in STATUSES:
        status_filter = ''
    if fulfilment_filter not in FULFILMENTS:
        fulfilment_filter = ''
    if type_filter not in ORDER_TYPES:
        type_filter = ''

    try:
        records = _fetch_orders(status_filter, fulfilment_filter, type_filter)
    except Exception as e:
        flash_error(f'Could not load online orders: {str(e)}')
        records = []

    customers = _customer_lookup(r.get('Customer_CustomerID') for r in records)
    now = datetime.now(MU_TZ)
    today = today_mauritius(now)
    for r in records:
        _apply_stripe_flag(r, now)
        r['_type'] = order_type_of(r)
        r['_type_label'] = TYPE_LABELS[r['_type']]
        r['_overdue'] = is_overdue(r['_type'], r.get('Status'), r.get('ReservedUntil'), today)
        r['_customer'] = customers.get(r.get('Customer_CustomerID'))
        r['_customer_name'] = _full_name(r['_customer'])
        r['_status_css'] = STATUS_CSS.get(r.get('Status'), 'pending')

    if search_query:
        order_id = parse_order_query(search_query)
        records = [r for r in records if _matches_search(r, search_query, order_id)]

    pagination = paginate(records, page, per_page=10)

    return render_template(
        'modules/online_order/list.html',
        pagination=pagination,
        search_query=search_query,
        status_filter=status_filter,
        fulfilment_filter=fulfilment_filter,
        type_filter=type_filter,
        statuses=STATUSES,
        fulfilments=FULFILMENTS,
        order_types=[(t, TYPE_LABELS[t]) for t in ORDER_TYPES],
        check_stripe_tooltip=CHECK_STRIPE_TOOLTIP,
    )


@bp.route('/view/<int:order_id>')
@login_required
def view(order_id):
    try:
        order = _get_order(order_id)
    except Exception as e:
        flash_error(f'Could not load the online order: {str(e)}')
        return redirect(url_for('online_order.index'))
    if order is None:
        flash_error(f'Online order ID {order_id} was not found.')
        return redirect(url_for('online_order.index'))
    _apply_stripe_flag(order)

    customer = _customer_lookup([order.get('Customer_CustomerID')]).get(order.get('Customer_CustomerID'))
    if order_type_of(order) == TYPE_RESERVATION:
        return _render_reservation(order_id, order, customer)

    try:
        items = (
            supabase.table('Online_Order_Item')
            .select('OrderItemID, Stock_Stock_ID, ItemDescription, Quantity, UnitPrice')
            .eq('Online_Order_OrderID', order_id)
            .order('OrderItemID')
            .execute()
        ).data or []
    except Exception:
        items = []
        flash_error('Could not load the items of this order.')

    try:
        payments = (
            supabase.table('Payment')
            .select(PAYMENT_COLUMNS)
            .eq('Online_Order_OrderID', order_id)
            .order('PaymentID')
            .execute()
        ).data or []
    except Exception:
        payments = []
        flash_error('Could not load the payments of this order.')

    for i in items:
        i['_line_total'] = float(i.get('UnitPrice') or 0) * int(i.get('Quantity') or 0)

    status = order.get('Status')
    fulfilment = order.get('FulfilmentMethod')
    total = float(order.get('TotalAmount') or 0)
    items_sum = lines_total(items)
    next_statuses = allowed_next_statuses(status, fulfilment)

    return render_template(
        'modules/online_order/view.html',
        order=order,
        order_ref=format_order_ref(order_id),
        is_reservation=False,
        customer=customer,
        customer_name=_full_name(customer),
        items=items,
        items_sum=items_sum,
        total=total,
        sum_mismatch=bool(items) and abs(items_sum - total) > 0.005,
        payments=payments,
        missing_payment=status in PAID_OR_LATER and not payments,
        refund_reminder=status == STATUS_CANCELLED and bool(payments or order.get('StripePaymentIntentID')),
        stripe_intent=stripe_intent_for(order, payments),
        paid_at=to_mauritius_time(order.get('PaidAt')),
        status_css=STATUS_CSS.get(status, 'pending'),
        check_stripe=order['_check_stripe'],
        check_stripe_tooltip=CHECK_STRIPE_TOOLTIP,
        next_actions=[(s, *ACTION_LABELS[s]) for s in next_statuses],
        can_cancel=can_cancel(status),
        cancel_restores_stock=status in CANCEL_WITH_RPC,
    )


def _render_reservation(order_id, order, customer):
    """View page for a bike reservation: the Reservation card replaces the items."""
    status = order.get('Status')
    sale_id = order.get('Sale_SaleID')
    sale, sale_payments, sale_error = None, [], False
    try:
        sale, sale_payments = _get_sale(sale_id)
    except Exception:
        sale_error = True
        flash_error('Could not load the sale and payments of this reservation.')

    balance = balance_due(sale.get('TotalAmount'), sale_payments) if sale else None
    next_statuses = allowed_next_statuses(status, order.get('FulfilmentMethod'), TYPE_RESERVATION)
    show_complete = STATUS_COMPLETED in next_statuses

    return render_template(
        'modules/online_order/view.html',
        order=order,
        order_ref=format_order_ref(order_id),
        is_reservation=True,
        customer=customer,
        customer_name=_full_name(customer),
        total=float(order.get('TotalAmount') or 0),
        bike_price=float(order['BikePrice']) if order.get('BikePrice') is not None else None,
        sale=sale,
        sale_id=sale_id,
        sale_total=float(sale.get('TotalAmount') or 0) if sale else None,
        sale_paid=round(sum(float(p.get('AmountPaid') or 0) for p in sale_payments), 2),
        balance_due=balance,
        overdue=is_overdue(TYPE_RESERVATION, status, order.get('ReservedUntil')),
        payments=sale_payments,
        missing_payment=(status in (STATUS_PAID, STATUS_COMPLETED) and not sale_error
                         and not sale_payments),
        refund_reminder=status == STATUS_CANCELLED and bool(order.get('StripePaymentIntentID')),
        stripe_intent=stripe_intent_for(order, sale_payments),
        paid_at=to_mauritius_time(order.get('PaidAt')),
        status_css=STATUS_CSS.get(status, 'pending'),
        check_stripe=order['_check_stripe'],
        check_stripe_tooltip=CHECK_STRIPE_TOOLTIP,
        next_actions=[],
        show_complete=show_complete,
        can_complete=show_complete and balance is not None and balance <= 0.005,
        complete_label=RESERVATION_COMPLETE_LABEL,
        collect_confirm_text=COLLECT_CONFIRM_TEXT,
        balance_block_msg=BALANCE_DUE_MSG if balance is not None else BALANCE_UNKNOWN_MSG,
        can_cancel=can_cancel(status, TYPE_RESERVATION),
        cancel_paid_reservation=status in RESERVATION_CANCEL_WITH_RPC,
        reservation_cancel_warning=RESERVATION_CANCEL_WARNING,
    )


@bp.route('/<int:order_id>/status', methods=['POST'])
@login_required
def change_status(order_id):
    new_status = request.form.get('new_status', '').strip()
    expected = request.form.get('expected_status', '').strip()

    try:
        order = _get_order(order_id)
    except Exception as e:
        flash_error(f'Could not load the online order: {str(e)}')
        return redirect(url_for('online_order.index'))
    if order is None:
        flash_error(f'Online order ID {order_id} was not found.')
        return redirect(url_for('online_order.index'))

    current = order.get('Status')
    # The page was loaded for a different status: someone else changed the order.
    if expected and expected != current:
        flash_error(ORDER_CHANGED_MSG)
        return redirect(_view_url(order_id))

    order_type = order_type_of(order)
    balance = None
    if order_type == TYPE_RESERVATION and new_status in RESERVATION_TRANSITIONS.get(current, []):
        balance = _reservation_balance(order)

    reason = transition_error(current, order.get('FulfilmentMethod'), new_status, order_type, balance)
    if reason:
        flash_error(reason)
        return redirect(_view_url(order_id))

    try:
        updated = (
            supabase.table('Online_Order')
            .update({'Status': new_status})
            .eq('OrderID', order_id)
            .eq('Status', current)
            .execute()
        )
    except Exception as e:
        flash_error(f'Could not update the order: {str(e)}')
        return redirect(_view_url(order_id))

    if updated.data and order_type == TYPE_RESERVATION:
        flash_success(f'{format_order_ref(order_id)} is completed: the motorcycle was collected.')
    elif updated.data:
        flash_success(f'{format_order_ref(order_id)} is now "{new_status}".')
    else:
        flash_error(ORDER_CHANGED_MSG)
    return redirect(_view_url(order_id))


@bp.route('/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel(order_id):
    expected = request.form.get('expected_status', '').strip()

    try:
        order = _get_order(order_id)
    except Exception as e:
        flash_error(f'Could not load the online order: {str(e)}')
        return redirect(url_for('online_order.index'))
    if order is None:
        flash_error(f'Online order ID {order_id} was not found.')
        return redirect(url_for('online_order.index'))

    current = order.get('Status')
    if expected and expected != current:
        flash_error(ORDER_CHANGED_MSG)
        return redirect(_view_url(order_id))

    ref = format_order_ref(order_id)
    if order_type_of(order) == TYPE_RESERVATION:
        return _cancel_reservation(order_id, order, current, ref)

    if current in CANCEL_UNPAID:
        # Nothing was charged and no stock was taken: a plain conditional update.
        try:
            updated = (
                supabase.table('Online_Order')
                .update({'Status': STATUS_CANCELLED})
                .eq('OrderID', order_id)
                .eq('Status', current)
                .execute()
            )
        except Exception as e:
            flash_error(f'Could not cancel the order: {str(e)}')
            return redirect(_view_url(order_id))
        if updated.data:
            flash_success(f'{ref} was cancelled. The customer had not paid, so no refund is needed.')
        else:
            flash_error(ORDER_CHANGED_MSG)
        return redirect(_view_url(order_id))

    if current in CANCEL_WITH_RPC:
        # The database function restores stock and cancels atomically.
        try:
            result = supabase.rpc('cancel_paid_online_order', {'p_order_id': order_id}).execute()
        except Exception as e:
            flash_error(rpc_error_message(str(e)))
            return redirect(_view_url(order_id))
        if result.data is True:
            flash_success(STRIPE_REFUND_MSG)
        else:
            flash_error(ORDER_CHANGED_MSG)
        return redirect(_view_url(order_id))

    flash_error(
        f'An order that is "{current}" cannot be cancelled here. Only orders awaiting '
        'payment, paid or processing can be cancelled.'
    )
    return redirect(_view_url(order_id))


def _cancel_reservation(order_id, order, current, ref):
    """Cancel a bike reservation: unpaid by conditional update, paid by the database function."""
    if current in CANCEL_UNPAID:
        # No sale or payment exists before the deposit is paid.
        try:
            updated = (
                supabase.table('Online_Order')
                .update({'Status': STATUS_CANCELLED})
                .eq('OrderID', order_id)
                .eq('Status', current)
                .execute()
            )
        except Exception as e:
            flash_error(f'Could not cancel the reservation: {str(e)}')
            return redirect(_view_url(order_id))
        if updated.data:
            flash_success(f'{ref} was cancelled. The customer had not paid the deposit, so no refund is needed.')
        else:
            flash_error(ORDER_CHANGED_MSG)
        return redirect(_view_url(order_id))

    if current in RESERVATION_CANCEL_WITH_RPC:
        # Deletes the deposit payment and the sale, frees the bike and cancels, atomically.
        try:
            result = supabase.rpc('cancel_bike_reservation', {'p_order_id': order_id}).execute()
        except Exception as e:
            flash_error(reservation_rpc_error_message(str(e)))
            return redirect(_view_url(order_id))
        if result.data is False:
            flash_error(ORDER_CHANGED_MSG)
            return redirect(_view_url(order_id))
        intent = order.get('StripePaymentIntentID')
        where = f' (payment intent {intent})' if intent else ''
        flash_success(
            f'{ref} was cancelled: the motorcycle is available again and the sale and online deposit '
            f'were removed. Refund the deposit in the Stripe Dashboard{where}.'
        )
        return redirect(_view_url(order_id))

    flash_error(
        f'A reservation that is "{current}" cannot be cancelled here. Only reservations awaiting '
        'the deposit or paid (not yet collected) can be cancelled.'
    )
    return redirect(_view_url(order_id))
