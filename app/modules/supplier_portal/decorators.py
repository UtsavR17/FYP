"""
Supplier portal authentication (Task 35).

Session isolation
-----------------
The Admin Panel shares one module-level Supabase client and re-authenticates
it on every admin request (sign_in_with_password / set_session). The portal
must never touch that object, otherwise admin and supplier requests could run
as each other. Every portal request therefore builds its OWN client from the
anon key and authenticates it with the supplier's tokens.

The supplier's tokens live under their own Flask session keys
(SUPPLIER_SESSION_KEYS). Portal logout clears only those keys, and admin
logout never clears them.
"""
from functools import wraps

from flask import g, redirect, session, url_for
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

# Only the URL and anon key constants are imported: never the shared client
from app.supabase_client import SUPABASE_ANON_KEY, SUPABASE_URL
from app.utils.flash_messages import flash_error, flash_warning


SUPPLIER_SESSION_KEYS = (
    'supplier_access_token',
    'supplier_refresh_token',
    'supplier_id',
    'supplier_name',
    'supplier_email',
)


class SupplierSessionError(Exception):
    """The stored supplier tokens are missing, expired or rejected."""


def new_anon_client() -> Client:
    """
    A fresh, unauthenticated client using the same URL and anon key as the
    admin client. auto_refresh_token is off so no background Timer thread is
    started (it would rotate the refresh token behind the session's back).
    """
    return create_client(
        SUPABASE_URL,
        SUPABASE_ANON_KEY,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def clear_supplier_session():
    """Remove only the supplier portal keys from the Flask session."""
    for key in SUPPLIER_SESSION_KEYS:
        session.pop(key, None)


def get_supplier_client() -> Client:
    """
    Return a client authenticated as the logged-in supplier for this request.

    set_session() refreshes the access token when it has expired; the
    (possibly new) token pair is written back to the Flask session. The
    PostgREST client is then explicitly authorised with the access token so
    every query runs as the supplier and RLS applies.

    Raises SupplierSessionError on any failure.
    """
    cached = g.get('supplier_client')
    if cached is not None:
        return cached

    access_token = session.get('supplier_access_token')
    refresh_token = session.get('supplier_refresh_token')
    if not access_token or not refresh_token:
        raise SupplierSessionError('No supplier session.')

    try:
        client = new_anon_client()
        response = client.auth.set_session(access_token, refresh_token)
        if not response or not response.session or not response.session.access_token:
            raise SupplierSessionError('Supplier session could not be restored.')

        new_access = response.session.access_token
        new_refresh = response.session.refresh_token or refresh_token
        session['supplier_access_token'] = new_access
        session['supplier_refresh_token'] = new_refresh

        client.postgrest.auth(new_access)
    except SupplierSessionError:
        raise
    except Exception as e:
        raise SupplierSessionError('Supplier session could not be restored.') from e

    g.supplier_client = client
    return client


def supplier_login_required(f):
    """
    Portal equivalent of @login_required.

    1. Requires the supplier tokens in the Flask session (an admin session
       does not count).
    2. Restores a per-request supplier client (get_supplier_client).
    3. Confirms the JWT still maps to the supplier stored in the session via
       current_supplier_id(), so an unlinked or deleted supplier is signed
       out immediately.
    On any failure only the supplier keys are cleared and the browser is sent
    to the portal login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('supplier_access_token'):
            return redirect(url_for('supplier_portal.login'))

        try:
            client = get_supplier_client()
            linked_id = client.rpc('current_supplier_id').execute().data
        except Exception:
            clear_supplier_session()
            flash_warning('Your supplier session has expired. Please sign in again.')
            return redirect(url_for('supplier_portal.login'))

        if linked_id is None or str(linked_id) != str(session.get('supplier_id')):
            clear_supplier_session()
            flash_error('This login is not linked to a supplier account.')
            return redirect(url_for('supplier_portal.login'))

        return f(*args, **kwargs)
    return decorated_function
