"""
Sale flow tests: after a sale is recorded the admin lands on the locked payment page of that sale
(with fallbacks to the Sale view or the list), and the Sales list no longer has an Edit button
(the Sale view keeps it). Fake Supabase + Flask test client.

Run from the repo root:  venv/Scripts/python -W ignore tests/test_sale_flow.py
"""
import re
import unittest

from harness import APP, Base, url  # noqa: F401
from fake_supabase import Result
from test_fix1 import TODAY, base_tables

import app.modules.sale.routes as sale  # noqa: E402

NEW_ID = 3          # base_tables has Sales 1 and 2; bike 12 (Rs 1,200) is the only Available bike
PAY_FLASH = 'Sale 3 recorded. Record the first payment below.'
DUPLICATE = 'This motorbike is already linked to another sale.'


def sale_form(**over):
    data = {'Customer_CustomerID': '1', 'New_MotorBike_NB_ID': '12', 'Employee_EmployeeID': '1',
            'SaleDate': TODAY, 'TotalAmount': '1200'}
    data.update(over)
    return data


class FlowBase(Base):
    tables = staticmethod(base_tables)

    def create(self, **over):
        return self.post(url('sale.create'), sale_form(**over))

    def location(self, r):
        return r.headers.get('Location', '')


class CreateRedirect(FlowBase):
    def test_redirects_to_locked_payment_page(self):
        r, _, flashes = self.create()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.location(r).endswith(url('payment.create', sale=NEW_ID)), self.location(r))
        self.assertEqual(flashes, [PAY_FLASH])
        self.assertEqual(len(self.rows('Sale', SaleID=NEW_ID)), 1)
        self.assertEqual(self.rows('New_MotorBike', NB_ID=12)[0]['Status'], 'Sold')
        self.assertEqual(self.rows('Payment', Sale_SaleID=NEW_ID), [])        # nothing paid yet

    def test_payment_page_opens_in_sale_mode_with_context(self):
        r, _, _ = self.create()
        r, page = self.get(self.location(r))
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'Record a payment for Sale {NEW_ID}.', page)
        self.assertIn('id="payment-context"', page)
        self.assertNotRegex(page, r'id="payment-context"[^>]*hidden')
        self.assertIn('Honda CB Shine (2026), Black', page)
        self.assertIn('VIN-12', page)
        self.assertIn('Alice Martin', page)
        self.assertRegex(page, r'data-ctx="remaining"[^>]*\s+data-value="1200(\.0+)?"')
        self.assertIn('name="form_token"', page)
        self.assertNotIn('name="Appointment_AppointmentID"', page)      # no appointment choice in sale mode

    def test_payment_page_has_way_back_to_the_sale(self):
        r, _, _ = self.create()
        _, page = self.get(self.location(r))
        view = re.escape(url('sale.view', sale_id=NEW_ID))
        self.assertRegex(page, r'<a href="%s"[^>]*>\s*<i[^>]*></i>Back to Sale' % view)
        self.assertRegex(page, r'<a href="%s"[^>]*>Cancel</a>' % view)

    def test_leaving_without_paying_keeps_an_unpaid_sale(self):
        self.create()
        _, page = self.get(url('sale.view', sale_id=NEW_ID))
        self.assertIn('Unpaid', page)
        self.assertIn(f'href="{url("payment.create", sale=NEW_ID)}"', page)
        self.assertIn('Record payment', page)
        _, page = self.get(url('sale.index'))
        self.assertRegex(page, r'pay-status-unpaid">Unpaid<')

    def test_first_deposit_from_landing_page_returns_to_sale(self):
        r, _, _ = self.create()
        _, page = self.get(self.location(r))
        token = re.search(r'name="form_token" value="([^"]+)"', page).group(1)
        r, _, flashes = self.post(url('payment.create', sale=NEW_ID), {
            'form_token': token, 'reference_type': 'sale', 'Sale_SaleID': str(NEW_ID), 'PaymentType': 'Deposit',
            'AmountPaid': '200', 'PaymentDate': TODAY, 'PaymentMethod': 'Cash'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.location(r).endswith(url('sale.view', sale_id=NEW_ID)))
        self.assertEqual(flashes, ['Payment was recorded successfully.'])
        self.assertEqual(len(self.rows('Payment', Sale_SaleID=NEW_ID)), 1)


class CreateFallbacks(FlowBase):
    def test_validation_error_keeps_form(self):
        r, page, flashes = self.create(Customer_CustomerID='')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Customer is required.', page)
        self.assertEqual(flashes, [])
        self.assertEqual(self.rows('Sale', SaleID=NEW_ID), [])
        self.assertEqual(self.rows('New_MotorBike', NB_ID=12)[0]['Status'], 'Available')

    def test_invalid_total_keeps_form(self):
        r, page, flashes = self.create(TotalAmount='-5')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Total amount must be a valid number of 0 or more.', page)
        self.assertEqual(flashes, [])
        self.assertEqual(len(self.rows('Sale')), 2)

    def test_missing_id_falls_back(self):
        self.db.id_columns['Sale'] = None                  # insert returns a row without SaleID
        r, _, flashes = self.create()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.location(r).endswith(url('sale.index')), self.location(r))
        self.assertEqual(flashes, ['Sale was recorded successfully.'])
        self.assertEqual(len(self.rows('Sale')), 3)

    def test_zero_total_falls_back_to_sale_view(self):
        r, _, flashes = self.create(TotalAmount='0')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.location(r).endswith(url('sale.view', sale_id=NEW_ID)), self.location(r))
        self.assertEqual(flashes, [f'Sale {NEW_ID} recorded.'])

    def test_inserted_id_helper(self):
        self.assertEqual(sale._inserted_sale_id(Result([{'SaleID': 7}])), 7)
        self.assertEqual(sale._inserted_sale_id(Result({'SaleID': 8})), 8)
        for data in ([], None, [{}], [{'SaleID': None}], [{'SaleID': '7'}], [{'SaleID': 0}], [{'SaleID': True}]):
            with self.subTest(data=data):
                self.assertIsNone(sale._inserted_sale_id(Result(data)))
        self.assertIsNone(sale._inserted_sale_id(object()))

    def test_double_submit_still_refused(self):
        def unique_bike(q):
            nb = q.payload.get('New_MotorBike_NB_ID')
            if any(s.get('New_MotorBike_NB_ID') == nb for s in self.db.tables['Sale']):
                return Exception('duplicate key value violates unique constraint "sale_new_motorbike_nb_id_key"')
            return None
        self.db.raise_on[('Sale', 'insert')] = unique_bike
        r1, _, _ = self.create()
        self.assertEqual(r1.status_code, 302)
        r2, page, flashes = self.create()                  # the same form posted again
        self.assertEqual(r2.status_code, 200)
        self.assertIn(DUPLICATE, page)
        self.assertEqual(flashes, [])
        self.assertEqual(len(self.rows('Sale', New_MotorBike_NB_ID=12)), 1)

    def test_insert_failure_shows_error_without_redirect(self):
        self.db.raise_on[('Sale', 'insert')] = Exception('network down')
        r, page, _ = self.create()
        self.assertEqual(r.status_code, 200)
        self.assertIn('Could not record sale: network down', page)


