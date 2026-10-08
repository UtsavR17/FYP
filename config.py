import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-fallback-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
    # Largest request body accepted (Task 49): a 2 MB product image plus the
    # other form fields. Larger requests get a friendly flash (see app/__init__.py).
    MAX_CONTENT_LENGTH = 3 * 1024 * 1024