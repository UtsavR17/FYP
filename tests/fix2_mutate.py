"""Fix Phase 2 mutation checks: break one rule at a time, run test_fix2.py, report failures, restore."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO', os.path.dirname(HERE))
os.chdir(REPO)
PO = 'app/modules/purchase_order/routes.py'
CO = 'app/modules/compatibility/routes.py'
JS = 'app/static/js/admin.js'
MUTATIONS = {
    'shipped condition removed': (PO,
        "        if shipped is False:\n            return NOT_SHIPPED_MSG\n",
        "        if False:\n            return NOT_SHIPPED_MSG\n"),
    'stage condition removed': (PO,
        "        if stage != STAGE_ACCEPTED:\n            return NOT_ACCEPTED_MSG\n",
        "        if False:\n            return NOT_ACCEPTED_MSG\n"),
    'item shipped check not called': (PO,
        "    blocked = _receive_block_redirect(po_id, shipped=bool(item.get('DateShipped')))\n",
        "    blocked = None\n"),
    'bike shipped check not called': (PO,
        "    blocked = _receive_block_redirect(po_id, shipped=line.get('Status') == 'Shipped')\n",
        "    blocked = None\n"),
    'header-status refusal removed': (PO,
        "        elif (status_value in COMPUTED_PO_STATUSES and status_value != record.get('Status')\n",
        "        elif (False and status_value != record.get('Status')\n"),
    'NULL-equal comparison removed': (CO,
        "    return (model_no, year_from, year_to)\n",
        "    return (model_no, year_from, year_to) if year_from is not None or year_to is not None else object()\n"),
    'compat pre-check skipped': (CO,
        "                if key in existing:\n",
        "                if False:\n"),
    'all-skipped error removed': (CO,
        "            elif skipped and not fail_count:\n",
        "            elif False:\n"),
    'edit duplicate pre-check removed': (CO,
        "                if _combo_key(model_no, year_from, year_to) in _existing_combos(stock_id, exclude_com_id=com_id):\n",
        "                if False:\n"),
    'flash auto-hides errors again': (JS,
        "    const alerts = document.querySelectorAll('.flash-container .alert-success, .flash-container .alert-info');\n",
        "    const alerts = document.querySelectorAll('.flash-container .alert');\n"),
}
for name, (path, old, new) in MUTATIONS.items():
    raw = open(path, 'rb').read()
    src = raw.decode('utf-8').replace('\r\n', '\n')
    assert src.count(old) == 1, name
    open(path, 'w', encoding='utf-8', newline='').write(src.replace(old, new))
    try:
        env = dict(os.environ, REPO=REPO, PYTHONPATH=HERE)
        out = subprocess.run([sys.executable, '-W', 'ignore', os.path.join(HERE, 'test_fix2.py')],
                             capture_output=True, text=True, env=env).stderr
        failing = sorted(set(re.findall(r'^(?:FAIL|ERROR): (\w+)', out, re.M)))
        print(f'{name}: {len(failing)} failing -> {", ".join(failing) or "NONE (mutation survived!)"}')
    finally:
        open(path, 'wb').write(raw)
