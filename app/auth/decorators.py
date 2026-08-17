from functools import wraps
from flask import session, redirect, url_for, flash
from app.supabase_client import supabase


def login_required(f):
    """
    Route protection decorator — full implementation (Task 17).

    On every protected request:
    1. Checks that an access_token exists in the Flask session.
    2. Restores the Supabase Auth session so all subsequent database
       calls in this request use the authenticated user's JWT.
    3. Validates the token by calling get_user(). If the token is
       expired or invalid, clears the session and redirects to login.

    Because the Supabase client has an active session, auth.uid()
    inside the audit triggers correctly resolves to the admin user's
    UUID, so Created_By and Updated_By show the real email.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        access_token  = session.get('access_token')
        refresh_token = session.get('refresh_token', '')

        if not access_token:
            return redirect(url_for('auth.login'))

        try:
            supabase.auth.set_session(access_token, refresh_token)
            user_response = supabase.auth.get_user(access_token)
            if not user_response or not user_response.user:
                raise Exception('Session invalid or expired.')
        except Exception:
            session.clear()
            flash('Your session has expired. Please sign in again.', 'warning')
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated_function