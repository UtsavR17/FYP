"""
Fix Phase 1 tests (Payments and Sales): sale payments card, contextual payment modes, DEC-5 payment
rules, date default, context card, payable appointments, sale form. Fake Supabase + Flask test client.

Run from the repo root:  venv/Scripts/python -W ignore tests/test_fix1.py
"""
import glob
import re
import unittest
from datetime import timedelta

from harness import APP, Base, install, url
from fake_supabase import FakeSupabase

import app.modules.payment.routes as pay  # noqa: E402

TODAY = pay.today_mauritius().isoformat()
TOMORROW = (pay.today_mauritius() + timedelta(days=1)).isoformat()
PLACEHOLDER = 'Payment management will be available in the next update'
FULL_MSG = 'A full payment must settle the remaining balance of Rs. {:,.2f}.'
DEPOSIT_TOTAL_MSG = 'A deposit must be less than the total of Rs. {:,.2f}. Choose Full Payment to pay everything.'
INSTALMENT_MSG = 'Record the deposit first. Instalments can only follow a deposit.'


def base_tables():
    return {
        'Brand': [{'Brand_ID': 1, 'Brand_Name': 'Honda'}],
        'Model': [{'Model_No': 1, 'Brand_Brand_ID': 1, 'Description': 'CB Shine'},
                  {'Model_No': 2, 'Brand_Brand_ID': 1, 'Description': 'Wave 110'}],
        'Customer': [{'CustomerID': 1, 'FirstName': 'Alice', 'LastName': 'Martin'},
                     {'CustomerID': 2, 'FirstName': 'Bob', 'LastName': 'Lee'}],
        'New_MotorBike': [
            {'NB_ID': 10, 'Model_Model_No': 1, 'Year': 2025, 'VIN': 'VIN-SHINE-10', 'Color_Color': 'Red',
             'Price': 1000, 'Status': 'Sold'},
            {'NB_ID': 11, 'Model_Model_No': 2, 'Year': 2024, 'VIN': None, 'Color_Color': None,
             'Price': 900, 'Status': 'Sold'},
            {'NB_ID': 12, 'Model_Model_No': 1, 'Year': 2026, 'VIN': 'VIN-12', 'Color_Color': 'Black',
             'Price': 1200, 'Status': 'Available'},
        ],
        # Sale 1: total 1000, no payments. Sale 2: reservation sale, online deposit 100 of 900.
        'Sale': [
            {'SaleID': 1, 'Customer_CustomerID': 1, 'New_MotorBike_NB_ID': 10, 'Employee_EmployeeID': 1,
             'SaleDate': '2026-10-01', 'TotalAmount': 1000},
            {'SaleID': 2, 'Customer_CustomerID': None, 'New_MotorBike_NB_ID': 11, 'Employee_EmployeeID': None,
             'SaleDate': '2026-10-02', 'TotalAmount': 900},
        ],
        'Payment': [
            {'PaymentID': 50, 'Sale_SaleID': 2, 'Appointment_AppointmentID': None, 'Online_Order_OrderID': None,
             'StripePaymentIntentID': 'pi_test_res', 'PaymentDate': '2026-10-02', 'AmountPaid': 100,
             'PaymentMethod': 'Online', 'PaymentType': 'Deposit'},
        ],
        'Online_Order': [{'OrderID': 7, 'Sale_SaleID': 2, 'OrderType': 'Reservation', 'Customer_CustomerID': 2}],
        'Role': [{'Role_ID': 1, 'Role_Name': ' salesperson '}, {'Role_ID': 2, 'Role_Name': 'Mechanic'}],
        'Employee': [
            {'EmployeeID': 1, 'FirstName': 'Sam', 'LastName': 'Seller', 'Role_Role_ID': 1},
            {'EmployeeID': 2, 'FirstName': 'Max', 'LastName': 'Wrench', 'Role_Role_ID': 2},
        ],
        'Customer_bike': [{'BikeID': 5, 'RegistrationNumber': 'AB123', 'Model_Model_No': 2, 'Customer_CustomerID': 2},
                          {'BikeID': 6, 'RegistrationNumber': None, 'Model_Model_No': None, 'Customer_CustomerID': None}],
        # Appointment totals come from services (Service 1 costs 500).
        'Service': [{'ServiceID': 1, 'Cost': 500}],
        'Appointment': [
            {'AppointmentID': i, 'Customer_bike_BikeID': 5, 'Appointment_Date': '2026-10-05', 'Status': s,
             'Appointment_time': '09:00:00', 'AppointmentType': 'Service', 'Employee_EmployeeID': 2}
            for i, s in ((101, 'Pending'), (102, 'Confirmed'), (103, 'In Progress'), (104, 'Completed'),
                         (105, 'Cancelled'), (106, 'No Show'))
        ] + [{'AppointmentID': 107, 'Customer_bike_BikeID': 6, 'Appointment_Date': '2026-10-06', 'Status': 'Confirmed',
              'Appointment_time': '10:00:00', 'AppointmentType': 'Service', 'Employee_EmployeeID': None}],
        'appointment_service': [{'Appointment_AppointmentID': i, 'Service_ServiceID': 1, 'Quantity': 1}
                                for i in range(101, 108)],
        'Appointment_Stock': [],
        'Stock': [],
    }


