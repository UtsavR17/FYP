import re
from datetime import date, datetime, timedelta, timezone

from flask import render_template, session, url_for
from app.dashboard import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.order_ref import format_order_ref


# -- Dashboard settings (Task 34) --------------------------------------------

# Mauritius is UTC+4 all year (no DST). A fixed offset avoids needing
# zoneinfo/tzdata on Windows.
MU_TZ = timezone(timedelta(hours=4))

# Stock at or below this quantity on hand counts as "low stock".
LOW_STOCK_THRESHOLD = 5

CHART_MONTHS = 6       # months shown on the sales line chart
TABLE_LIMIT = 5        # rows shown in each "needs attention" table
IN_CHUNK_SIZE = 100    # max ids per .in_() lookup
PAGE_SIZE = 1000       # PostgREST default max rows per request

APPOINTMENT_STATUSES = [
    'Pending', 'Confirmed', 'In Progress', 'Completed', 'Cancelled', 'No Show',
]
UPCOMING_STATUSES = ['Pending', 'Confirmed', 'In Progress']
OPEN_PO_STATUSES = ['Pending', 'Partially Received']

# Online parts orders that count as sales (the customer has paid; Task 42).
ONLINE_PARTS_SOLD_STATUSES = [
    'Paid', 'Processing', 'Ready for Pickup', 'Out for Delivery', 'Completed',
]


def _get_dashboard_counts():
    """
    Query the total record count for each Phase 1 table.
    Each query is wrapped individually so a single failure
    does not crash the entire dashboard.
    Returns a dict mapping a short key to an integer count.
    """
    queries = [
        ('color',       'Color'),
        ('category',    'Category'),
        ('brand',       'Brand'),
        ('model',       'Model'),
        ('spare_parts', 'Spare_Parts'),
        ('stock',       'Stock'),
        ('service',     'Service'),
        ('role',        'Role'),
        ('employee',    'Employee'),
        ('supplier',    'Supplier'),
        ('compatibility', 'Compatibility'),
        ('purchase_order', 'PurchaseOrder'),
        ('customer', 'Customer'),
        ('customer_bike', 'Customer_bike'),
        ('new_motorbike', 'New_MotorBike'),
        ('appointment', 'Appointment'),
        ('sale','Sale'),
        ('payment', 'Payment'),
        ('online_order', 'Online_Order'),
        ('supplier_application', 'Supplier_Application'),
    ]

    counts = {}
    for key, table_name in queries:
        try:
            result = supabase.table(table_name).select(
                '*', count='exact'
            ).execute()
            counts[key] = result.count if result.count is not None else 0
        except Exception:
            counts[key] = 0

    # Online orders waiting for staff (Task 40, split by type in Task 42).
    # Each count has its own try, like every count.
    try:
        result = (
            supabase.table('Online_Order')
            .select('OrderID', count='exact')
            .eq('OrderType', 'Parts')
            .eq('Status', 'Paid')
            .execute()
        )
        counts['online_order_to_process'] = result.count or 0
    except Exception:
        counts['online_order_to_process'] = 0

    try:
        result = (
            supabase.table('Online_Order')
            .select('OrderID', count='exact')
            .eq('OrderType', 'Reservation')
            .eq('Status', 'Paid')
            .execute()
        )
        counts['online_order_reserved'] = result.count or 0
    except Exception:
        counts['online_order_reserved'] = 0

    try:
        result = (
            supabase.table('Online_Order')
            .select('OrderID', count='exact')
            .eq('OrderType', 'Reservation')
            .eq('Status', 'Paid')
            .lt('ReservedUntil', _today().isoformat())
            .execute()
        )
        counts['online_order_overdue'] = result.count or 0
    except Exception:
        counts['online_order_overdue'] = 0

    # Supplier applications waiting for review (Task 46). Its own try, like every count.
    try:
        result = (
            supabase.table('Supplier_Application')
            .select('ApplicationID', count='exact')
            .eq('Status', 'Pending')
            .execute()
        )
        counts['supplier_application_pending'] = result.count or 0
    except Exception:
        counts['supplier_application_pending'] = 0

    # Online bookings waiting for confirmation (Task 44): Pending with no employee.
    try:
        result = (
            supabase.table('Appointment')
            .select('AppointmentID', count='exact')
            .eq('Status', 'Pending')
            .is_('Employee_EmployeeID', 'null')
            .execute()
        )
        counts['appointment_to_confirm'] = result.count or 0
    except Exception:
        counts['appointment_to_confirm'] = 0

    return counts


