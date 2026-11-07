"""
Records which rows each list search returns, as JSON, for fixtures_ids.SEARCH_BEFORE.
Used to capture the behaviour before Fix Phase 7 (run with REPO=<checkout of main a1e7c05>)
and to compare after it. Rows are read from the records each list route passes to
render_template, so the result does not depend on how the page displays ids.

Run from the repo root:  venv/Scripts/python -W ignore tests/record_searches.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402  (REPO decides which checkout's app is loaded)
from fake_supabase import FakeSupabase  # noqa: E402
import fixtures_ids  # noqa: E402

_captured = []


def _capture_records(module):
    original = module.render_template

    def wrapper(template, **context):
        pagination = context.get('pagination')
        if pagination is not None:
            _captured.append(list(pagination['records']))     # paginate() returns a dict
        return original(template, **context)
    module.render_template = wrapper


def search_ids(client, kind, query):
    list_ep, key = fixtures_ids.LISTS[kind]
    found, page = [], 1
    while page < 20:
        _captured.clear()
        client.get(harness.url(list_ep, q=query, page=page))
        rows = _captured[-1] if _captured else []
        ids = [r.get(key) for r in rows if r.get(key) not in found]
        if not ids:
            break
        found += ids
        page += 1
    return sorted(found)


def make_client():
    harness.install(FakeSupabase(fixtures_ids.tables()))
    for list_ep, _ in fixtures_ids.LISTS.values():
        module = sys.modules[harness.APP.view_functions[list_ep].__module__]
        if not hasattr(module.render_template, '__wrapped_capture__'):
            _capture_records(module)
            module.render_template.__wrapped_capture__ = True
    client = harness.APP.test_client()
    with client.session_transaction() as s:
        s['access_token'], s['refresh_token'], s['user_email'] = 't', 'r', 'staff@example.com'
    return client


def record(queries=None):
    queries = queries or fixtures_ids.SEARCH_BEFORE
    client = make_client()
    return {kind: {q: search_ids(client, kind, q) for q in qs} for kind, qs in queries.items()}


if __name__ == '__main__':
    print(json.dumps(record(), sort_keys=True))
