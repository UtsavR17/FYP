"""
Fix Phase 3 tests: appointment status transitions (DEC-12), Confirm panel (ISS-13), services and parts
only after confirmation (ISS-12), locked bike (ISS-14), bike labels (ISS-15). Fake Supabase + Flask.

Run from the repo root:  venv/Scripts/python -W ignore tests/test_fix3.py
"""
import re
import unittest

from harness import APP, Base, url

import app.modules.appointment.routes as appt  # noqa: E402

STATUSES = ('Pending', 'Confirmed', 'In Progress', 'Completed', 'Cancelled', 'No Show')
TABLE = {
    'Pending':     {'Confirmed', 'Cancelled'},
    'Confirmed':   {'In Progress', 'Completed', 'Cancelled', 'No Show'},
    'In Progress': {'Completed', 'Cancelled'},
    'Completed': set(), 'Cancelled': set(), 'No Show': set(),
}
REFUSED = 'This status change is not allowed.'
CHANGED = 'This appointment has changed. Refresh and try again.'
CONFIRM_FIRST = 'Confirm the appointment first.'


def tables():
    return {
        'Brand': [{'Brand_ID': 1, 'Brand_Name': 'Honda'}],
        'Model': [{'Model_No': 1, 'Brand_Brand_ID': 1, 'Description': 'CB Shine'}],
        'Customer': [{'CustomerID': 1, 'FirstName': 'Alice', 'LastName': 'Martin'}],
        'Customer_bike': [
            {'BikeID': 5, 'RegistrationNumber': 'AB123', 'Year': 2019, 'Model_Model_No': 1, 'Customer_CustomerID': 1},
            {'BikeID': 6, 'RegistrationNumber': 'ZZ999', 'Year': None, 'Model_Model_No': None, 'Customer_CustomerID': None},
        ],
        'Employee': [{'EmployeeID': 2, 'FirstName': 'Max', 'LastName': 'Wrench'}],
        'Service': [{'ServiceID': 1, 'Service_Name': 'Oil change', 'Cost': 300},
                    {'ServiceID': 2, 'Service_Name': 'Brakes', 'Cost': 500}],
        'Spare_Parts': [{'SP_id': 1, 'SP_name': 'Filter'}],
        'Stock': [{'Stock_ID': 9, 'Spare_Parts_SP_id': 1, 'Brand_Brand_ID': 1, 'Size': None, 'S_Price': 50, 'QOH': 10},
                  {'Stock_ID': 10, 'Spare_Parts_SP_id': 1, 'Brand_Brand_ID': 1, 'Size': 'L', 'S_Price': 60, 'QOH': 10}],
        'Appointment': [],
        'appointment_service': [],
        'Appointment_Stock': [],
        'Payment': [],
    }


class Fix3Base(Base):
    tables = staticmethod(tables)

    def make(self, appt_id, status, employee=2, bike=5, with_lines=False):
        self.db.tables['Appointment'].append({
            'AppointmentID': appt_id, 'Customer_bike_BikeID': bike, 'Employee_EmployeeID': employee,
            'Appointment_Date': '2026-11-20', 'Appointment_time': '09:00:00', 'AppointmentType': 'Service',
            'Status': status})
        if with_lines:
            self.db.tables['appointment_service'].append(
                {'Appointment_AppointmentID': appt_id, 'Service_ServiceID': 1, 'Quantity': 1})
            self.db.tables['Appointment_Stock'].append(
                {'Appointment_AppointmentID': appt_id, 'Stock_Stock_ID': 9, 'Quantity': 3})

    def status(self, appt_id):
        return self.rows('Appointment', AppointmentID=appt_id)[0]['Status']

    def edit(self, appt_id, status, **extra):
        rec = self.rows('Appointment', AppointmentID=appt_id)[0]
        data = {'Employee_EmployeeID': str(rec['Employee_EmployeeID'] or ''), 'Appointment_Date': '2026-11-20',
                'Appointment_time': '09:00', 'AppointmentType': 'Service', 'Status': status,
                'expected_status': rec['Status']}
        data.update(extra)
        return self.post(url('appointment.edit', appt_id=appt_id), data)

    def confirm(self, appt_id, **form):
        data = {'Employee_EmployeeID': '2', 'AppointmentType': 'Repair', 'Appointment_Date': '2026-11-22',
                'Appointment_time': '10:30'}
        data.update(form)
        return self.post(url('appointment.confirm', appt_id=appt_id), data)


