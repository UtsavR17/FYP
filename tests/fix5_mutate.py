"""
Fix Phase 5 mutation checks: break one rule at a time, run test_fix5.py, report the failing
tests, then restore the file. Every mutation must make at least one test fail.

Run from the repo root:  venv/Scripts/python tests/fix5_mutate.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO', os.path.dirname(HERE))
ACC = 'app/modules/customer/accounts.py'
ROUTES = 'app/modules/customer/routes.py'
FORM = 'app/templates/modules/customer/form.html'

MUTATIONS = {
    'protected-login rule removed (delete)': (ROUTES,
        "    login_protected = bool(auth_user_id and admin_client and login_is_protected(auth_user_id, admin_client))\n",
        "    login_protected = False\n"),
    'protected-login rule removed (staff and supplier)': (ACC,
        "    if staff or suppliers:\n        return True\n",
        "    if False:\n        return True\n"),
    'protected-login rule removed (deactivate)': (ROUTES,
        "    if login_is_protected(auth_user_id, admin_client):\n        flash_error(PROTECTED_LOGIN_MSG)\n",
        "    if False:\n        flash_error(PROTECTED_LOGIN_MSG)\n"),
    'pending applications not protected': (ACC,
        "    return any(a.get('Status') != SUPPLIER_APPLICATION_REJECTED for a in applications)\n",
        "    return any(a.get('Status') == 'Approved' for a in applications)\n"),
    'history refusal removed': (ROUTES,
        "    if history.has_history:\n",
        "    if False:\n"),
    'fail-safe removed (lookup failure)': (ACC,
        "    except Exception:\n        return True\n    if staff or suppliers:\n",
        "    except Exception:\n        return False\n    if staff or suppliers:\n"),
    'fail-safe removed (no client)': (ACC,
        "    if admin_client is None:\n        return True\n",
        "    if admin_client is None:\n        return False\n"),
    'short ban duration': (ACC,
        "BAN_DURATION = '876000h'\n",
        "BAN_DURATION = '24h'\n"),
    'login deleted before the rows': (ROUTES,
        "    try:\n        if history.unused_bike_ids:\n",
        "    _delete_login(admin_client, auth_user_id) if auth_user_id and not login_protected else None\n"
        "    try:\n        if history.unused_bike_ids:\n"),
    'buttons shown for protected logins': (FORM,
        "    {% elif acct.protected %}\n",
        "    {% elif False %}\n"),
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
        out = subprocess.run([sys.executable, '-W', 'ignore', os.path.join(HERE, 'test_fix5.py')],
                             capture_output=True, text=True, env=env).stderr
        failing = sorted(set(re.findall(r'^(?:FAIL|ERROR): (\w+)', out, re.M)))
        survived += not failing
        print(f'{name}: {len(failing)} failing -> {", ".join(failing) or "NONE (mutation survived!)"}')
    finally:
        open(full, 'wb').write(raw)
sys.exit(1 if survived else 0)
