"""Fix Phase 3 mutation checks: break one rule at a time, run test_fix3.py, report failures, restore."""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get('REPO', os.path.dirname(HERE))
os.chdir(REPO)
A = 'app/modules/appointment/routes.py'
MUTATIONS = {
    'transition guard removed (edit)': (A,
        "        elif not can_transition(previous_status, status_value):\n",
        "        elif False:\n"),
    'cancel guard removed': (A,
        "    if 'Cancelled' not in ALLOWED_TRANSITIONS.get(current, ()):\n",
        "    if False:\n"),
    'confirm employee requirement removed': (A,
        "    if not emp_raw:\n        errors['Employee_EmployeeID'] = 'Choose the employee who will handle this appointment.'\n",
        "    if False:\n        errors['Employee_EmployeeID'] = 'Choose the employee who will handle this appointment.'\n"),
    'confirm not conditional on Pending': (A,
        "        }).eq('AppointmentID', appt_id).eq('Status', 'Pending').execute()\n",
        "        }).eq('AppointmentID', appt_id).execute()\n"),
    'service/stock status check removed': (A,
        "    if status in LINE_EDIT_STATUSES:\n        return None\n",
        "    if True:\n        return None\n"),
    'bike-ignore rule removed (edit uses posted bike)': (A,
        "    bike_id = record.get('Customer_bike_BikeID')     # locked on edit (DEC-9)\n",
        "    bike_id = int(request.form.get('Customer_bike_BikeID') or record.get('Customer_bike_BikeID'))\n"),
    'pending edit redirect removed': (A,
        "    if previous_status == 'Pending':\n        return redirect(url_for('appointment.view', appt_id=appt_id, _anchor='confirm'))\n",
        "    if False:\n        return redirect(url_for('appointment.view', appt_id=appt_id, _anchor='confirm'))\n"),
}
for name, (path, old, new) in MUTATIONS.items():
    raw = open(path, 'rb').read()
    src = raw.decode('utf-8').replace('\r\n', '\n')
    assert src.count(old) == 1, name
    open(path, 'w', encoding='utf-8', newline='').write(src.replace(old, new))
    try:
        env = dict(os.environ, REPO=REPO, PYTHONPATH=HERE)
        out = subprocess.run([sys.executable, '-W', 'ignore', os.path.join(HERE, 'test_fix3.py')],
                             capture_output=True, text=True, env=env).stderr
        failing = sorted(set(re.findall(r'^(?:FAIL|ERROR): (\w+)', out, re.M)))
        print(f'{name}: {len(failing)} failing -> {", ".join(failing) or "NONE (mutation survived!)"}')
    finally:
        open(path, 'wb').write(raw)