# --------------------------------------------------------------------------- 2.1 transitions
class T1Transitions(Fix3Base):
    def test_every_cell(self):
        """Edit (Confirmed / In Progress), Confirm and Cancel paths for every from/to pair."""
        n = 100
        for current in STATUSES:
            for target in STATUSES:
                if target == current:
                    continue
                n += 1
                self.make(n, current)
                allowed = target in TABLE[current]
                if current == 'Pending' and target == 'Confirmed':
                    r, _, flashes = self.confirm(n)
                elif target == 'Cancelled':
                    r, _, flashes = self.post(url('appointment.cancel', appt_id=n))
                elif current in ('Confirmed', 'In Progress'):
                    r, page, flashes = self.edit(n, target)
                    if not allowed:
                        self.assertIn(REFUSED, page, f'{current}->{target}')
                else:
                    r, _, flashes = self.edit(n, target)       # Pending / locked: edit is not a path
                result = self.status(n)
                self.assertEqual(result, target if allowed else current, f'{current} -> {target}')

    def test_edit_status_select_offers_only_allowed(self):
        for i, current in enumerate(('Confirmed', 'In Progress'), start=1):
            self.make(i, current)
            _, page = self.get(url('appointment.edit', appt_id=i))
            sel = page.split('id="Status"')[1].split('</select>')[0]
            offered = set(re.findall(r'<option\s+value="([^"]+)"', sel)) - {''}
            self.assertEqual(offered, TABLE[current] | {current}, current)

    def test_cancelled_cannot_be_cancelled_again(self):
        self.make(1, 'Cancelled')
        _, page = self.get(url('appointment.view', appt_id=1))
        self.assertNotIn(url('appointment.cancel', appt_id=1), page)
        updates_before = len(self.db.updates)
        r, _, flashes = self.post(url('appointment.cancel', appt_id=1))
        self.assertEqual(flashes, [REFUSED])
        self.assertEqual(len(self.db.updates), updates_before)

    def test_locked_statuses_cannot_be_edited(self):
        for i, status in enumerate(('Completed', 'Cancelled', 'No Show'), start=1):
            self.make(i, status)
            r = self.client.get(url('appointment.edit', appt_id=i))
            self.assertEqual(r.status_code, 302)
            self.assertNotIn('/edit/', r.headers['Location'])

    def test_completion_deducts_stock_once(self):
        self.make(1, 'In Progress', with_lines=True)
        r, _, flashes = self.edit(1, 'Completed')
        self.assertEqual(self.status(1), 'Completed')
        self.assertEqual(self.rows('Stock', Stock_ID=9)[0]['QOH'], 7)
        self.assertIn('stock quantities have been updated', flashes[0])
        self.edit(1, 'Completed')                                   # forged repeat
        self.post(url('appointment.add_stock', appt_id=1), {'Stock_Stock_ID': '10', 'Quantity': '1'})
        self.assertEqual(self.rows('Stock', Stock_ID=9)[0]['QOH'], 7)

    def test_stale_form_after_customer_cancel(self):
        self.make(1, 'Confirmed')
        self.db.before_update['Appointment'] = lambda db: db.tables['Appointment'][0].update(Status='Cancelled')
        r, _, flashes = self.edit(1, 'In Progress')
        self.assertEqual(flashes, [CHANGED])
        self.assertEqual(self.status(1), 'Cancelled')