class Fix1Base(Base):
    tables = staticmethod(base_tables)

    def new_token(self, path):
        r, page = self.get(path)
        m = re.search(r'name="form_token" value="([^"]+)"', page)
        return r, page, (m.group(1) if m else '')

    def pay_sale(self, sale_id, ptype, amount, date=TODAY, method='Cash', **extra):
        _, _, token = self.new_token(url('payment.create', sale=sale_id))
        data = {'form_token': token, 'reference_type': 'sale', 'Sale_SaleID': str(sale_id), 'PaymentType': ptype,
                'AmountPaid': str(amount), 'PaymentDate': date, 'PaymentMethod': method}
        data.update(extra)
        return self.post(url('payment.create', sale=sale_id), data)

    def pay_appt(self, appt_id, ptype, amount, date=TODAY, **extra):
        _, _, token = self.new_token(url('payment.create'))
        data = {'form_token': token, 'reference_type': 'appointment', 'Appointment_AppointmentID': str(appt_id),
                'PaymentType': ptype, 'AmountPaid': str(amount), 'PaymentDate': date, 'PaymentMethod': 'Card'}
        data.update(extra)
        return self.post(url('payment.create'), data)

    def payments(self, **match):
        return self.rows('Payment', **match)

    def add_payment(self, pid, ptype, amount, sale=None, appt=None):
        self.db.tables['Payment'].append({
            'PaymentID': pid, 'Sale_SaleID': sale, 'Appointment_AppointmentID': appt, 'Online_Order_OrderID': None,
            'StripePaymentIntentID': None, 'PaymentDate': '2026-10-03', 'AmountPaid': amount,
            'PaymentMethod': 'Cash', 'PaymentType': ptype})


# --------------------------------------------------------------------------- 2.1 sale view
class S1SaleView(Fix1Base):
    def test_placeholder_gone_from_every_template(self):
        for path in glob.glob('app/templates/**/*.html', recursive=True):
            with open(path, encoding='utf-8') as fh:
                self.assertNotIn(PLACEHOLDER, fh.read(), path)
        _, page = self.get(url('sale.view', sale_id=1))
        self.assertNotIn(PLACEHOLDER, page)

    def test_no_payments_unpaid_with_button(self):
        _, page = self.get(url('sale.view', sale_id=1))
        self.assertIn('No payment recorded for this sale yet.', page)
        self.assertIn('pay-status-unpaid">Unpaid', page)
        self.assertIn(f'href="{url("payment.create", sale=1)}"', page)
        self.assertIn('Rs. 1,000.00', page)

    def test_partial_payments_listed_with_balance(self):
        self.add_payment(60, 'Deposit', 300, sale=1)
        self.add_payment(61, 'Instalment', 200, sale=1)
        _, page = self.get(url('sale.view', sale_id=1))
        self.assertIn('pay-status-partially-paid">Partially paid', page)
        self.assertIn('Rs. 500.00', page)              # paid and balance
        self.assertEqual(page.count('<td class="text-end">Rs. '), 2)
        self.assertIn(f'href="{url("payment.create", sale=1)}"', page)

    def test_fully_paid_hides_button(self):
        self.add_payment(60, 'Full Payment', 1000, sale=1)
        _, page = self.get(url('sale.view', sale_id=1))
        self.assertIn('pay-status-paid">Paid', page)
        self.assertNotIn(url('payment.create', sale=1), page)

    def test_online_payment_marked_locked(self):
        _, page = self.get(url('sale.view', sale_id=2))
        self.assertIn('(Online, locked)', page)
        self.assertIn('Rs. 800.00', page)

    def test_sale_list_payment_status_one_query(self):
        self.add_payment(60, 'Deposit', 300, sale=1)
        self.db.log.clear()
        _, page = self.get(url('sale.index'))
        self.assertIn('<th>Payment</th>', page)
        self.assertIn('Partially paid', page)
        payment_selects = [e for e in self.db.log if e[0] == 'Payment' and e[1] == 'select']
        self.assertEqual(len(payment_selects), 1)


