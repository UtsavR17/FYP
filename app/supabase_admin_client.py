"""
Service-role Supabase client (Task 35).

Bypasses RLS, so it is used ONLY by the admin Supplier routes that manage
supplier portal logins (auth.admin.create_user, update_user_by_id and
delete_user). Import it lazily inside those route functions and nowhere else.

The key is read from SUPABASE_SERVICE_KEY in .env and is never logged,
flashed, rendered or sent to the browser.
"""
import os
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.environ.get('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY: str = os.environ.get('SUPABASE_SERVICE_KEY', '')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise EnvironmentError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in the .env file."
    )

# No user session is ever set on this client, and token refresh is off so
# no background refresh timer is started.
supabase_admin: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    options=ClientOptions(auto_refresh_token=False, persist_session=False),
)