class ListAndViewButtons(FlowBase):
    def test_list_has_view_and_delete_but_no_edit(self):
        _, page = self.get(url('sale.index'))
        self.assertNotIn('/sales/edit/', page)
        self.assertNotIn('fa-pen', page)
        for sid in (1, 2):
            self.assertIn(f'href="{url("sale.view", sale_id=sid)}"', page)
        self.assertIn(f'data-delete-url="{url("sale.delete", sale_id=1)}"', page)
        self.assertIn('id="deleteModal"', page)

    def test_reservation_sale_delete_still_blocked(self):
        _, page = self.get(url('sale.index'))
        self.assertNotIn(f'data-delete-url="{url("sale.delete", sale_id=2)}"', page)
        self.assertIn('Cancel the reservation from Online Orders.', page)
        r, _, flashes = self.post(url('sale.delete', sale_id=2))
        self.assertIn('belongs to online reservation', flashes[0])
        self.assertEqual(len(self.rows('Sale', SaleID=2)), 1)

    def test_view_keeps_edit_for_every_sale(self):
        for sid in (1, 2):                                 # walk-in sale and reservation sale
            with self.subTest(sale=sid):
                _, page = self.get(url('sale.view', sale_id=sid))
                self.assertIn(f'href="{url("sale.edit", sale_id=sid)}"', page)
                self.assertIn('Edit Sale', page)
        r, _ = self.get(url('sale.edit', sale_id=2))
        self.assertEqual(r.status_code, 200)

    def test_actions_column_markup(self):
        _, page = self.get(url('sale.index'))
        groups = re.findall(r'<div class="action-btn-group">(.*?)</div>\s*</td>', page, re.S)
        self.assertEqual(len(groups), 2)
        for g in groups:
            self.assertEqual(len(re.findall(r'class="btn btn-sm ', g)), 2)    # View + Delete


if __name__ == '__main__':
    unittest.main(verbosity=1)
