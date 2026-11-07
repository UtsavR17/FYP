# Admin Panel tests

Fake-client tests: an in-memory fake of supabase-py plus Flask's test client. They need no
database and make no network calls. The harness replaces `app.supabase_admin_client` with a
fake module, so the real service key in `.env` is never loaded by a test.

Run from the repo root with the project venv:

```bash
venv/Scripts/python -W ignore tests/test_smoke.py
venv/Scripts/python -W ignore tests/test_fix5.py
venv/Scripts/python tests/fix5_mutate.py
```

| File | What it covers |
|---|---|
| `fake_supabase.py` | Fake client: query builder, rpc, storage, and an `auth.admin` recorder (users with `banned_until`, simulated failures) |
| `harness.py` | Flask app, `install()`, `url()`, and the `Base` test case with `get`, `post` and `rows` |
| `test_smoke.py` | Every Admin GET route renders without a server error |
| `test_fix1.py`, `fix1_mutate.py` | Fix Phase 1: payments and sales |
| `test_fix2.py`, `fix2_mutate.py` | Fix Phase 2: PO receiving gate and compatibility feedback |
| `test_fix3.py`, `fix3_mutate.py` | Fix Phase 3: appointment workflow |
| `test_empty_fields.py` | Empty optional fields render empty, never "None" |
| `test_fix5.py` | Fix Phase 5: customer history, delete rules, online account deactivation |
| `fix5_mutate.py` | Breaks each Phase 5 rule in turn; every change must fail a test |
| `test_fix7_ids.py` | Fix Phase 7: plain numeric ids on every page, type badges, flash and modal texts, searches by number and old forms |
| `test_fix7_ui.py` | Fix Phase 7: collapsible sidebar markup and logic, unpaid online order wording, portal brand hint |
| `fixtures_ids.py`, `record_searches.py` | Search dataset, and the search results recorded on main before Phase 7 |
| `fix7_mutate.py` | Breaks the id helper, the search normaliser and the Phase 7 wording in turn |

Set `REPO=<other checkout>` to run the suites against another worktree.
