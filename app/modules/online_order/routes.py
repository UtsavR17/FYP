"""
Online Orders (Task 40).

Orders are created and paid by customers on the Client Side (Next.js + Stripe).
Staff can only view them, move them through the fulfilment workflow and cancel
them. There are no create, edit or delete routes, and audit columns are never
selected or shown.
"""
from datetime import datetime, timedelta, timezone

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

# Allowed status changes. Anything not listed here is refused.
TRANSITIONS = {
    STATUS_PAID:       [STATUS_PROCESSING],
    STATUS_PROCESSING: [STATUS_READY, STATUS_DELIVERY],
    STATUS_READY:      [STATUS_COMPLETED],
    STATUS_DELIVERY:   [STATUS_COMPLETED],
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

# Explicit column lists (no audit columns, no select *).
# Date_Created is the only audit column read, and only to work out the
# "Check Stripe" flag; it is stripped from every row before rendering.
ORDER_LIST_COLUMNS = (
    'OrderID, OrderDate, Customer_CustomerID, Status, FulfilmentMethod, '
    'EstimatedDate, TotalAmount, Date_Created'
)
ORDER_VIEW_COLUMNS = (
    'OrderID, OrderDate, Customer_CustomerID, Status, FulfilmentMethod, '
    'DeliveryStreet, DeliveryTown, DeliveryPostCode, DeliveryPhone, '
    'EstimatedDate, TotalAmount, PaidAt, Date_Created'
)
CUSTOMER_COLUMNS = 'CustomerID, FirstName, LastName, PhoneNumber, Email'

IN_CHUNK_SIZE = 100
PAGE_SIZE = 1000


# -- Pure helpers (unit tested) ------------------------------------------------

def allowed_next_statuses(status, fulfilment):
    """Statuses this order may move to next, given its fulfilment method."""
    return [
        target for target in TRANSITIONS.get(status, [])
        if FULFILMENT_FOR_TARGET.get(target, fulfilment) == fulfilment
    ]


def transition_error(status, fulfilment, new_status):
    """Friendly reason why a status change is refused, or None if it is allowed."""
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


def can_cancel(status):
    return status in CANCEL_UNPAID or status in CANCEL_WITH_RPC


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


def _fetch_orders(status_filter, fulfilment_filter):
    """All orders matching the (whitelisted) filters, newest first, paged past the row cap."""
    rows = []
    start = 0
    while True:
        query = supabase.table('Online_Order').select(ORDER_LIST_COLUMNS)
        if status_filter:
            query = query.eq('Status', status_filter)
        if fulfilment_filter:
            query = query.eq('FulfilmentMethod', fulfilment_filter)
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


# -- Routes ---------------------------------------------------------------------

@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()[:60]
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '').strip()
    fulfilment_filter = request.args.get('fulfilment', '').strip()
    if status_filter not in STATUSES:
        status_filter = ''
    if fulfilment_filter not in FULFILMENTS:
        fulfilment_filter = ''

    try:
        records = _fetch_orders(status_filter, fulfilment_filter)
    except Exception as e:
        flash_error(f'Could not load online orders: {str(e)}')
        records = []

    customers = _customer_lookup(r.get('Customer_CustomerID') for r in records)
    now = datetime.now(MU_TZ)
    for r in records:
        _apply_stripe_flag(r, now)
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
        statuses=STATUSES,
        fulfilments=FULFILMENTS,
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
            .select('PaymentID, PaymentDate, AmountPaid, PaymentMethod, PaymentType, StripePaymentIntentID')
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
        customer=customer,
        customer_name=_full_name(customer),
        items=items,
        items_sum=items_sum,
        total=total,
        sum_mismatch=bool(items) and abs(items_sum - total) > 0.005,
        payments=payments,
        missing_payment=status in PAID_OR_LATER and not payments,
        refund_reminder=status == STATUS_CANCELLED and bool(payments),
        paid_at=to_mauritius_time(order.get('PaidAt')),
        status_css=STATUS_CSS.get(status, 'pending'),
        check_stripe=order['_check_stripe'],
        check_stripe_tooltip=CHECK_STRIPE_TOOLTIP,
        next_actions=[(s, *ACTION_LABELS[s]) for s in next_statuses],
        can_cancel=can_cancel(status),
        cancel_restores_stock=status in CANCEL_WITH_RPC,
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

    reason = transition_error(current, order.get('FulfilmentMethod'), new_status)
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

    if updated.data:
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
