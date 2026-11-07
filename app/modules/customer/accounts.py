"""
Customer history and online login helpers (Fix Phase 5: ISS-07, decision DEC-4).

History: a customer may be deleted only when nothing refers to them except garage bikes that
have no appointments. Otherwise the delete is refused and the online login can be deactivated.

Online login: the service-role client (app/supabase_admin_client.py) is imported lazily by
get_service_client() and used only by the customer delete, deactivate and reactivate routes
and by the customer edit page. It is never passed to a template and never logged.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.supabase_client import supabase

# About 100 years. A banned login cannot sign in, and a password reset does not lift the ban.
BAN_DURATION = '876000h'
UNBAN_DURATION = 'none'

STATUS_ACTIVE = 'Active'
STATUS_DEACTIVATED = 'Deactivated'
STATUS_NONE = 'No online account'
STATUS_UNKNOWN = 'Unknown'

SUPPLIER_APPLICATION_REJECTED = 'Rejected'

PROTECTED_LOGIN_MSG = (
    'This online login is also used by staff or a supplier, so it cannot be changed '
    'from the customer page.'
)
NOT_CONFIGURED_MSG = (
    'Online accounts cannot be managed on this server. '
    'Add SUPABASE_SERVICE_KEY to the .env file and restart the app.'
)


# =============================================================================
# History (2.1)
# =============================================================================

@dataclass
class CustomerHistory:
    appointments: int = 0
    sales: int = 0
    online_orders: int = 0
    unused_bike_ids: list = field(default_factory=list)   # bikes without appointments
    used_bike_ids: list = field(default_factory=list)     # bikes with at least one appointment

    @property
    def has_history(self):
        return bool(self.appointments or self.sales or self.online_orders)

    def summary(self):
        """'2 appointments, 1 sale and 3 online orders' (only the non-zero parts)."""
        parts = [
            _count_label(self.appointments, 'appointment', 'appointments'),
            _count_label(self.sales, 'sale', 'sales'),
            _count_label(self.online_orders, 'online order', 'online orders'),
        ]
        parts = [p for p in parts if p]
        if len(parts) <= 1:
            return ''.join(parts)
        return ', '.join(parts[:-1]) + ' and ' + parts[-1]


def _count_label(n, singular, plural):
    if not n:
        return ''
    return f'{n} {singular if n == 1 else plural}'


def customer_history(customer_id):
    """
    Counts what refers to this customer: appointments (through their bikes), sales and online
    orders, plus their garage bikes split into unused and used. Four queries in total, whatever
    the number of bikes. Raises when a lookup fails, so callers never delete on a guess.
    """
    bikes = (
        supabase.table('Customer_bike')
        .select('BikeID')
        .eq('Customer_CustomerID', customer_id)
        .execute()
    ).data or []
    bike_ids = sorted({b.get('BikeID') for b in bikes if b.get('BikeID') is not None})

    appointments = []
    if bike_ids:
        appointments = (
            supabase.table('Appointment')
            .select('AppointmentID, Customer_bike_BikeID')
            .in_('Customer_bike_BikeID', bike_ids)
            .execute()
        ).data or []
    used = {a.get('Customer_bike_BikeID') for a in appointments}

    sales = (
        supabase.table('Sale')
        .select('SaleID')
        .eq('Customer_CustomerID', customer_id)
        .execute()
    ).data or []
    orders = (
        supabase.table('Online_Order')
        .select('OrderID')
        .eq('Customer_CustomerID', customer_id)
        .execute()
    ).data or []

    return CustomerHistory(
        appointments=len(appointments),
        sales=len(sales),
        online_orders=len(orders),
        unused_bike_ids=[b for b in bike_ids if b not in used],
        used_bike_ids=[b for b in bike_ids if b in used],
    )


# =============================================================================
# Online login (2.2 and 2.3)
# =============================================================================

def get_service_client():
    """The service-role client, imported lazily, or None when it is not configured."""
    try:
        from app.supabase_admin_client import supabase_admin
    except Exception:
        return None
    return supabase_admin


def login_is_protected(auth_user_id, admin_client):
    """
    True when this login belongs to staff or a supplier, so it must never be deleted, banned or
    unbanned from the customer pages: its id is in Staff_User, a Supplier row links it
    (Supplier.AuthUserID), or a supplier application that is not Rejected names it as the
    applicant (pending applications are included so an applicant is never orphaned).

    Same fail-safe as Task 47's supplier helper _login_is_shared: no client or any lookup
    failure counts as protected. The lookups use the service-role client, so row level
    security can never hide a staff or supplier row and make the login look unprotected.
    """
    if not auth_user_id:
        return False
    if admin_client is None:
        return True
    try:
        staff = (
            admin_client.table('Staff_User')
            .select('AuthUserID')
            .eq('AuthUserID', auth_user_id)
            .limit(1)
            .execute()
        ).data or []
        suppliers = (
            admin_client.table('Supplier')
            .select('SupplierID')
            .eq('AuthUserID', auth_user_id)
            .limit(1)
            .execute()
        ).data or []
        applications = (
            admin_client.table('Supplier_Application')
            .select('ApplicationID, Status')
            .eq('AuthUserID', auth_user_id)
            .execute()
        ).data or []
    except Exception:
        return True
    if staff or suppliers:
        return True
    return any(a.get('Status') != SUPPLIER_APPLICATION_REJECTED for a in applications)


def is_not_found_error(error):
    code = str(getattr(error, 'code', '') or '').lower()
    return getattr(error, 'status', None) == 404 or code == 'user_not_found'


def auth_error_reason(error):
    """Short, safe reason text from a Supabase Auth API error (never a stack trace)."""
    message = getattr(error, 'message', None)
    if getattr(error, 'status', None) and message:
        return message
    return 'the authentication service did not respond as expected'


def fetch_login(admin_client, auth_user_id):
    """
    The login as {'email', 'banned_until'}, or None when no such login exists. Raises on any
    other failure.

    The installed gotrue (2.12.x) User model drops banned_until, so get_user_by_id cannot tell
    whether a login is banned. The admin API's own request helper returns the raw user JSON with
    the same URL and headers; get_user_by_id is the fallback if a later version removes it.
    """
    try:
        uuid.UUID(str(auth_user_id))
    except ValueError:
        return None
    admin = admin_client.auth.admin
    try:
        request = getattr(admin, '_request', None)
        if callable(request):
            data = request('GET', f'admin/users/{auth_user_id}', xform=lambda d: d)
        else:
            user = admin.get_user_by_id(auth_user_id).user
            data = user.model_dump() if hasattr(user, 'model_dump') else dict(vars(user))
    except Exception as e:
        if is_not_found_error(e):
            return None
        raise
    if isinstance(data, dict) and isinstance(data.get('user'), dict):
        data = data['user']
    data = data if isinstance(data, dict) else {}
    return {'email': data.get('email'), 'banned_until': data.get('banned_until')}


def is_banned(login, now=None):
    """True while banned_until is in the future. An unreadable value counts as banned."""
    value = (login or {}).get('banned_until')
    if not value:
        return False
    if isinstance(value, datetime):
        until = value
    else:
        try:
            until = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except ValueError:
            return True
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until > (now or datetime.now(timezone.utc))


def online_account(auth_user_id):
    """
    Status for the customer edit page: {'status', 'email', 'protected'}. Reads the login with
    the service-role client, so it is called on that page only, never per row in a list.
    """
    if not auth_user_id:
        return {'status': STATUS_NONE, 'email': None, 'protected': False}
    client = get_service_client()
    if client is None:
        return {'status': STATUS_UNKNOWN, 'email': None, 'protected': True,
                'reason': NOT_CONFIGURED_MSG}
    protected = login_is_protected(auth_user_id, client)
    try:
        login = fetch_login(client, auth_user_id)
    except Exception:
        return {'status': STATUS_UNKNOWN, 'email': None, 'protected': protected,
                'reason': 'The online account could not be checked right now. Reload the page to try again.'}
    if login is None:
        return {'status': STATUS_NONE, 'email': None, 'protected': protected}
    status = STATUS_DEACTIVATED if is_banned(login) else STATUS_ACTIVE
    return {'status': status, 'email': login.get('email'), 'protected': protected}
