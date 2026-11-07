"""
Shared Flask test-client harness for the Admin Panel suites (no database, no network).

Run a suite from the repo root with the project venv:
    venv/Scripts/python -W ignore tests/test_smoke.py
REPO defaults to the folder above tests/; set REPO=<other checkout> to test another worktree.

The service-role module app.supabase_admin_client is replaced by a fake before any route can
import it, so the real service key in .env is never loaded by a test. Base.setUp points that
fake's `supabase_admin` at the same in-memory FakeSupabase as the normal client.
"""
import html
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO', os.path.dirname(HERE))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)
os.chdir(REPO)

FAKE_ADMIN_MODULE = types.ModuleType('app.supabase_admin_client')
FAKE_ADMIN_MODULE.supabase_admin = None
sys.modules['app.supabase_admin_client'] = FAKE_ADMIN_MODULE

from fake_supabase import FakeSupabase  # noqa: E402
from app import create_app  # noqa: E402

APP = create_app()
APP.config.update(TESTING=True, SECRET_KEY='test')


def install(fake):
    """Point every loaded app module's `supabase` (and the fake service-role client) at the fake."""
    for name, module in list(sys.modules.items()):
        if (name == 'app' or name.startswith('app.')) and hasattr(module, 'supabase'):
            setattr(module, 'supabase', fake)
    FAKE_ADMIN_MODULE.supabase_admin = fake


def url(endpoint, **kw):
    from flask import url_for
    with APP.test_request_context():
        return url_for(endpoint, **kw)


class Base(unittest.TestCase):
    tables = staticmethod(dict)   # override: returns the starting tables

    def setUp(self):
        self.db = FakeSupabase(self.tables())
        install(self.db)
        self.client = APP.test_client()
        with self.client.session_transaction() as s:
            s['access_token'] = 'test-token'
            s['refresh_token'] = 'r'
            s['user_email'] = 'staff@example.com'

    def get(self, path, **kw):
        r = self.client.get(path, **kw)
        return r, html.unescape(r.get_data(as_text=True))

    def post(self, path, data=None, **kw):
        """POST; returns (response, unescaped body, flashes still queued in the session)."""
        r = self.client.post(path, data=data or {}, **kw)
        with self.client.session_transaction() as s:
            flashes = [m for _, m in s.get('_flashes', [])]
            s.pop('_flashes', None)
        return r, html.unescape(r.get_data(as_text=True)), flashes

    def rows(self, table, **match):
        return [r for r in self.db.tables.get(table, []) if all(r.get(k) == v for k, v in match.items())]
