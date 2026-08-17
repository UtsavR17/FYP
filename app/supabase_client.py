import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY: str = os.environ.get('SUPABASE_ANON_KEY', '')

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise EnvironmentError(
        "SUPABASE_URL and SUPABASE_ANON_KEY must be set in the .env file."
        )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)