# --------------------------------------------------------------------------- 2.2 confirm panel
class C1Confirm(Fix3Base):
    def setUp(self):
        super().setUp()
        self.make(1, 'Pending', employee=None, with_lines=True)

    def test_pending_view_shows_panel_and_read_only_sections(self):
        _, page = self.get(url('appointment.view', appt_id=1))
        self.assertIn('id="confirm"', page)
        self.assertIn(f'action="{url("appointment.confirm", appt_id=1)}"', page)
        self.assertIn('Confirm this appointment to add services, parts or payments.', page)
        self.assertIn('Oil change', page)                                 # customer's services still shown
        self.assertNotIn(url('appointment.add_service', appt_id=1), page)
        self.assertNotIn(url('appointment.add_stock', appt_id=1), page)
        self.assertNotIn(url('appointment.edit_service', appt_id=1, service_id=1), page)
        self.assertNotIn('prefill_appt=1', page)
        self.assertNotIn(f'href="{url("appointment.edit", appt_id=1)}"', page)
        self.assertIn(f'formaction="{url("appointment.cancel", appt_id=1)}"', page)

    def test_confirm_without_employee(self):
        r, page, flashes = self.confirm(1, Employee_EmployeeID='', AppointmentType='Inspection')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Choose the employee who will handle this appointment.', page)
        self.assertNotIn('alert-success', page)
        self.assertEqual(flashes, [])
        self.assertEqual(self.status(1), 'Pending')
        self.assertRegex(page, r'<option\s+value="Inspection"\s+selected')    # values kept
        self.assertIn('value="2026-11-22"', page)

    def test_confirm_with_invalid_employee(self):
        for bad in ('99', 'abc'):
            r, page, _ = self.confirm(1, Employee_EmployeeID=bad)
            self.assertIn('Please select a valid employee.', page)
        self.assertEqual(self.status(1), 'Pending')

    def test_confirm_invalid_date_or_time(self):
        r, page, _ = self.confirm(1, Appointment_Date='not-a-date', Appointment_time='25')
        self.assertIn('Appointment Date must be a valid date.', page)
        self.assertIn('Appointment time must be a valid time', page)
        self.assertEqual(self.status(1), 'Pending')

    def test_confirm_success(self):
        r, _, flashes = self.confirm(1)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(flashes, ['Appointment #1 confirmed with Max Wrench.'])
        row = self.rows('Appointment', AppointmentID=1)[0]
        self.assertEqual((row['Status'], row['Employee_EmployeeID'], row['AppointmentType'],
                          row['Appointment_Date'], row['Appointment_time'], row['Customer_bike_BikeID']),
                         ('Confirmed', 2, 'Repair', '2026-11-22', '10:30', 5))

    def test_confirm_race_with_customer_cancel(self):
        self.db.before_update['Appointment'] = lambda db: db.tables['Appointment'][0].update(Status='Cancelled')
        r, _, flashes = self.confirm(1)
        self.assertEqual(flashes, [CHANGED])
        row = self.rows('Appointment', AppointmentID=1)[0]
        self.assertEqual((row['Status'], row['Employee_EmployeeID']), ('Cancelled', None))

    def test_confirm_on_non_pending_refused(self):
        self.make(2, 'Confirmed')
        r, _, flashes = self.confirm(2, Employee_EmployeeID='2')
        self.assertEqual(flashes, [CHANGED])

    def test_pending_edit_url_goes_to_panel(self):
        r = self.client.get(url('appointment.edit', appt_id=1))
        self.assertTrue(r.headers['Location'].endswith(url('appointment.view', appt_id=1) + '#confirm'))
        r, _, flashes = self.edit(1, 'Pending')                       # old "updated successfully" path
        self.assertEqual(r.status_code, 302)
        self.assertEqual(flashes, [])
        self.assertEqual(len([u for u in self.db.updates if u[0] == 'Appointment']), 0)

    def test_cancel_pending_without_employee(self):
        r, _, flashes = self.post(url('appointment.cancel', appt_id=1))
        self.assertEqual(flashes, ['Appointment #1 was cancelled.'])
        self.assertEqual(self.status(1), 'Cancelled')


