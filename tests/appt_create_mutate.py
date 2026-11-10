"""
Appointment Create status mutation checks: break one rule at a time, run test_appt_create_status.py,
report the failing tests, then restore the file. Every mutation must make at least one test fail.

Run from the repo root:  venv/Scripts/python tests/appt_create_mutate.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO', os.path.dirname(HERE))
ROUTES = 'app/modules/appointment/routes.py'

MUTATIONS = {
    'server accepts every valid status again': (ROUTES,
        "        elif status_value not in CREATE_STATUSES:\n",
        "        elif status_value not in VALID_STATUSES:\n"),
    'server check removed': (ROUTES,
        "        elif status_value not in CREATE_STATUSES:\n",
        "        elif False:\n"),
    'form offers every status again': (ROUTES,
        "        status_options=CREATE_STATUS_OPTIONS\n",
        "        status_options=STATUS_OPTIONS\n"),
    'In Progress allowed on create': (ROUTES,
        "CREATE_STATUSES = ('Pending', 'Confirmed')\n",
        "CREATE_STATUSES = ('Pending', 'Confirmed', 'In Progress')\n"),
    'Confirmed refused on create': (ROUTES,
        "CREATE_STATUSES = ('Pending', 'Confirmed')\n",
        "CREATE_STATUSES = ('Pending',)\n"),
    'employee no longer required': (ROUTES,
        "            errors['Employee_EmployeeID'] = 'Employee is required.'\n",
        "            pass\n"),
    'transition table changed': (ROUTES,
        "    'Confirmed':   ('In Progress', 'Completed', 'Cancelled', 'No Show'),\n",
        "    'Confirmed':   ('Pending', 'Cancelled'),\n"),
}

survived = 0
for name, (path, old, new) in MUTATIONS.items():
    full = os.path.join(REPO, path)
    raw = open(full, 'rb').read()
    src = raw.decode('utf-8')
    crlf = '\r\n' in src
    src = src.replace('\r\n', '\n')
    assert src.count(old) == 1, name
    mutated = src.replace(old, new)
    open(full, 'w', encoding='utf-8', newline='').write(mutated.replace('\n', '\r\n') if crlf else mutated)
    try:
        env = dict(os.environ, REPO=REPO)
        out = subprocess.run([sys.executable, '-W', 'ignore', os.path.join(HERE, 'test_appt_create_status.py')],
                             capture_output=True, text=True, env=env).stderr
        failing = sorted(set(re.findall(r'^(?:FAIL|ERROR): (\w+)', out, re.M)))
        survived += not failing
        print(f'{name}: {len(failing)} failing -> {", ".join(failing) or "NONE (mutation survived!)"}')
    finally:
        open(full, 'wb').write(raw)
sys.exit(1 if survived else 0)
