from flask import render_template, request, redirect, url_for, session, flash
from app.auth import bp
from app.supabase_client import supabase
from app.utils.flash_messages import flash_error
from app.auth.decorators import ADMIN_SESSION_KEYS


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page.
    GET:  Renders the login form. If already authenticated, redirects to dashboard.
    POST: Validates credentials with Supabase Auth. On success stores the
          access_token, refresh_token, and user_email in Flask's session.
    """
    # Already logged in — go to dashboard
    if session.get('access_token'):
        return redirect(url_for('dashboard.index'))

    error = None

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            error = 'Email and password are required.'
        else:
            response = None
            try:
                response = supabase.auth.sign_in_with_password({
                    'email':    email,
                    'password': password,
                })
            except Exception:
                error = 'Invalid email or password. Please try again.'

            if response is not None:
                # Only accounts on the Staff_User allow-list may use the Admin Panel
                try:
                    is_staff = supabase.rpc('is_staff').execute().data is True
                except Exception:
                    is_staff = False

                if is_staff:
                    session['access_token']  = response.session.access_token
                    session['refresh_token'] = response.session.refresh_token
                    session['user_email']    = response.user.email
                    return redirect(url_for('dashboard.index'))

                try:
                    supabase.auth.sign_out({'scope': 'local'})
                except Exception:
                    pass
                flash_error('This account is not authorised for the Admin Panel.')

    return render_template('auth/login.html', error=error)


@bp.route('/logout')
def logout():
    """
    Logs the user out of both Supabase Auth and Flask's session,
    then redirects to the login page.
    """
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in ADMIN_SESSION_KEYS:
        session.pop(key, None)
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('auth.login'))