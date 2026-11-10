"""
Appointment Create status tests: a new appointment can only start as Pending or Confirmed (offered
on the form and enforced on the server); Confirmed needs an employee; Edit and the transition table
are unchanged. Fake Supabase + Flask.

Run from the repo root:  venv/Scripts/python -W ignore tests/test_appt_create_status.py
"""
import re
import unittest

from harness import APP, Base, url  # noqa: F401

import app.modules.appointment.routes as appt  # noqa: E402

ALL_STATUSES = ('Pending', 'Confirmed', 'In Progress', 'Completed', 'Cancelled', 'No Show')
CREATE_OK = ('Pending', 'Confirmed')
REFUSED = 'New appointments can only start as Pending or Confirmed.'
TABLE = {
    'Pending':     ('Confirmed', 'Cancelled'),
    'Confirmed':   ('In Progress', 'Completed', 'Cancelled', 'No Show'),
    'In Progress': ('Completed', 'Cancelled'),
    'Completed': (), 'Cancelled': (), 'No Show': (),
}


def tables():
    return {
        'Brand': [{'Brand_ID': 1, 'Brand_Name': 'Honda'}],
        'Model': [{'Model_No': 1, 'Brand_Brand_ID': 1, 'Description': 'CB Shine'}],
        'Customer': [{'CustomerID': 1, 'FirstName': 'Alice', 'LastName': 'Martin'}],
        'Customer_bike': [{'BikeID': 5, 'RegistrationNumber': 'AB123', 'Year': 2019, 'Model_Model_No': 1,
                           'Customer_CustomerID': 1}],
        'Employee': [{'EmployeeID': 2, 'FirstName': 'Max', 'LastName': 'Wrench'}],
        'Service': [], 'Spare_Parts': [], 'Stock': [],
        'Appointment': [], 'appointment_service': [], 'Appointment_Stock': [], 'Payment': [],
    }


def status_options(page):
    """Values of the options in the Status select (the empty placeholder excluded)."""
    m = re.search(r'<select[^>]*name="Status".*?</select>', page, re.S)
    assert m, 'Status select not found'
    return [v for v in re.findall(r'<option\s+value="([^"]*)"', m.group(0)) if v]


class CreateBase(Base):
    tables = staticmethod(tables)

    def create(self, status, employee='2'):
        return self.post(url('appointment.create'), {
            'Customer_bike_BikeID': '5', 'Employee_EmployeeID': employee, 'Appointment_Date': '2026-12-15',
            'Appointment_time': '10:00', 'AppointmentType': 'Service', 'Status': status})


class CreateForm(CreateBase):
    def test_form_offers_only_pending_and_confirmed(self):
        r, page = self.get(url('appointment.create'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(status_options(page), list(CREATE_OK))

    def test_form_after_error_still_offers_only_two(self):
        r, page, _ = self.create('Completed')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(status_options(page), list(CREATE_OK))

    def test_constants(self):
        self.assertEqual(tuple(appt.CREATE_STATUSES), CREATE_OK)
        self.assertEqual(appt.CREATE_STATUS_REFUSED_MSG, REFUSED)


class CreatePostedStatus(CreateBase):
    def test_each_status_posted_directly(self):
        for status in ALL_STATUSES:
            with self.subTest(status=status):
                self.db.tables['Appointment'].clear()
                r, page, flashes = self.create(status)
                if status in CREATE_OK:
                    self.assertEqual(r.status_code, 302)
                    self.assertEqual(len(self.db.tables['Appointment']), 1)
                    self.assertEqual(self.db.tables['Appointment'][0]['Status'], status)
                    self.assertIn('Appointment was created successfully.', flashes)
                else:
                    self.assertEqual(r.status_code, 200)
                    self.assertIn(REFUSED, page)
                    self.assertEqual(self.db.tables['Appointment'], [])

    def test_unknown_status_refused(self):
        for status in ('Shipped', 'pending', 'Pending ', '<b>x</b>'):
            with self.subTest(status=status):
                r, page, _ = self.create(status)
                if status.strip() in CREATE_OK:          # surrounding spaces are trimmed, like every field
                    self.assertEqual(r.status_code, 302)
                    self.db.tables['Appointment'].clear()
                    continue
                self.assertEqual(r.status_code, 200)
                self.assertIn(REFUSED, page)
                self.assertEqual(self.db.tables['Appointment'], [])

    def test_empty_status_still_required(self):
        r, page, _ = self.create('')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Status is required.', page)
        self.assertEqual(self.db.tables['Appointment'], [])

    def test_confirmed_without_employee_refused(self):
        r, page, _ = self.create('Confirmed', employee='')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Employee is required.', page)
        self.assertEqual(self.db.tables['Appointment'], [])

    def test_confirmed_with_employee_saves_employee(self):
        r, _, _ = self.create('Confirmed')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.db.tables['Appointment'][0]['Employee_EmployeeID'], 2)


class EditUnchanged(CreateBase):
    def make(self, appt_id, status):
        self.db.tables['Appointment'].append({
            'AppointmentID': appt_id, 'Customer_bike_BikeID': 5, 'Employee_EmployeeID': 2,
            'Appointment_Date': '2026-12-15', 'Appointment_time': '10:00:00', 'AppointmentType': 'Service',
            'Status': status})

    def test_transition_table_unchanged(self):
        self.assertEqual({k: tuple(v) for k, v in appt.ALLOWED_TRANSITIONS.items()}, TABLE)
        self.assertEqual(tuple(appt.VALID_STATUSES), ALL_STATUSES)

    def test_edit_still_offers_later_statuses(self):
        self.make(1, 'Confirmed')
        _, page = self.get(url('appointment.edit', appt_id=1))
        self.assertEqual(status_options(page), ['Confirmed', 'In Progress', 'Completed', 'Cancelled', 'No Show'])

    def test_edit_can_move_to_in_progress(self):
        self.make(1, 'Confirmed')
        r, _, _ = self.post(url('appointment.edit', appt_id=1), {
            'Employee_EmployeeID': '2', 'Appointment_Date': '2026-12-15', 'Appointment_time': '10:00',
            'AppointmentType': 'Service', 'Status': 'In Progress', 'expected_status': 'Confirmed'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.rows('Appointment', AppointmentID=1)[0]['Status'], 'In Progress')


if __name__ == '__main__':
    unittest.main(verbosity=1)