# --------------------------------------------------------------------------- 2.3 lines only after confirmation
class L1Lines(Fix3Base):
    def attempts(self, appt_id):
        return [
            ('add service', url('appointment.add_service', appt_id=appt_id), {'Service_ServiceID': '2', 'Quantity': '1'}),
            ('edit service', url('appointment.edit_service', appt_id=appt_id, service_id=1), {'Quantity': '2'}),
            ('delete service', url('appointment.delete_service', appt_id=appt_id, service_id=1), {}),
            ('add stock', url('appointment.add_stock', appt_id=appt_id), {'Stock_Stock_ID': '10', 'Quantity': '1'}),
            ('edit stock', url('appointment.edit_stock', appt_id=appt_id, stock_id=9), {'Quantity': '2'}),
            ('delete stock', url('appointment.delete_stock', appt_id=appt_id, stock_id=9), {}),
        ]

    def snapshot(self):
        return (repr(self.db.tables['appointment_service']), repr(self.db.tables['Appointment_Stock']))

    def test_pending_refused_including_direct_posts(self):
        self.make(1, 'Pending', employee=None, with_lines=True)
        before = self.snapshot()
        for label, path, data in self.attempts(1):
            r = self.client.get(path) if 'delete' not in label else None
            if r is not None:
                self.assertEqual(r.status_code, 302, label)
            r, _, flashes = self.post(path, data)
            self.assertEqual(r.status_code, 302, label)
            self.assertIn(CONFIRM_FIRST, flashes, label)
        self.assertEqual(self.snapshot(), before)

    def test_locked_statuses_refused(self):
        for i, status in enumerate(('Completed', 'Cancelled', 'No Show'), start=1):
            self.make(i, status, with_lines=True)
        before = self.snapshot()
        for i in (1, 2, 3):
            for label, path, data in self.attempts(i):
                r, _, flashes = self.post(path, data)
                self.assertIn('cannot be changed', flashes[0], label)
        self.assertEqual(self.snapshot(), before)

    def test_confirmed_and_in_progress_allowed(self):
        for i, status in enumerate(('Confirmed', 'In Progress'), start=1):
            self.make(i, status, with_lines=True)
            r, _, flashes = self.post(url('appointment.add_service', appt_id=i), {'Service_ServiceID': '2', 'Quantity': '1'})
            self.assertIn('Service was added to the appointment.', flashes, status)
            r, _, flashes = self.post(url('appointment.add_stock', appt_id=i), {'Stock_Stock_ID': '10', 'Quantity': '1'})
            self.assertIn('Stock item was added to the appointment.', flashes, status)
            r, _, flashes = self.post(url('appointment.delete_service', appt_id=i, service_id=1))
            self.assertIn('Service was removed from the appointment.', flashes, status)

    def test_payment_button_per_status(self):
        expected = {'Pending': False, 'Confirmed': True, 'In Progress': True, 'Completed': True,
                    'Cancelled': False, 'No Show': False}
        for i, status in enumerate(STATUSES, start=1):
            self.make(i, status, with_lines=True)
            _, page = self.get(url('appointment.view', appt_id=i))
            self.assertEqual(f'prefill_appt={i}"' in page, expected[status], status)


