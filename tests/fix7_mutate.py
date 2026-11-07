"""
Fix Phase 7 mutation checks: break one rule at a time, run the Phase 7 suites, report the
failing tests, then restore the file. Every mutation must make at least one test fail.

Run from the repo root:  venv/Scripts/python tests/fix7_mutate.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO', os.path.dirname(HERE))
IDS = 'app/utils/ids.py'
REF = 'app/utils/order_ref.py'
PAY = 'app/modules/payment/routes.py'
LAYOUT = 'app/templates/layout/admin_layout.html'
JS = 'app/static/js/admin.js'
OO_VIEW = 'app/templates/modules/online_order/view.html'
PORTAL = 'app/templates/supplier_portal/product_form.html'

MUTATIONS = {
    'numeric helper adds a prefix': (IDS,
        "    return str(number) if number >= 0 else '-'\n",
        "    return f'#{number}' if number >= 0 else '-'\n"),
    'typed id uses an old prefix': (IDS,
        "    return f'{TYPE_WORDS.get(kind, kind.capitalize())} {display_id(value)}'\n",
        "    return f'{kind.upper()}-{display_id(value)}'\n"),
    'order_ref wrapper back to ORD-000012': (REF,
        "    return display_id(order_id)\n",
        "    return f'ORD-{int(order_id):06d}' if order_id else '-'\n"),
    'normaliser ignores prefixes': (IDS,
        "    if prefix and prefix not in QUERY_PREFIXES.get(kind, ()):\n",
        "    if prefix:\n"),
    'normaliser accepts any prefix': (IDS,
        "    if prefix and prefix not in QUERY_PREFIXES.get(kind, ()):\n",
        "    if False:\n"),
    'payment search loses the legacy alias': (PAY,
        "            or q in r.get('_search_alias', '')\n",
        ""),
    'early sidebar script removed': (LAYOUT,
        "                document.documentElement.classList.add('sidebar-collapsed');\n",
        ""),
    'drawer does not return focus': (JS,
        "            sidebarToggle.focus();\n",
        ""),
    'unpaid banner removed': (OO_VIEW,
        "    <div><strong>This order has not been paid. Stock has not been changed.</strong></div>\n",
        "    <div></div>\n"),
    'unpaid cancel wording removed': (OO_VIEW,
        "{% if order.Status == 'Pending Payment' %}Cancel this unpaid order?{% else %}",
        "{% if False %}{% else %}"),
    'portal brand hint removed': (PORTAL,
        "                    help_text='Brand not listed? Contact the dealership to have it added.') }}",
        "                    help_text='') }}"),
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
        failing = []
        for suite in ('test_fix7_ids.py', 'test_fix7_ui.py'):
            out = subprocess.run([sys.executable, '-W', 'ignore', os.path.join(HERE, suite)],
                                 capture_output=True, text=True, env=dict(os.environ, REPO=REPO)).stderr
            failing += re.findall(r'^(?:FAIL|ERROR): (\w+)', out, re.M)
        failing = sorted(set(failing))
        survived += not failing
        print(f'{name}: {len(failing)} failing -> {", ".join(failing) or "NONE (mutation survived!)"}')
    finally:
        open(full, 'wb').write(raw)
sys.exit(1 if survived else 0)
