"""
In-memory fake of the supabase-py client for the Admin Panel tests (Flask test client, no database).

Supports the query-builder calls used by the app: select / insert / update / delete, eq, neq, is_,
in_, gt, gte, lt, lte, order, limit, range, single, maybe_single, plus rpc, storage and auth.admin.
Unknown builder methods (or_, ilike, ...) are accepted and ignored so unrelated pages still render.

Test controls on FakeSupabase:
  raise_on[(table, op)]  exception, or callable(query) returning an exception or None (a hook)
  fail_tables            tables whose every call raises
  before_update[table]   callable(db) run once before the next update on that table
  id_columns[table]      primary key auto-assigned on insert when missing (default list below)
  log / updates / deletes / inserts   call records for assertions
"""
import copy

DEFAULT_ID_COLUMNS = {
    'Payment': 'PaymentID', 'Sale': 'SaleID', 'Appointment': 'AppointmentID', 'Stock': 'Stock_ID',
    'Spare_Parts': 'SP_id', 'Model': 'Model_No', 'PurchaseOrder': 'PurchaseOrderID',
    'PurchaseOrderItem': 'POItem_ID', 'Customer': 'CustomerID', 'Employee': 'EmployeeID', 'Role': 'Role_ID',
    'New_MotorBike': 'NB_ID', 'Supplier': 'SupplierID', 'Brand': 'Brand_ID', 'Category': 'CAT_ID',
    'Service': 'ServiceID', 'Customer_bike': 'BikeID', 'Online_Order': 'OrderID',
}


class Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class Query:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.op = 'select'
        self.columns = '*'
        self.want_count = False
        self.filters = []
        self.orders = []
        self._limit = None
        self._range = None
        self._single = False
        self.payload = None

    # -- operations ---------------------------------------------------------
    def select(self, columns='*', count=None, **_):
        self.columns = columns
        self.want_count = count is not None
        return self

    def update(self, payload):
        self.op, self.payload = 'update', payload
        return self

    def insert(self, payload):
        self.op, self.payload = 'insert', payload
        return self

    def delete(self):
        self.op = 'delete'
        return self

    # -- filters ------------------------------------------------------------
    def _add(self, kind, col, val, fn):
        self.filters.append(fn)
        self.db.log.append((self.table, kind, col, val))
        return self

    def eq(self, col, val):
        return self._add('eq', col, val, lambda r: r.get(col) == val)

    def neq(self, col, val):
        return self._add('neq', col, val, lambda r: r.get(col) != val)

    def is_(self, col, val):
        return self._add('is', col, val,
                         lambda r: r.get(col) is None if val in ('null', None) else r.get(col) == val)

    def in_(self, col, vals):
        vals = list(vals)
        return self._add('in', col, tuple(vals), lambda r: r.get(col) in vals)

    def gt(self, col, val):
        return self._add('gt', col, val, lambda r: r.get(col) is not None and str(r.get(col)) > str(val))

    def gte(self, col, val):
        return self._add('gte', col, val, lambda r: r.get(col) is not None and str(r.get(col)) >= str(val))

    def lt(self, col, val):
        return self._add('lt', col, val, lambda r: r.get(col) is not None and str(r.get(col)) < str(val))

    def lte(self, col, val):
        return self._add('lte', col, val, lambda r: r.get(col) is not None and str(r.get(col)) <= str(val))

    def order(self, col, desc=False, **_):
        self.orders.append((col, desc))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = 'maybe'
        return self

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)

        def passthrough(*_a, **_k):
            return self
        return passthrough

    # -- execution ----------------------------------------------------------
    def _matching(self):
        rows = self.db.tables.setdefault(self.table, [])
        return [r for r in rows if all(f(r) for f in self.filters)]

    def execute(self):
        self.db.log.append((self.table, self.op, self.columns))
        if self.table in self.db.fail_tables:
            raise Exception(f'simulated failure on {self.table}')
        raiser = self.db.raise_on.get((self.table, self.op))
        if raiser:
            exc = raiser(self) if callable(raiser) else raiser
            if exc:
                raise exc

        if self.op == 'update':
            hook = self.db.before_update.pop(self.table, None)
            if hook:
                hook(self.db)
            changed = []
            for r in self._matching():
                r.update(copy.deepcopy(self.payload))
                changed.append(copy.deepcopy(r))
            self.db.updates.append((self.table, copy.deepcopy(self.payload), len(changed)))
            return Result(changed)

        if self.op == 'insert':
            rows = copy.deepcopy(self.payload if isinstance(self.payload, list) else [self.payload])
            key = self.db.id_columns.get(self.table)
            table = self.db.tables.setdefault(self.table, [])
            for r in rows:
                if key and r.get(key) is None:
                    existing = [x.get(key) for x in table if isinstance(x.get(key), int)]
                    r[key] = max(existing, default=0) + 1
                table.append(r)
            self.db.inserts.append((self.table, copy.deepcopy(rows)))
            return Result(copy.deepcopy(rows))

        if self.op == 'delete':
            matching = self._matching()
            self.db.tables[self.table] = [r for r in self.db.tables.get(self.table, []) if r not in matching]
            self.db.deletes.append((self.table, len(matching)))
            return Result(copy.deepcopy(matching))

        rows = self._matching()
        for col, desc in reversed(self.orders):
            rows.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        total = len(rows)
        if self._range:
            rows = rows[self._range[0]:self._range[1] + 1]
        if self._limit is not None:
            rows = rows[:self._limit]
        rows = copy.deepcopy(rows)
        if self._single is True:
            if len(rows) != 1:
                raise Exception('JSON object requested, multiple (or no) rows returned')
            return Result(rows[0], total if self.want_count else None)
        if self._single == 'maybe':
            return Result(rows[0] if rows else None)
        return Result(rows, total if self.want_count else None)