# --------------------------------------------------------------------------- 2.4 bike locked
class B1BikeLocked(Fix3Base):
    def test_edit_ignores_posted_bike(self):
        self.make(1, 'Confirmed')
        _, page = self.get(url('appointment.edit', appt_id=1))
        self.assertNotIn('name="Customer_bike_BikeID"', page)
        self.assertIn('AB123, Honda CB Shine (2019), Alice Martin', page)
        self.assertIn('cancel this appointment and create a new one', page)
        r, _, _ = self.edit(1, 'Confirmed', Customer_bike_BikeID='6')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.rows('Appointment', AppointmentID=1)[0]['Customer_bike_BikeID'], 5)

    def test_confirm_ignores_posted_bike(self):
        self.make(1, 'Pending', employee=None)
        self.confirm(1, Customer_bike_BikeID='6')
        self.assertEqual(self.rows('Appointment', AppointmentID=1)[0]['Customer_bike_BikeID'], 5)

    def test_create_still_selects_bike(self):
        _, page = self.get(url('appointment.create'))
        self.assertIn('name="Customer_bike_BikeID"', page)
        r, _, flashes = self.post(url('appointment.create'), {
            'Customer_bike_BikeID': '6', 'Employee_EmployeeID': '2', 'Appointment_Date': '2026-11-25',
            'Appointment_time': '11:00', 'AppointmentType': 'Service', 'Status': 'Pending'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.db.tables['Appointment'][-1]['Customer_bike_BikeID'], 6)


# --------------------------------------------------------------------------- 2.5 labels
class N1Labels(Fix3Base):
    def test_labels_everywhere_null_safe(self):
        self.make(1, 'Confirmed', bike=5)
        self.make(2, 'Confirmed', bike=6)
        _, page = self.get(url('appointment.index'))
        self.assertIn('AB123, Honda CB Shine (2019), Alice Martin', page)
        self.assertIn('ZZ999', page)
        self.assertNotIn('ZZ999,', page)                     # no model and no customer: registration only
        _, page = self.get(url('appointment.view', appt_id=1))
        self.assertIn('AB123, Honda CB Shine (2019), Alice Martin', page)
        _, page = self.get(url('appointment.create'))
        self.assertIn('AB123, Honda CB Shine (2019), Alice Martin', page)
        self.assertRegex(page, r'<option\s+value="6"\s*>\s*ZZ999\s*</option>')

    def test_helper_unit(self):
        labels = appt._bike_labels([5, 6])
        self.assertEqual(labels[5]['label'], 'AB123, Honda CB Shine (2019)')
        self.assertEqual(labels[5]['full'], 'AB123, Honda CB Shine (2019), Alice Martin')
        self.assertEqual((labels[6]['label'], labels[6]['customer']), ('ZZ999', None))

    def test_no_per_row_queries(self):
        for i in range(1, 41):
            self.make(i, 'Confirmed', bike=5 if i % 2 else 6)
        self.db.log.clear()
        self.get(url('appointment.index'))
        bike_selects = [e for e in self.db.log if e[0] == 'Customer_bike' and e[1] == 'select']
        self.assertEqual(len(bike_selects), 1)

    def test_search_registration_brand_model(self):
        self.make(1, 'Confirmed', bike=5)
        self.make(2, 'Confirmed', bike=6)
        for q, shown, hidden in (('ab123', 1, 2), ('honda', 1, 2), ('shine', 1, 2), ('zz999', 2, 1)):
            _, page = self.get(url('appointment.index', q=q))
            self.assertIn(url('appointment.view', appt_id=shown), page, q)
            self.assertNotIn(url('appointment.view', appt_id=hidden), page, q)


class X1Security(Fix3Base):
    def test_login_required(self):
        anon = APP.test_client()
        for path in (url('appointment.confirm', appt_id=1), url('appointment.cancel', appt_id=1),
                     url('appointment.delete_service', appt_id=1, service_id=1),
                     url('appointment.delete_stock', appt_id=1, stock_id=9)):
            r = anon.post(path)
            self.assertEqual(r.status_code, 302)
            self.assertIn('/auth/login', r.headers['Location'])

    def test_needs_confirmation_filter_kept(self):
        self.make(1, 'Pending', employee=None)
        self.make(2, 'Confirmed')
        _, page = self.get(url('appointment.index', filter='needs_confirmation'))
        self.assertIn(url('appointment.view', appt_id=1), page)
        self.assertNotIn(url('appointment.view', appt_id=2), page)


if __name__ == '__main__':
    unittest.main(verbosity=1)