# --------------------------------------------------------------------------- 2.2 modes
class M1Modes(Fix1Base):
    def test_standalone_page_is_appointment_only(self):
        _, page = self.get(url('payment.create'))
        self.assertIn('Record appointment payment', page)
        self.assertNotIn('type="radio"', page)
        self.assertNotIn('name="Sale_SaleID"', page)
        self.assertIn('name="Appointment_AppointmentID"', page)
        self.assertIn('<input type="hidden" name="reference_type" value="appointment">', page)

    def test_sale_page_is_locked_to_the_sale(self):
        _, page = self.get(url('payment.create', sale=1))
        self.assertIn('Record sale payment', page)
        self.assertIn('<input type="hidden" name="Sale_SaleID" value="1">', page)
        self.assertNotIn('<select class="form-select" id="Sale_SaleID"', page.replace('\n', ' ').replace('  ', ' '))
        self.assertNotIn('name="Appointment_AppointmentID"', page)
        self.assertNotIn('type="radio"', page)
        # posting back keeps the context: no action attribute, so the query string stays
        self.assertRegex(page, r'<form method="POST" novalidate id="paymentForm"\s')
        self.assertNotRegex(page, r'id="paymentForm"[^>]*action=')

    def test_list_button_opens_appointment_page(self):
        _, page = self.get(url('payment.index'))
        self.assertIn(f'href="{url("payment.create")}"', page)

    def test_sale_payment_redirects_to_sale_view(self):
        r, _, flashes = self.pay_sale(1, 'Deposit', 300)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers['Location'].endswith(url('sale.view', sale_id=1)))
        self.assertEqual(flashes, ['Payment was recorded successfully.'])
        self.assertEqual(len(self.payments(Sale_SaleID=1)), 1)

    def test_forged_sale_post_on_appointment_page_refused(self):
        _, _, token = self.new_token(url('payment.create'))
        r, page, _ = self.post(url('payment.create'), {
            'form_token': token, 'reference_type': 'sale', 'Sale_SaleID': '1', 'PaymentType': 'Full Payment',
            'AmountPaid': '1000', 'PaymentDate': TODAY, 'PaymentMethod': 'Cash'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('Sale payments are recorded from the sale', page)
        self.assertEqual(self.payments(Sale_SaleID=1), [])

    def test_mismatched_sale_id_refused(self):
        r, page, _ = self.pay_sale(1, 'Deposit', 300, Sale_SaleID='2')
        self.assertEqual(r.status_code, 200)
        self.assertIn('This page records a payment for SALE-1 only.', page)
        self.assertEqual(len(self.payments()), 1)

    def test_appointment_post_on_sale_path_refused(self):
        r, page, _ = self.pay_sale(1, 'Deposit', 300, reference_type='appointment', Appointment_AppointmentID='102')
        self.assertIn('This page records a payment for SALE-1 only.', page)
        r, page, _ = self.pay_sale(1, 'Deposit', 300, Appointment_AppointmentID='102')
        self.assertIn('This page records a payment for SALE-1 only.', page)
        self.assertEqual(len(self.payments()), 1)

    def test_bad_or_paid_sale_context(self):
        r, _, flashes = self.post(url('payment.create', sale='abc'))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(url('payment.create', sale=999))
        self.assertTrue(r.headers['Location'].endswith(url('sale.index')))
        self.add_payment(60, 'Full Payment', 1000, sale=1)
        r = self.client.get(url('payment.create', sale=1))
        self.assertTrue(r.headers['Location'].endswith(url('sale.view', sale_id=1)))

    def test_double_submit_still_blocked(self):
        _, _, token = self.new_token(url('payment.create', sale=1))
        data = {'form_token': token, 'reference_type': 'sale', 'Sale_SaleID': '1', 'PaymentType': 'Deposit',
                'AmountPaid': '300', 'PaymentDate': TODAY, 'PaymentMethod': 'Cash'}
        self.post(url('payment.create', sale=1), data)
        r, _, flashes = self.post(url('payment.create', sale=1), data)     # replay after success
        self.assertIn('already been submitted', flashes[0])
        r, _, flashes = self.post(url('payment.create'), dict(data, form_token=''))   # no token at all
        self.assertIn('already been submitted', flashes[0])
        self.assertEqual(len(self.payments(Sale_SaleID=1)), 1)

    def test_prefill_from_appointment_view_kept(self):
        _, page = self.get(url('payment.create', prefill_appt=102))
        self.assertRegex(page, r'<option\s+value="102"\s+selected')


# --------------------------------------------------------------------------- 2.3 DEC-5 matrix
class R1SaleMatrix(Fix1Base):
    """Sale 1: total 1000."""

    def assert_refused(self, result, text):
        r, page, _ = result
        self.assertEqual(r.status_code, 200, text)
        self.assertIn(text, page)

    def assert_saved(self, result):
        r, page, flashes = result
        self.assertEqual(r.status_code, 302, re.findall(r'invalid-feedback">([^<]+)', page))

    def test_first_payment(self):
        self.assert_refused(self.pay_sale(1, 'Full Payment', '999.99'), FULL_MSG.format(1000))
        self.assert_refused(self.pay_sale(1, 'Full Payment', '1000.01'), FULL_MSG.format(1000))
        self.assert_refused(self.pay_sale(1, 'Deposit', '1000'), DEPOSIT_TOTAL_MSG.format(1000))
        self.assert_refused(self.pay_sale(1, 'Deposit', '1000.01'), DEPOSIT_TOTAL_MSG.format(1000))
        self.assert_refused(self.pay_sale(1, 'Instalment', '100'), INSTALMENT_MSG)
        self.assertEqual(self.payments(Sale_SaleID=1), [])
        self.assert_saved(self.pay_sale(1, 'Full Payment', '1000'))

    def test_deposit_just_below_total(self):
        self.assert_saved(self.pay_sale(1, 'Deposit', '999.99'))
        self.assert_saved(self.pay_sale(1, 'Instalment', '0.01'))

    def test_after_deposit(self):
        self.assert_saved(self.pay_sale(1, 'Deposit', '300'))
        self.assert_refused(self.pay_sale(1, 'Deposit', '100'), 'A deposit can only be the first payment')
        self.assert_refused(self.pay_sale(1, 'Full Payment', '699.99'), FULL_MSG.format(700))
        self.assert_refused(self.pay_sale(1, 'Full Payment', '700.01'), FULL_MSG.format(700))
        self.assert_refused(self.pay_sale(1, 'Instalment', '700.01'), 'exceeds the remaining balance of Rs. 700.00')
        self.assert_saved(self.pay_sale(1, 'Instalment', '699.99'))
        self.assert_saved(self.pay_sale(1, 'Instalment', '0.01'))     # last instalment closes the balance

    def test_full_after_deposit_settles(self):
        self.assert_saved(self.pay_sale(1, 'Deposit', '300'))
        self.assert_saved(self.pay_sale(1, 'Full Payment', '700'))
        self.assertEqual(self.client.get(url('payment.create', sale=1)).status_code, 302)   # fully paid

    def test_after_full_settlement_everything_refused(self):
        self.add_payment(60, 'Full Payment', 1000, sale=1)
        for ptype in ('Full Payment', 'Deposit', 'Instalment'):
            # The GET redirects (fully paid), so plant a token as if the form had been open already.
            with self.client.session_transaction() as s:
                s['payment_form_token'] = 'open-form'
            self.assert_refused(self.post(url('payment.create', sale=1), {
                'form_token': 'open-form', 'reference_type': 'sale', 'Sale_SaleID': '1', 'PaymentType': ptype,
                'AmountPaid': '1', 'PaymentDate': TODAY, 'PaymentMethod': 'Cash'}),
                'This sale is already fully paid (Rs. 1,000.00).')
        self.assertEqual(len(self.payments(Sale_SaleID=1)), 1)

    def test_amount_must_be_positive(self):
        self.assert_refused(self.pay_sale(1, 'Deposit', '0'), 'Amount paid must be a number greater than 0.')
        self.assert_refused(self.pay_sale(1, 'Deposit', '-5'), 'Amount paid must be a number greater than 0.')

    def test_online_deposit_counts_as_the_deposit(self):
        # Sale 2: online reservation deposit 100 of 900 (Stripe). A second deposit is refused,
        # an instalment is allowed.
        self.assert_refused(self.pay_sale(2, 'Deposit', '50'), 'A deposit can only be the first payment')
        self.assert_saved(self.pay_sale(2, 'Instalment', '400'))
        self.assert_saved(self.pay_sale(2, 'Full Payment', '400'))

    def test_online_payment_counts_as_deposit_whatever_its_stored_type(self):
        self.db.tables['Payment'][0]['PaymentType'] = 'Full Payment'
        self.assert_saved(self.pay_sale(2, 'Instalment', '100'))


class R2AppointmentMatrix(Fix1Base):
    """Appointment 102 (Confirmed): total 500."""

    def test_matrix(self):
        r, page, _ = self.pay_appt(102, 'Instalment', '100')
        self.assertIn(INSTALMENT_MSG, page)
        r, page, _ = self.pay_appt(102, 'Deposit', '500')
        self.assertIn(DEPOSIT_TOTAL_MSG.format(500), page)
        r, page, _ = self.pay_appt(102, 'Full Payment', '499.99')
        self.assertIn(FULL_MSG.format(500), page)
        r, _, flashes = self.pay_appt(102, 'Deposit', '200')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers['Location'].endswith(url('payment.index')))
        r, page, _ = self.pay_appt(102, 'Instalment', '300.01')
        self.assertIn('exceeds the remaining balance of Rs. 300.00', page)
        r, _, _ = self.pay_appt(102, 'Instalment', '300')
        self.assertEqual(r.status_code, 302)
        r, page, _ = self.pay_appt(102, 'Full Payment', '1')
        self.assertIn('This appointment is already fully paid (Rs. 500.00).', page)
        self.assertEqual(len(self.payments(Appointment_AppointmentID=102)), 2)


class R3EditRules(Fix1Base):
    def setUp(self):
        super().setUp()
        self.add_payment(60, 'Deposit', 300, sale=1)
        self.add_payment(61, 'Instalment', 200, sale=1)

    def edit(self, pid, **form):
        data = {'reference_type': 'sale', 'Sale_SaleID': '1', 'PaymentDate': '2026-10-03', 'PaymentMethod': 'Cash'}
        data.update(form)
        return self.post(url('payment.edit', payment_id=pid), data)

    def test_deposit_with_later_instalment_cannot_change_type(self):
        r, page, _ = self.edit(60, PaymentType='Full Payment', AmountPaid='800')
        self.assertIn('This deposit already has later payments, so its type cannot be changed.', page)
        r, page, _ = self.edit(60, PaymentType='Instalment', AmountPaid='300')
        self.assertIn('This deposit already has later payments', page)

    def test_deposit_amount_edit_rules(self):
        r, page, _ = self.edit(60, PaymentType='Deposit', AmountPaid='1000')
        self.assertIn(DEPOSIT_TOTAL_MSG.format(1000), page)
        r, page, _ = self.edit(60, PaymentType='Deposit', AmountPaid='800.01')    # 200 already paid later
        self.assertIn('exceeds the remaining balance of Rs. 800.00', page)
        r, _, flashes = self.edit(60, PaymentType='Deposit', AmountPaid='350')
        self.assertEqual(r.status_code, 302, flashes)
        self.assertEqual(self.payments(PaymentID=60)[0]['AmountPaid'], 350.0)

    def test_instalment_edit_excludes_itself(self):
        r, _, _ = self.edit(61, PaymentType='Instalment', AmountPaid='700')
        self.assertEqual(r.status_code, 302)
        r, page, _ = self.edit(61, PaymentType='Instalment', AmountPaid='700.01')
        self.assertIn('exceeds the remaining balance of Rs. 700.00', page)
        r, page, _ = self.edit(61, PaymentType='Deposit', AmountPaid='100')
        self.assertIn('A deposit can only be the first payment', page)

    def test_lone_deposit_cannot_be_edited_into_full_value(self):
        self.db.tables['Payment'] = [p for p in self.db.tables['Payment'] if p['PaymentID'] != 61]
        r, page, _ = self.edit(60, PaymentType='Deposit', AmountPaid='1000')
        self.assertIn(DEPOSIT_TOTAL_MSG.format(1000), page)
        r, _, _ = self.edit(60, PaymentType='Full Payment', AmountPaid='1000')   # no later payments: allowed
        self.assertEqual(r.status_code, 302)

    def test_online_payments_stay_locked(self):
        r, _, flashes = self.post(url('payment.edit', payment_id=50), {'PaymentType': 'Deposit', 'AmountPaid': '1'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('cannot be edited or deleted', flashes[0])
        r, _, flashes = self.post(url('payment.delete', payment_id=50))
        self.assertIn('cannot be edited or deleted', flashes[0])
        self.assertEqual(len(self.payments(PaymentID=50)), 1)

    def test_rule_unit_cases(self):
        hist = [{'PaymentID': 1, 'PaymentType': 'Deposit', 'AmountPaid': 100}]
        self.assertIsNone(pay.check_payment_rules('Instalment', 900, 1000, hist))
        self.assertEqual(pay.check_payment_rules('Instalment', 900.01, 1000, hist)[0], 'AmountPaid')
        self.assertEqual(pay.check_payment_rules('Instalment', 1, 1000, [])[1], INSTALMENT_MSG)
        self.assertIsNone(pay.check_payment_rules('Full Payment', 900, 1000, hist))
        self.assertEqual(pay.payment_summary(1000, hist)['status'], 'Partially paid')
        self.assertEqual(pay.payment_summary(1000, [])['status'], 'Unpaid')
        self.assertEqual(pay.payment_summary(100, hist)['status'], 'Paid')


# --------------------------------------------------------------------------- 2.4 date
class D1Dates(Fix1Base):
    def test_default_today_in_both_modes(self):
        for path in (url('payment.create'), url('payment.create', sale=1)):
            _, page = self.get(path)
            self.assertRegex(page, r'name="PaymentDate"\s+value="%s"' % TODAY, path)

    def test_sale_date_never_copied(self):
        _, page = self.get(url('payment.create', sale=1))
        self.assertNotIn('sale_date && !payDateInput.value', page)
        self.assertNotRegex(page, r'name="PaymentDate"\s+value="2026-10-01"')

    def test_future_date_refused_today_allowed(self):
        r, page, _ = self.pay_sale(1, 'Deposit', '100', date=TOMORROW)
        self.assertIn('Payment date cannot be in the future.', page)
        r, _, _ = self.pay_sale(1, 'Deposit', '100', date=TODAY)
        self.assertEqual(r.status_code, 302)

    def test_edit_keeps_stored_date(self):
        self.add_payment(60, 'Deposit', 300, sale=1)
        _, page = self.get(url('payment.edit', payment_id=60))
        self.assertRegex(page, r'name="PaymentDate"\s+value="2026-10-03"')


# --------------------------------------------------------------------------- 2.5 context card
class C1Context(Fix1Base):
    def test_sale_context_card(self):
        _, page = self.get(url('payment.create', sale=1))
        for text in ('Honda CB Shine (2025), Red', 'VIN-SHINE-10', 'Alice Martin', '2026-10-01',
                     'Rs. 1,000.00', 'Rs. 0.00'):
            self.assertIn(text, page)

    def test_sale_context_null_optional_data(self):
        _, page = self.get(url('payment.create', sale=2))
        self.assertIn('Honda Wave 110 (2024)', page)
        self.assertIn('data-ctx="vin">-<', page)
        self.assertIn('data-ctx="customer_name">-<', page)
        self.assertIn('Rs. 800.00', page)

    def test_json_endpoints(self):
        r = self.client.get(url('payment.sale_info', sale_id=1))
        d = r.get_json()
        self.assertEqual((d['brand'], d['model'], d['year'], d['colour'], d['vin'], d['customer_name']),
                         ('Honda', 'CB Shine', 2025, 'Red', 'VIN-SHINE-10', 'Alice Martin'))
        self.assertEqual((d['total_amount'], d['total_paid'], d['remaining']), (1000.0, 0.0, 1000.0))
        d = self.client.get(url('payment.appointment_info', appt_id=102)).get_json()
        self.assertEqual((d['registration'], d['bike'], d['customer_name'], d['appointment_date'],
                          d['appointment_status'], d['total_amount']),
                         ('AB123', 'Honda Wave 110', 'Bob Lee', '2026-10-05', 'Confirmed', 500.0))
        d = self.client.get(url('payment.appointment_info', appt_id=107)).get_json()
        self.assertEqual((d['registration'], d['bike'], d['customer_name']), (None, '-', None))
        self.assertEqual(self.client.get(url('payment.sale_info', sale_id=999)).status_code, 404)

    def test_appointment_context_rendered_when_selected(self):
        _, page = self.get(url('payment.create', prefill_appt=102))
        for text in ('AB123', 'Honda Wave 110', 'Bob Lee', 'Confirmed', 'Rs. 500.00'):
            self.assertIn(text, page)

    def test_type_help_and_script(self):
        _, page = self.get(url('payment.create', sale=1))
        self.assertIn(pay.PAYMENT_TYPE_HELP, page)
        self.assertIn("type === 'Full Payment'", page)
        self.assertIn('amountInput.readOnly = true', page)
        # the script reads the raw balance, not the "Rs. 1,000.00" text (browser-found bug)
        self.assertIn('data-value="1000.0"', page)
        self.assertNotIn("textContent.replace(/[^0-9.]/g", page)


# --------------------------------------------------------------------------- 2.6 payable appointments
class A1Payable(Fix1Base):
    def test_only_payable_statuses_listed(self):
        _, page = self.get(url('payment.create'))
        options = [int(v) for v in re.findall(r'<option\s+value="(\d+)"', page.split('id="Appointment_AppointmentID"')[1].split('</select>')[0])]
        self.assertEqual(sorted(options), [102, 103, 104, 107])

    def test_paid_appointments_not_listed(self):
        self.add_payment(60, 'Full Payment', 500, appt=102)
        _, page = self.get(url('payment.create'))
        self.assertNotRegex(page, r'<option\s+value="102"')

    def test_direct_post_for_non_payable_refused(self):
        for appt_id, status in ((105, 'Cancelled'), (101, 'Pending'), (106, 'No Show')):
            r, page, _ = self.pay_appt(appt_id, 'Full Payment', '500')
            self.assertIn(f'This one is {status}.', page)
        self.assertEqual(self.payments(Appointment_AppointmentID=105), [])

    def test_edit_existing_payment_of_cancelled_appointment(self):
        self.add_payment(60, 'Deposit', 100, appt=105)
        _, page = self.get(url('payment.edit', payment_id=60))
        self.assertRegex(page, r'<option\s+value="105"\s+selected>\s*APPT-#105[^<]*\(Cancelled\)')
        r, _, _ = self.post(url('payment.edit', payment_id=60), {
            'Appointment_AppointmentID': '105', 'PaymentType': 'Deposit', 'AmountPaid': '150',
            'PaymentDate': '2026-10-03', 'PaymentMethod': 'Card'})
        self.assertEqual(r.status_code, 302)
        r, page, _ = self.post(url('payment.edit', payment_id=60), {
            'Appointment_AppointmentID': '106', 'PaymentType': 'Deposit', 'AmountPaid': '150',
            'PaymentDate': '2026-10-03', 'PaymentMethod': 'Card'})
        self.assertIn('This one is No Show.', page)

    def test_options_are_batched(self):
        self.db.log.clear()
        self.get(url('payment.create'))
        svc = [e for e in self.db.log if e[0] == 'appointment_service' and e[1] == 'select']
        self.assertLessEqual(len(svc), 2)


# --------------------------------------------------------------------------- 2.7 sale form
class F1SaleForm(Fix1Base):
    def test_colour_in_bike_labels(self):
        _, page = self.get(url('sale.create'))
        self.assertIn('NB-12 - Honda CB Shine (2026), Black', page)
        _, page = self.get(url('sale.index'))
        self.assertIn('NB-10 - Honda CB Shine (2025), Red', page)
        self.assertIn('NB-11 - Honda Wave 110 (2024)<', page)
        _, page = self.get(url('sale.view', sale_id=1))
        self.assertIn('Honda CB Shine (2025), Red', page)

    def test_sale_date_defaults_to_today(self):
        _, page = self.get(url('sale.create'))
        self.assertRegex(page, r'name="SaleDate"\s+value="%s"' % TODAY)

    def test_only_salespeople_listed(self):
        _, page = self.get(url('sale.create'))
        sel = page.split('id="Employee_EmployeeID"')[1].split('</select>')[0]
        self.assertIn('Sam Seller', sel)
        self.assertNotIn('Max Wrench', sel)
        self.assertIn('The salesperson who processed this sale.', page)

    def test_no_salesperson_role(self):
        self.db.tables['Role'] = [{'Role_ID': 2, 'Role_Name': 'Mechanic'}]
        _, page = self.get(url('sale.create'))
        self.assertIn('Create a role named Salesperson and assign it to employees.', page)
        sel = page.split('id="Employee_EmployeeID"')[1].split('</select>')[0]
        self.assertEqual(re.findall(r'<option\s+value="(\d+)"', sel), [])

    def test_create_refuses_non_salesperson(self):
        r, page, _ = self.post(url('sale.create'), {
            'Customer_CustomerID': '1', 'New_MotorBike_NB_ID': '12', 'Employee_EmployeeID': '2',
            'SaleDate': TODAY, 'TotalAmount': '1200'})
        self.assertIn('Please choose a salesperson from the list.', page)
        self.assertEqual(len(self.rows('Sale')), 2)
        r, _, _ = self.post(url('sale.create'), {
            'Customer_CustomerID': '1', 'New_MotorBike_NB_ID': '12', 'Employee_EmployeeID': '1',
            'SaleDate': TODAY, 'TotalAmount': '1200'})
        self.assertEqual(r.status_code, 302)

    def test_edit_keeps_non_salesperson_marked(self):
        self.db.tables['Sale'][0]['Employee_EmployeeID'] = 2
        _, page = self.get(url('sale.edit', sale_id=1))
        self.assertRegex(page, r'<option\s+value="2"\s+selected>\s*Max Wrench \(not a salesperson\)')
        r, _, flashes = self.post(url('sale.edit', sale_id=1), {
            'Customer_CustomerID': '1', 'New_MotorBike_NB_ID': '10', 'Employee_EmployeeID': '2',
            'SaleDate': '2026-10-01', 'TotalAmount': '1000'})
        self.assertEqual(r.status_code, 302, flashes)

    def test_reservation_sale_unaffected(self):
        _, page = self.get(url('sale.edit', sale_id=2))
        self.assertIn('The motorbike of an online reservation cannot be changed.', page)
        r, _, _ = self.post(url('sale.edit', sale_id=2), {
            'Customer_CustomerID': '2', 'New_MotorBike_NB_ID': '12', 'Employee_EmployeeID': '',
            'SaleDate': '2026-10-02', 'TotalAmount': '900'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.rows('Sale', SaleID=2)[0]['New_MotorBike_NB_ID'], 11)
        self.assertIsNone(self.rows('Sale', SaleID=2)[0]['Employee_EmployeeID'])
        r, _, flashes = self.post(url('sale.delete', sale_id=2))
        self.assertIn('belongs to online reservation', flashes[0])


# --------------------------------------------------------------------------- security
class X1Security(Fix1Base):
    def test_login_required(self):
        anon = APP.test_client()
        for method, path in (('get', url('payment.create', sale=1)), ('post', url('payment.create', sale=1)),
                             ('get', url('payment.create')), ('get', url('payment.sale_info', sale_id=1)),
                             ('get', url('payment.appointment_info', appt_id=102)), ('get', url('sale.view', sale_id=1))):
            r = getattr(anon, method)(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn('/auth/login', r.headers['Location'])

    def test_no_audit_fields_written(self):
        self.pay_sale(1, 'Deposit', '300')
        inserted = [rows for table, rows in self.db.inserts if table == 'Payment'][-1][0]
        for col in ('Created_By', 'Updated_By', 'Date_Created', 'Date_Updated'):
            self.assertNotIn(col, inserted)


if __name__ == '__main__':
    unittest.main(verbosity=1)