class Rpc:
    def __init__(self, db, name, params):
        self.db, self.name, self.params = db, name, params

    def execute(self):
        self.db.rpc_calls.append((self.name, self.params))
        handler = self.db.rpc_handlers.get(self.name)
        if handler is None:
            raise Exception(f'no handler for rpc {self.name}')
        return Result(handler(self.db, self.params))


class FakeBucket:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def create_signed_url(self, path, expires_in, options=None):
        self.db.storage_calls.append(('create_signed_url', self.name, path, expires_in))
        if self.db.storage_fail or path not in self.db.storage_objects:
            raise Exception('Object not found')
        return {'signedURL': f'https://storage.example/signed/{self.name}/token-{len(self.db.storage_calls)}'}

    def upload(self, path, file, file_options=None):
        self.db.storage_calls.append(('upload', self.name, path, len(file), dict(file_options or {})))
        if 'upload' in self.db.storage_fail_ops:
            raise Exception('simulated upload failure')
        self.db.storage_objects.add(f'{self.name}/{path}')
        return {'path': path}

    def remove(self, paths):
        self.db.storage_calls.append(('remove', self.name, list(paths)))
        if 'remove' in self.db.storage_fail_ops:
            raise Exception('simulated remove failure')
        for p in paths:
            self.db.storage_objects.discard(f'{self.name}/{p}')
        return [{'name': p} for p in paths]


class FakeStorage:
    def __init__(self, db):
        self.db = db

    def from_(self, name):
        return FakeBucket(self.db, name)


class _User:
    user = object()


class FakeAuthError(Exception):
    """Shaped like gotrue's AuthApiError (message, status, code)."""
    def __init__(self, message, status=500, code=None):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


class FakeAuthAdmin:
    """
    Recorder for auth.admin. `users` maps id -> raw user JSON (as the GoTrue admin API returns
    it, including banned_until). `fail_ops` holds operation names that raise
    ('get', 'delete_user', 'update_user_by_id'). `calls` keeps (op, user_id); `attributes`
    keeps (user_id, attributes) for every update_user_by_id call.
    """
    def __init__(self):
        self.calls = []
        self.attributes = []
        self.users = {}
        self.fail_ops = set()

    def add_user(self, user_id, email, banned_until=None):
        self.users[user_id] = {'id': user_id, 'email': email, 'banned_until': banned_until}

    def _missing(self, user_id):
        if user_id not in self.users:
            raise FakeAuthError('User not found', status=404, code='user_not_found')

    def _request(self, method, path, *a, xform=None, **k):
        user_id = path.rsplit('/', 1)[-1]
        self.calls.append(('get', user_id))
        if 'get' in self.fail_ops:
            raise FakeAuthError('simulated auth failure')
        self._missing(user_id)
        data = copy.deepcopy(self.users[user_id])
        return xform(data) if xform else data

    def delete_user(self, user_id, *a, **k):
        self.calls.append(('delete_user', user_id))
        if 'delete_user' in self.fail_ops:
            raise FakeAuthError('simulated delete failure')
        self._missing(user_id)
        self.users.pop(user_id, None)

    def update_user_by_id(self, user_id, attributes, *a, **k):
        self.calls.append(('update_user_by_id', user_id))
        self.attributes.append((user_id, dict(attributes)))
        if 'update_user_by_id' in self.fail_ops:
            raise FakeAuthError('simulated update failure')
        if self.users and user_id not in self.users:
            self._missing(user_id)
        if 'ban_duration' in attributes:
            ban = attributes['ban_duration']
            self.users[user_id]['banned_until'] = None if ban == 'none' else '2126-10-01T00:00:00Z'

    def create_user(self, attributes, *a, **k):
        self.calls.append(('create_user', attributes.get('email')))

        class _U:
            class user:
                id = 'new-portal-user'
        return _U()


class Auth:
    def __init__(self):
        self.admin = FakeAuthAdmin()

    def set_session(self, *_a, **_k):
        return None

    def get_user(self, *_a, **_k):
        return _User()


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = copy.deepcopy(tables or {})
        self.log, self.updates, self.deletes, self.inserts = [], [], [], []
        self.rpc_calls, self.rpc_handlers = [], {}
        self.before_update, self.raise_on = {}, {}
        self.fail_tables = set()
        self.id_columns = dict(DEFAULT_ID_COLUMNS)
        self.auth = Auth()
        self.storage = FakeStorage(self)
        self.storage_calls, self.storage_objects = [], set()
        self.storage_fail, self.storage_fail_ops = False, set()

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, params=None):
        return Rpc(self, name, params or {})
