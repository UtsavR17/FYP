"""Fix Phase 1 mutation checks: break one rule at a time, run test_fix1.py, report failures, restore."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO', os.path.dirname(HERE))
os.chdir(REPO)
P = 'app/modules/payment/routes.py'
S = 'app/modules/sale/routes.py'
MUTATIONS = {
    'deposit-first rule removed': (P,
        "        if earlier:\n            return 'PaymentType', (\n",
        "        if False:\n            return 'PaymentType', (\n"),
    'deposit below total rule removed': (P,
        "        if amount >= total - CENT:\n",
        "        if False:\n"),
    'instalment needs deposit removed': (P,
        "        if not any(_effective_type(p) == TYPE_DEPOSIT for p in earlier):\n",
        "        if False:\n"),
    'full payment exact rule removed': (P,
        "        if abs(amount - remaining) > CENT:\n",
        "        if False:\n"),
    'online deposit not counted': (P,
        "    return TYPE_DEPOSIT if _is_online_payment(payment) else payment.get('PaymentType')\n",
        "    return payment.get('PaymentType')\n"),
    'deposit type lock removed': (P,
        "    if (current_payment and current_payment.get('PaymentType') == TYPE_DEPOSIT and later\n",
        "    if (False and current_payment and later\n"),
    'status filter removed from options': (P,
        "            if a.get('Status') in PAYABLE_APPOINTMENT_STATUSES or a['AppointmentID'] == current_appt_id\n",
        "            if True\n"),
    'status check removed from server': (P,
        "                elif rows[0].get('Status') not in PAYABLE_APPOINTMENT_STATUSES and not keeps_own:\n",
        "                elif False:\n"),
    'sale context check removed (mismatch)': (P,
        "        elif not is_edit and sale_id != context_sale_id:\n",
        "        elif False:\n"),
    'sale POST allowed on appointment page': (P,
        "    if not is_edit and mode == 'appointment' and (posted_type == 'sale' or sale_id_raw):\n",
        "    if False:\n"),
    'future date allowed': (P,
        "    elif date_type.fromisoformat(pay_date) > today_mauritius():\n",
        "    elif False:\n"),
    'salesperson filter removed': (S,
        "        for e in employees if e.get('Role_Role_ID') in role_ids\n",
        "        for e in employees\n"),
    'one-time token check loosened': (P,
        "        if not submitted_token or submitted_token != session_token:\n",
        "        if session_token is not None and submitted_token != session_token:\n"),
}
for name, (path, old, new) in MUTATIONS.items():
    raw = open(path, 'rb').read()
    src = raw.decode('utf-8').replace('\r\n', '\n')
    assert src.count(old) == 1, name
    open(path, 'w', encoding='utf-8', newline='').write(src.replace(old, new))
    try:
        env = dict(os.environ, REPO=REPO, PYTHONPATH=HERE)
        out = subprocess.run([sys.executable, '-W', 'ignore', os.path.join(HERE, 'test_fix1.py')],
                             capture_output=True, text=True, env=env).stderr
        failing = sorted(set(re.findall(r'^(?:FAIL|ERROR): (\w+)', out, re.M)))
        print(f'{name}: {len(failing)} failing -> {", ".join(failing) or "NONE (mutation survived!)"}')
    finally:
        open(path, 'wb').write(raw)