# -- Small helpers -------------------------------------------------------------

def _today():
    """Today's date in Mauritius time."""
    return datetime.now(MU_TZ).date()


def _shift_month(year, month, delta):
    """Return (year, month) moved by delta months."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _parse_date(value):
    """Parse 'YYYY-MM-DD' (or an ISO timestamp) into a date, else None."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _to_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _mauritius_date(value):
    """ISO timestamp (naive = UTC) -> its calendar date in Mauritius time, else None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(MU_TZ).date()


def _format_mur(amount):
    """Full money format: 'MUR 428,500.00'."""
    return f'MUR {amount:,.2f}'


def _format_mur_compact(amount):
    """Compact money format for KPI cards: 'MUR 428.5K', 'MUR 1.2M'."""
    for limit, suffix in ((1_000_000, 'M'), (1_000, 'K')):
        if abs(amount) >= limit:
            short = f'{amount / limit:.1f}'.rstrip('0').rstrip('.')
            return f'MUR {short}{suffix}'
    return _format_mur(amount)


def _format_short_date(d, today):
    """'2 Oct', with the year added when it is not the current year."""
    if not d:
        return '-'
    label = f'{d.day} {d:%b}'
    return label if d.year == today.year else f'{label} {d.year}'


def _chunks(values, size=IN_CHUNK_SIZE):
    values = list(values)
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _fetch_all(build_query):
    """
    Run a select and keep paging with .range() until every row is read,
    so tables larger than the PostgREST row cap are not silently cut off.
    build_query must return a fresh, ordered query builder each call.
    """
    rows = []
    start = 0
    while True:
        batch = build_query().range(start, start + PAGE_SIZE - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def _lookup(table, key_column, columns, ids):
    """
    Resolve related rows with one .in_() query per 100 ids.
    Returns {key: row}. A failing chunk is skipped, not raised.
    """
    ids = sorted({i for i in ids if i is not None})
    found = {}
    for chunk in _chunks(ids):
        try:
            result = (
                supabase.table(table)
                .select(columns)
                .in_(key_column, chunk)
                .execute()
            )
            for row in (result.data or []):
                found[row[key_column]] = row
        except Exception:
            continue
    return found


def _welcome_name():
    """
    The session only stores the user's email, so the welcome name is the
    first alphabetic part of the email's local part, title-cased
    (e.g. 'utsav.ramjattan@x.com' -> 'Utsav'). Falls back to 'Admin'.
    """
    email = (session.get('user_email') or '').strip()
    local = email.split('@', 1)[0] if email else ''
    parts = [p for p in re.split(r'[^A-Za-z]+', local) if p]
    if parts:
        return parts[0].title()
    return local.title() if local else 'Admin'


# -- Data helpers --------------------------------------------------------------

def _get_appointment_summary(today, window_start, window_end):
    """
    One paged query over Appointment (id, date, status) feeds three widgets:
    today's appointment KPI, the status donut, and the list of Completed
    appointments inside the chart window (used for parts sales).
    """
    summary = {
        'today_count': 0,
        'status_counts': {s: 0 for s in APPOINTMENT_STATUSES},
        'completed_in_window': {},   # AppointmentID -> date
    }
    try:
        rows = _fetch_all(lambda: (
            supabase.table('Appointment')
            .select('AppointmentID, Appointment_Date, Status')
            .order('AppointmentID')
        ))
    except Exception:
        return summary

    for row in rows:
        status = row.get('Status')
        appt_date = _parse_date(row.get('Appointment_Date'))
        if status in summary['status_counts']:
            summary['status_counts'][status] += 1
        if appt_date == today and status != 'Cancelled':
            summary['today_count'] += 1
        if (status == 'Completed' and appt_date
                and window_start <= appt_date < window_end):
            summary['completed_in_window'][row['AppointmentID']] = appt_date

    return summary


def _get_bikes_available_count():
    try:
        result = (
            supabase.table('New_MotorBike')
            .select('NB_ID', count='exact')
            .eq('Status', 'Available')
            .limit(1)
            .execute()
        )
        return result.count or 0
    except Exception:
        return 0


def _get_payments_this_month(today):
    """SUM(AmountPaid) for payments dated in the current calendar month."""
    month_start = today.replace(day=1)
    next_year, next_month = _shift_month(today.year, today.month, 1)
    month_end = date(next_year, next_month, 1)
    try:
        rows = _fetch_all(lambda: (
            supabase.table('Payment')
            .select('PaymentID, AmountPaid')
            .gte('PaymentDate', month_start.isoformat())
            .lt('PaymentDate', month_end.isoformat())
            .order('PaymentID')
        ))
    except Exception:
        return 0.0
    return sum(_to_float(r.get('AmountPaid')) for r in rows)


def _get_chart_months(today):
    """The last CHART_MONTHS calendar months, oldest first, as (year, month)."""
    return [
        _shift_month(today.year, today.month, offset)
        for offset in range(-(CHART_MONTHS - 1), 1)
    ]


def _get_sales_series(months, window_start, window_end, completed_in_window):
    """
    Monthly motorcycle sales and parts sales (MUR) for the line chart.

    Motorcycle sales: SUM(Sale.TotalAmount) by month of SaleDate.
    Parts sales: there is no parts-sales table, so this is the value of
    spare parts used in Completed appointments:
    SUM(Appointment_Stock.Quantity * Stock.S_Price) by month of
    Appointment_Date. Note: S_Price is the CURRENT selling price; the
    schema keeps no price snapshot per appointment.
    Plus online parts orders (Task 42): SUM(Online_Order.TotalAmount) for
    OrderType 'Parts' in a paid status, by the Mauritius month of PaidAt.
    Reservations are not added here: their Sale is in the motorcycle series.
    """
    index = {ym: i for i, ym in enumerate(months)}
    motorcycle = [0.0] * len(months)
    parts = [0.0] * len(months)

    try:
        sales = _fetch_all(lambda: (
            supabase.table('Sale')
            .select('SaleID, SaleDate, TotalAmount')
            .gte('SaleDate', window_start.isoformat())
            .lt('SaleDate', window_end.isoformat())
            .order('SaleID')
        ))
    except Exception:
        sales = []

    for sale in sales:
        sale_date = _parse_date(sale.get('SaleDate'))
        slot = index.get((sale_date.year, sale_date.month)) if sale_date else None
        if slot is not None:
            motorcycle[slot] += _to_float(sale.get('TotalAmount'))

    usage = []
    for chunk in _chunks(completed_in_window.keys()):
        try:
            result = (
                supabase.table('Appointment_Stock')
                .select('Appointment_AppointmentID, Stock_Stock_ID, Quantity')
                .in_('Appointment_AppointmentID', chunk)
                .execute()
            )
            usage.extend(result.data or [])
        except Exception:
            continue

    prices = _lookup(
        'Stock', 'Stock_ID', 'Stock_ID, S_Price',
        (u.get('Stock_Stock_ID') for u in usage),
    )

    for u in usage:
        appt_date = completed_in_window.get(u.get('Appointment_AppointmentID'))
        slot = index.get((appt_date.year, appt_date.month)) if appt_date else None
        if slot is None:
            continue
        price = _to_float(prices.get(u.get('Stock_Stock_ID'), {}).get('S_Price'))
        parts[slot] += _to_float(u.get('Quantity')) * price

    for month_index, amount in _get_online_parts_by_month(index, window_start, window_end):
        parts[month_index] += amount

    return [round(v, 2) for v in motorcycle], [round(v, 2) for v in parts]


def _get_online_parts_by_month(index, window_start, window_end):
    """
    [(chart slot, TotalAmount)] for paid online parts orders. The query is one
    day wider than the window on each side (PaidAt is stored in UTC); the
    Mauritius month of PaidAt then decides the slot exactly.
    """
    try:
        orders = _fetch_all(lambda: (
            supabase.table('Online_Order')
            .select('OrderID, PaidAt, TotalAmount')
            .eq('OrderType', 'Parts')
            .in_('Status', ONLINE_PARTS_SOLD_STATUSES)
            .gte('PaidAt', (window_start - timedelta(days=1)).isoformat())
            .lt('PaidAt', (window_end + timedelta(days=1)).isoformat())
            .order('OrderID')
        ))
    except Exception:
        return []

    out = []
    for o in orders:
        paid_on = _mauritius_date(o.get('PaidAt'))
        slot = index.get((paid_on.year, paid_on.month)) if paid_on else None
        if slot is not None:
            out.append((slot, _to_float(o.get('TotalAmount'))))
    return out


def _get_month_labels(months):
    """'May', 'Jun'... or 'Dec 25', 'Jan 26' when the window spans two years."""
    spans_years = months[0][0] != months[-1][0]
    labels = []
    for year, month in months:
        d = date(year, month, 1)
        labels.append(f'{d:%b %y}' if spans_years else f'{d:%b}')
    return labels


def _get_upcoming_appointments(today):
    """Next TABLE_LIMIT open appointments from today onwards."""
    try:
        result = (
            supabase.table('Appointment')
            .select('AppointmentID, Appointment_Date, Appointment_time, '
                    'AppointmentType, Status, Customer_bike_BikeID, Employee_EmployeeID')
            .gte('Appointment_Date', today.isoformat())
            .in_('Status', UPCOMING_STATUSES)
            .order('Appointment_Date')
            .order('Appointment_time')
            .order('AppointmentID')
            .limit(TABLE_LIMIT)
            .execute()
        )
        rows = result.data or []
    except Exception:
        return []

    bikes = _lookup(
        'Customer_bike', 'BikeID',
        'BikeID, RegistrationNumber, Customer_CustomerID',
        (r.get('Customer_bike_BikeID') for r in rows),
    )
    customers = _lookup(
        'Customer', 'CustomerID', 'CustomerID, FirstName, LastName',
        (b.get('Customer_CustomerID') for b in bikes.values()),
    )

    items = []
    for r in rows:
        appt_date = _parse_date(r.get('Appointment_Date'))
        time_label = str(r.get('Appointment_time') or '')[:5]
        if appt_date == today:
            when = time_label or 'Today'
        else:
            when = f"{appt_date:%d %b} {time_label}".strip() if appt_date else '-'

        bike = bikes.get(r.get('Customer_bike_BikeID'), {})
        customer = customers.get(bike.get('Customer_CustomerID'), {})
        first = (customer.get('FirstName') or '').strip()
        last = (customer.get('LastName') or '').strip()
        name = f'{first} {last[:1]}.' if first and last else (first or last or '-')

        items.append({
            'id': r['AppointmentID'],
            'when': when,
            'is_today': appt_date == today,
            'customer': name,
            'bike': bike.get('RegistrationNumber') or '-',
            'type': r.get('AppointmentType') or '-',
            'status': r.get('Status') or '-',
            'unassigned': r.get('Employee_EmployeeID') is None,
            'url': url_for('appointment.view', appt_id=r['AppointmentID']),
        })
    return items


def _get_open_purchase_orders(today):
    """Pending / Partially Received POs, soonest expected first (nulls last)."""
    try:
        # Postgres sorts NULLs last on ascending order by default.
        result = (
            supabase.table('PurchaseOrder')
            .select('PurchaseOrderID, ExpectedDate, Status, Supplier_SupplierID, SupplierStage')
            .in_('Status', OPEN_PO_STATUSES)
            .order('ExpectedDate')
            .order('PurchaseOrderID')
            .limit(TABLE_LIMIT)
            .execute()
        )
        rows = result.data or []
    except Exception:
        return []

    suppliers = _lookup(
        'Supplier', 'SupplierID', 'SupplierID, SupplierName',
        (r.get('Supplier_SupplierID') for r in rows),
    )

    items = []
    for r in rows:
        expected = _parse_date(r.get('ExpectedDate'))
        items.append({
            'id': r['PurchaseOrderID'],
            'supplier': suppliers.get(
                r.get('Supplier_SupplierID'), {}
            ).get('SupplierName') or '-',
            'expected': _format_short_date(expected, today),
            'overdue': bool(expected and expected < today),
            'status': r.get('Status') or '-',
            'stage': r.get('SupplierStage') or 'Draft',
            'url': url_for('purchase_order.view', po_id=r['PurchaseOrderID']),
        })
    return items


def _get_low_stock():
    """
    Lowest-QOH stock rows at or below LOW_STOCK_THRESHOLD.
    count='exact' returns the full low-stock total for the KPI card in
    the same request as the top rows for the table.
    Returns (total_count, items).
    """
    try:
        result = (
            supabase.table('Stock')
            .select('Stock_ID, Spare_Parts_SP_id, Brand_Brand_ID, Size, QOH',
                    count='exact')
            .lte('QOH', LOW_STOCK_THRESHOLD)
            .order('QOH')
            .order('Stock_ID')
            .limit(TABLE_LIMIT)
            .execute()
        )
        rows = result.data or []
        total = result.count or 0
    except Exception:
        return 0, []

    parts = _lookup(
        'Spare_Parts', 'SP_id', 'SP_id, SP_name',
        (r.get('Spare_Parts_SP_id') for r in rows),
    )
    brands = _lookup(
        'Brand', 'Brand_ID', 'Brand_ID, Brand_Name',
        (r.get('Brand_Brand_ID') for r in rows),
    )

    items = []
    for r in rows:
        qoh = int(_to_float(r.get('QOH')))
        items.append({
            'id': r['Stock_ID'],
            'part': parts.get(r.get('Spare_Parts_SP_id'), {}).get('SP_name') or '-',
            'brand': brands.get(r.get('Brand_Brand_ID'), {}).get('Brand_Name') or '-',
            'size': (r.get('Size') or '').strip() or '-',
            'qoh': qoh,
            'url': url_for('stock.edit', stock_id=r['Stock_ID']),
        })
    return total, items


def _get_recent_payments(today):
    """Latest TABLE_LIMIT payments, newest first."""
    try:
        result = (
            supabase.table('Payment')
            .select('PaymentID, PaymentDate, AmountPaid, PaymentType, '
                    'Sale_SaleID, Appointment_AppointmentID, Online_Order_OrderID')
            .order('PaymentDate', desc=True)
            .order('PaymentID', desc=True)
            .limit(TABLE_LIMIT)
            .execute()
        )
        rows = result.data or []
    except Exception:
        return []

    items = []
    for r in rows:
        sale_id = r.get('Sale_SaleID')
        appt_id = r.get('Appointment_AppointmentID')
        order_id = r.get('Online_Order_OrderID')
        if sale_id:
            reference = f'SALE-{sale_id}'
            link = url_for('sale.view', sale_id=sale_id)
        elif appt_id:
            reference = f'APPT-{appt_id}'
            link = url_for('appointment.view', appt_id=appt_id)
        elif order_id:
            reference = format_order_ref(order_id)
            link = url_for('online_order.view', order_id=order_id)
        else:
            reference = '-'
            link = url_for('payment.edit', payment_id=r['PaymentID'])

        items.append({
            'id': r['PaymentID'],
            'reference': reference,
            'type': r.get('PaymentType') or '-',
            'amount': _format_mur(_to_float(r.get('AmountPaid'))),
            'date': _format_short_date(_parse_date(r.get('PaymentDate')), today),
            'url': link,
        })
    return items


def _online_order_pills(counts):
    """Pills on the Online Orders tile; zero counts are left out."""
    pills = []
    if counts.get('online_order_to_process'):
        pills.append({'text': f"{counts['online_order_to_process']} to process", 'css': ''})
    if counts.get('online_order_reserved'):
        pills.append({'text': f"{counts['online_order_reserved']} reserved", 'css': 'oo-tile-pill-reserved'})
    if counts.get('online_order_overdue'):
        pills.append({'text': f"{counts['online_order_overdue']} overdue", 'css': 'oo-tile-pill-overdue'})
    return pills


def _supplier_application_pills(counts):
    """'N pending' pill on the Supplier Applications tile; left out when zero."""
    n = counts.get('supplier_application_pending')
    return [{'text': f'{n} pending', 'css': 'sa-tile-pill-pending'}] if n else []


def _appointment_pills(counts):
    """'N to confirm' pill on the Appointments tile; left out when zero."""
    n = counts.get('appointment_to_confirm')
    return [{'text': f'{n} to confirm', 'css': 'appt-tile-pill-confirm'}] if n else []


def _build_module_groups(counts):
    """The 19 module tiles, grouped by day-to-day function."""
    def tile(key, label, icon, endpoint, desc):
        return {
            'label': label,
            'count': counts.get(key, 0),
            'icon':  icon,
            'url':   url_for(endpoint),
            'desc':  desc,
        }

    return [
        {
            'title': 'Master Data',
            'icon':  'fa-database',
            'tiles': [
                tile('brand', 'Brands', 'fa-copyright', 'brand.index',
                     'Manage bike and part brands'),
                tile('model', 'Models', 'fa-motorcycle', 'model.index',
                     'Manage motorbike models'),
                tile('color', 'Colors', 'fa-palette', 'color.index',
                     'Manage available motorbike colors'),
                tile('category', 'Categories', 'fa-tags', 'category.index',
                     'Manage spare part categories'),
                tile('role', 'Roles', 'fa-id-badge', 'role.index',
                     'Manage employee roles and rates'),
                tile('employee', 'Employees', 'fa-user-tie', 'employee.index',
                     'Manage staff records'),
                tile('service', 'Services', 'fa-wrench', 'service.index',
                     'Manage workshop services'),
                tile('supplier', 'Suppliers', 'fa-truck', 'supplier.index',
                     'Manage supplier information'),
                dict(tile('supplier_application', 'Supplier Applications', 'fa-file-signature',
                          'supplier_application.index', 'Review requests to become a supplier'),
                     pills=_supplier_application_pills(counts)),
            ],
        },
        {
            'title': 'Inventory & Purchasing',
            'icon':  'fa-boxes-stacked',
            'tiles': [
                tile('stock', 'Stock', 'fa-boxes-stacked', 'stock.index',
                     'Manage stock inventory levels'),
                tile('spare_parts', 'Spare Parts', 'fa-gears', 'spare_parts.index',
                     'Manage spare parts catalogue'),
                tile('purchase_order', 'Purchase Orders', 'fa-file-invoice',
                     'purchase_order.index', 'Manage supplier purchase orders'),
                tile('compatibility', 'Compatibility', 'fa-link',
                     'compatibility.index', 'Manage stock-to-model compatibility'),
                tile('new_motorbike', 'New Motorbikes', 'fa-motorcycle',
                     'new_motorbike.index', 'Manage new motorbike inventory'),
            ],
        },
        {
            'title': 'Customers & Sales',
            'icon':  'fa-users',
            'tiles': [
                tile('customer', 'Customers', 'fa-users', 'customer.index',
                     'Manage customer records'),
                tile('customer_bike', 'Customer Bikes', 'fa-motorcycle',
                     'customer_bike.index', 'Manage registered customer motorbikes'),
                tile('sale', 'Sales', 'fa-handshake', 'sale.index',
                     'Manage motorbike sales records'),
                dict(tile('online_order', 'Online Orders', 'fa-bag-shopping',
                          'online_order.index',
                          'Process spare part orders and bike reservations placed online'),
                     pills=_online_order_pills(counts)),
            ],
        },
        {
            'title': 'Service & Payments',
            'icon':  'fa-screwdriver-wrench',
            'tiles': [
                dict(tile('appointment', 'Appointments', 'fa-calendar-check',
                          'appointment.index', 'Manage service and repair appointments'),
                     pills=_appointment_pills(counts)),
                tile('payment', 'Payments', 'fa-credit-card', 'payment.index',
                     'Manage payment records'),
            ],
        },
    ]


@bp.route('/')
@login_required
def index():
    today = _today()
    months = _get_chart_months(today)
    window_start = date(months[0][0], months[0][1], 1)
    end_year, end_month = _shift_month(today.year, today.month, 1)
    window_end = date(end_year, end_month, 1)

    counts = _get_dashboard_counts()
    appt_summary = _get_appointment_summary(today, window_start, window_end)
    motorcycle_sales, parts_sales = _get_sales_series(
        months, window_start, window_end, appt_summary['completed_in_window']
    )
    low_stock_total, low_stock_items = _get_low_stock()
    payments_month = _get_payments_this_month(today)

    kpis = [
        {
            'label': "Today's appointments",
            'value': appt_summary['today_count'],
            'icon':  'fa-calendar-day',
            'url':   url_for('appointment.index'),
        },
        {
            'label': 'Bikes available',
            'value': _get_bikes_available_count(),
            'icon':  'fa-motorcycle',
            'url':   url_for('new_motorbike.index'),
        },
        {
            'label': 'Low-stock items',
            'value': low_stock_total,
            'icon':  'fa-triangle-exclamation',
            'url':   url_for('stock.index'),
        },
        {
            'label': 'Payments received',
            'period': 'This month',
            'value': _format_mur_compact(payments_month),
            'title': _format_mur(payments_month),
            'icon':  'fa-arrow-trend-up',
            'url':   url_for('payment.index'),
        },
    ]

    status_counts = [appt_summary['status_counts'][s] for s in APPOINTMENT_STATUSES]
    chart_data = {
        'months':      _get_month_labels(months),
        'motorcycle':  motorcycle_sales,
        'parts':       parts_sales,
        'statuses':    APPOINTMENT_STATUSES,
        'statusCounts': status_counts,
    }

    module_groups = _build_module_groups(counts)

    return render_template(
        'dashboard/index.html',
        welcome_name=_welcome_name(),
        today_label=f'{today:%A}, {today.day} {today:%B %Y}',
        kpis=kpis,
        chart_data=chart_data,
        status_total=sum(status_counts),
        upcoming=_get_upcoming_appointments(today),
        open_pos=_get_open_purchase_orders(today),
        low_stock=low_stock_items,
        low_stock_threshold=LOW_STOCK_THRESHOLD,
        recent_payments=_get_recent_payments(today),
        module_groups=module_groups,
        module_total=sum(len(g['tiles']) for g in module_groups),
    )
