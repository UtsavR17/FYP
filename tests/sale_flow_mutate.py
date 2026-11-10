"""
Sale flow mutation checks: break one rule at a time, run test_sale_flow.py, report the failing
tests, then restore the file. Every mutation must make at least one test fail.

Run from the repo root:  venv/Scripts/python tests/sale_flow_mutate.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO', os.path.dirname(HERE))
ROUTES = 'app/modules/sale/routes.py'
LIST = 'app/templates/modules/sale/list.html'

EDIT_BUTTON = (
    "                    <a href=\"{{ url_for('sale.edit', sale_id=row.SaleID) }}\"\n"
    "                       class=\"btn btn-sm btn-outline-primary\">\n"
    "                        <i class=\"fa-solid fa-pen me-1\"></i>Edit\n"
    "                    </a>\n"
)

MUTATIONS = {
    'redirect back to the Sales list': (ROUTES,
        "                return redirect(url_for('payment.create', sale=new_sale_id))\n",
        "                return redirect(url_for('sale.index'))\n"),
    'redirect to the Sale view': (ROUTES,
        "                return redirect(url_for('payment.create', sale=new_sale_id))\n",
        "                return redirect(url_for('sale.view', sale_id=new_sale_id))\n"),
    'redirect to the appointment payment page': (ROUTES,
        "                return redirect(url_for('payment.create', sale=new_sale_id))\n",
        "                return redirect(url_for('payment.create'))\n"),
    'old success flash': (ROUTES,
        "                flash_success(f'Sale {new_sale_id} recorded. Record the first payment below.')\n",
        "                flash_success('Sale was recorded successfully.')\n"),
    'zero-total fallback removed': (ROUTES,
        "                if total_amount <= CENT:\n",
        "                if False:\n"),
    'missing-id fallback removed': (ROUTES,
        "        return None\n    if isinstance(sale_id, bool) or not isinstance(sale_id, int) or sale_id <= 0:\n",
        "        return 1\n    if isinstance(sale_id, bool) or not isinstance(sale_id, int) or sale_id <= 0:\n"),
    'duplicate-bike error path removed': (ROUTES,
        "                return redirect(url_for('payment.create', sale=new_sale_id))\n"
        "            except Exception as e:\n"
        "                error_msg = str(e)\n"
        "                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():\n",
        "                return redirect(url_for('payment.create', sale=new_sale_id))\n"
        "            except Exception as e:\n"
        "                error_msg = str(e)\n"
        "                if False:\n"),
    'Edit button restored in the list': (LIST,
        "                    {% if row._delete_blocked %}\n",
        EDIT_BUTTON + "                    {% if row._delete_blocked %}\n"),
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
        out = subprocess.run([sys.executable, '-W', 'ignore', os.path.join(HERE, 'test_sale_flow.py')],
                             capture_output=True, text=True, env=env).stderr
        failing = sorted(set(re.findall(r'^(?:FAIL|ERROR): (\w+)', out, re.M)))
        survived += not failing
        print(f'{name}: {len(failing)} failing -> {", ".join(failing) or "NONE (mutation survived!)"}')
    finally:
        open(full, 'wb').write(raw)
sys.exit(1 if survived else 0)
