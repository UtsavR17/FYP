"""
Fix Phase 5 (ISS-07, DEC-4): customer deletion and online account deactivation.

Fake supabase-py client (the same fake also stands in for the service-role client and its
auth.admin recorder) plus the Flask test client. No database, no network.

Run from the repo root:  venv/Scripts/python -W ignore tests/test_fix5.py
"""
import unittest
from datetime import datetime, timezone

import harness
from harness import APP, Base, url

from app.modules.customer import accounts

U_CUST = '11111111-1111-4111-8111-111111111111'    # customer-only login
U_SUPP = '22222222-2222-4222-8222-222222222222'    # also a supplier login
U_STAFF = '33333333-3333-4333-8333-333333333333'   # also a staff login
U_APP = '44444444-4444-4444-8444-444444444444'     # applicant of a supplier application
FUTURE = '2126-10-01T00:00:00Z'


def customer(cid, first, auth=None, email=None):
    return {'CustomerID': cid, 'FirstName': first, 'LastName': 'Test', 'PhoneNumber': f'5{cid:03d}',
            'Email': email or f'{first.lower()}@example.mu', 'Street': 'Royal Road', 'Town': 'Curepipe',
            'NIC': f'N{cid}', 'HomeNumber': None, 'PostCode': None, 'AuthUserID': auth}


def bike(bid, cid):
    return {'BikeID': bid, 'RegistrationNumber': f'R{bid}', 'VIN': f'V{bid}', 'Year': 2020,
            'Model_Model_No': 1, 'Customer_CustomerID': cid}


def tables():
    return {
        'Customer': [customer(1, 'Ana', U_CUST), customer(2, 'Ben'), customer(3, 'Cleo', U_SUPP),
                     customer(4, 'Dev', U_STAFF), customer(5, 'Eva', U_CUST), customer(6, 'Finn', U_APP)],
        'Customer_bike': [bike(10, 1), bike(11, 1), bike(20, 2), bike(50, 5), bike(51, 5)],
        'Appointment': [], 'Sale': [], 'Online_Order': [],
        'Supplier': [{'SupplierID': 1, 'SupplierName': 'Parts Ltd', 'AuthUserID': U_SUPP}],
        'Staff_User': [{'AuthUserID': U_STAFF}],
        'Supplier_Application': [],
        'Model': [{'Model_No': 1, 'Brand_Brand_ID': 1, 'Description': 'CB Shine'}],
    }


class P5Base(Base):
    tables = staticmethod(tables)

    def setUp(self):
        super().setUp()
        self.admin = self.db.auth.admin
        for uid, email in ((U_CUST, 'ana@example.mu'), (U_SUPP, 'cleo@example.mu'),
                           (U_STAFF, 'dev@example.mu'), (U_APP, 'finn@example.mu')):
            self.admin.add_user(uid, email)

    def tearDown(self):
        harness.FAKE_ADMIN_MODULE.supabase_admin = None

    def auth_ops(self, op):
        return [c for c in self.admin.calls if c[0] == op]

    def appointment(self, aid, bike_id):
        self.db.tables['Appointment'].append({'AppointmentID': aid, 'Customer_bike_BikeID': bike_id,
                                              'Status': 'Completed'})

    def delete(self, cid):
        return self.post(url('customer.delete', customer_id=cid))


# =============================================================================
# 2.1 History helper
# =============================================================================

class HistoryHelper(P5Base):
    def history(self, cid):
        return accounts.customer_history(cid)

    def test_no_history_and_no_bikes(self):
        h = self.history(6)
        self.assertFalse(h.has_history)
        self.assertEqual((h.appointments, h.sales, h.online_orders, h.unused_bike_ids, h.used_bike_ids),
                         (0, 0, 0, [], []))

    def test_only_unused_bikes(self):
        h = self.history(1)
        self.assertFalse(h.has_history)
        self.assertEqual(h.unused_bike_ids, [10, 11])
        self.assertEqual(h.used_bike_ids, [])

    def test_used_bike(self):
        self.appointment(1, 11)
        self.appointment(2, 11)
        h = self.history(1)
        self.assertTrue(h.has_history)
        self.assertEqual(h.appointments, 2)
        self.assertEqual((h.unused_bike_ids, h.used_bike_ids), ([10], [11]))

    def test_sales(self):
        self.db.tables['Sale'].append({'SaleID': 1, 'Customer_CustomerID': 2})
        h = self.history(2)
        self.assertTrue(h.has_history)
        self.assertEqual(h.sales, 1)
        self.assertEqual(h.summary(), '1 sale')

    def test_online_orders(self):
        self.db.tables['Online_Order'] += [{'OrderID': i, 'Customer_CustomerID': 6} for i in (1, 2)]
        h = self.history(6)
        self.assertTrue(h.has_history)
        self.assertEqual(h.summary(), '2 online orders')

    def test_mixed_summary_and_other_customers_ignored(self):
        self.appointment(1, 10)
        self.appointment(2, 11)
        self.appointment(3, 20)          # Ben's bike: not counted for Ana
        self.db.tables['Sale'].append({'SaleID': 1, 'Customer_CustomerID': 1})
        self.db.tables['Online_Order'] += [{'OrderID': i, 'Customer_CustomerID': 1} for i in (1, 2, 3)]
        self.db.tables['Online_Order'].append({'OrderID': 9, 'Customer_CustomerID': 2})
        h = self.history(1)
        self.assertEqual(h.summary(), '2 appointments, 1 sale and 3 online orders')

    def test_batched_queries(self):
        for i in range(1, 6):
            self.appointment(i, 10)
        self.history(1)
        appt_queries = [e for e in self.db.log if e[0] == 'Appointment' and e[1] == 'select']
        self.assertEqual(len(appt_queries), 1)
        self.assertIn(('Appointment', 'in', 'Customer_bike_BikeID', (10, 11)), self.db.log)

    def test_null_safe(self):
        self.db.tables['Customer_bike'].append({'BikeID': None, 'Customer_CustomerID': 2})
        self.db.tables['Appointment'].append({'AppointmentID': 7, 'Customer_bike_BikeID': None})
        h = self.history(2)
        self.assertEqual(h.unused_bike_ids, [20])
        self.assertFalse(h.has_history)

    def test_lookup_failure_raises(self):
        self.db.fail_tables.add('Sale')
        with self.assertRaises(Exception):
            self.history(1)


# =============================================================================
# 2.2 Delete
# =============================================================================

class DeleteWithoutHistory(P5Base):
    def test_customer_only_login_is_deleted_with_bikes(self):
        r, _, flashes = self.delete(1)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.rows('Customer', CustomerID=1), [])
        self.assertEqual(self.rows('Customer_bike', Customer_CustomerID=1), [])
        self.assertEqual(len(self.rows('Customer_bike')), 3)            # other customers' bikes stay
        self.assertEqual(self.auth_ops('delete_user'), [('delete_user', U_CUST)])
        self.assertNotIn(U_CUST, self.admin.users)
        self.assertIn('Customer "Ana Test" was deleted successfully with 2 garage bikes.', flashes)
        self.assertIn('Their online login was removed, so they can no longer sign in.', flashes)

    def test_order_rows_first_login_last(self):
        self.delete(1)
        ops = [e[0] for e in self.db.log if len(e) == 3 and e[1] == 'delete']
        self.assertEqual(ops, ['Customer_bike', 'Customer'])
        self.assertEqual(self.admin.calls[-1], ('delete_user', U_CUST))

    def test_bike_delete_is_scoped_to_the_customer(self):
        self.delete(1)
        self.assertIn(('Customer_bike', 'in', 'BikeID', (10, 11)), self.db.log)
        self.assertIn(('Customer_bike', 'eq', 'Customer_CustomerID', 1), self.db.log)

    def test_supplier_login_is_kept(self):
        _, _, flashes = self.delete(3)
        self.assertEqual(self.rows('Customer', CustomerID=3), [])
        self.assertEqual(self.auth_ops('delete_user'), [])
        self.assertIn(U_SUPP, self.admin.users)
        self.assertIn('The online login was kept because it is also used by staff or a supplier.', flashes)

    def test_staff_login_is_kept(self):
        _, _, flashes = self.delete(4)
        self.assertEqual(self.rows('Customer', CustomerID=4), [])
        self.assertEqual(self.auth_ops('delete_user'), [])
        self.assertIn('The online login was kept because it is also used by staff or a supplier.', flashes)

    def test_approved_or_pending_applicant_login_is_kept(self):
        for status in ('Approved', 'Pending'):
            with self.subTest(status=status):
                self.setUp()
                self.db.tables['Supplier_Application'] = [{'ApplicationID': 1, 'AuthUserID': U_APP,
                                                           'Status': status}]
                self.delete(6)
                self.assertEqual(self.rows('Customer', CustomerID=6), [])
                self.assertEqual(self.auth_ops('delete_user'), [])

    def test_rejected_applicant_login_is_deleted(self):
        self.db.tables['Supplier_Application'] = [{'ApplicationID': 1, 'AuthUserID': U_APP, 'Status': 'Rejected'}]
        self.delete(6)
        self.assertEqual(self.auth_ops('delete_user'), [('delete_user', U_APP)])

    def test_without_login(self):
        _, _, flashes = self.delete(2)
        self.assertEqual(self.rows('Customer', CustomerID=2), [])
        self.assertEqual(self.admin.calls, [])
        self.assertEqual(flashes, ['Customer "Ben Test" was deleted successfully with 1 garage bike.'])

    def test_protection_lookup_failure_keeps_login(self):
        for table in ('Staff_User', 'Supplier', 'Supplier_Application'):
            with self.subTest(table=table):
                self.setUp()
                self.db.fail_tables.add(table)
                _, _, flashes = self.delete(1)
                self.assertEqual(self.rows('Customer', CustomerID=1), [])
                self.assertEqual(self.auth_ops('delete_user'), [])
                self.assertIn(U_CUST, self.admin.users)
                self.assertIn('The online login was kept because it is also used by staff or a supplier.',
                              flashes)

    def test_login_deletion_failure_warns_with_email(self):
        self.admin.fail_ops.add('delete_user')
        _, _, flashes = self.delete(1)
        self.assertEqual(self.rows('Customer', CustomerID=1), [])
        self.assertIn('Customer "Ana Test" was deleted successfully with 2 garage bikes.', flashes)
        self.assertIn('Customer deleted, but the online login could not be removed. Deactivate or remove it '
                      'in Supabase Authentication. Email: ana@example.mu.', flashes)
        self.assertFalse(any('login was removed' in f for f in flashes))

    def test_service_client_not_configured_warns(self):
        harness.FAKE_ADMIN_MODULE.supabase_admin = None
        _, _, flashes = self.delete(1)
        self.assertEqual(self.rows('Customer', CustomerID=1), [])
        self.assertTrue(any(f.startswith('Customer deleted, but the online login could not be removed.')
                            for f in flashes))

    def test_login_already_missing_counts_as_removed(self):
        del self.admin.users[U_CUST]
        _, _, flashes = self.delete(1)
        self.assertIn('Their online login was removed, so they can no longer sign in.', flashes)

    def test_customer_not_found(self):
        _, _, flashes = self.delete(99)
        self.assertEqual(flashes, ['Customer ID 99 was not found. Nothing was deleted.'])
        self.assertEqual(self.db.deletes, [])

    def test_fk_error_is_still_handled(self):
        self.db.raise_on[('Customer', 'delete')] = Exception('update or delete violates foreign key constraint')
        _, _, flashes = self.delete(2)
        self.assertTrue(flashes[0].startswith('Cannot delete "Ben Test" because they have associated'))
        self.assertEqual(self.admin.calls, [])

    def test_no_row_deleted_is_an_error_and_login_kept(self):
        self.db.raise_on[('Customer', 'delete')] = lambda q: setattr(q, 'filters', [lambda r: False])
        _, _, flashes = self.delete(1)
        self.assertEqual(flashes, ['Customer "Ana Test" was not deleted. Reload the page and try again.'])
        self.assertEqual(self.auth_ops('delete_user'), [])


class DeleteWithHistory(P5Base):
    def test_refused_with_counts_and_nothing_deleted(self):
        self.appointment(1, 10)
        self.appointment(2, 11)
        self.db.tables['Sale'].append({'SaleID': 1, 'Customer_CustomerID': 1})
        self.db.tables['Online_Order'] += [{'OrderID': i, 'Customer_CustomerID': 1} for i in (1, 2, 3)]
        r, _, flashes = self.delete(1)
        self.assertEqual(flashes, [
            'Cannot delete "Ana Test". This customer has 2 appointments, 1 sale and 3 online orders. '
            'Deleting would erase history. Nothing was deleted. '
            'To stop them signing in online, use Deactivate online account below.'])
        self.assertTrue(r.headers['Location'].endswith(url('customer.edit', customer_id=1) + '#online-account'))
        self.assertEqual(self.db.deletes, [])
        self.assertFalse([e for e in self.db.log if len(e) == 3 and e[1] == 'delete'])
        self.assertEqual(self.admin.calls, [])
        self.assertEqual(len(self.rows('Customer_bike', Customer_CustomerID=1)), 2)

    def test_unused_bikes_are_kept_when_another_bike_is_used(self):
        self.appointment(1, 51)
        self.delete(5)
        self.assertEqual(len(self.rows('Customer_bike', Customer_CustomerID=5)), 2)
        self.assertEqual(self.db.deletes, [])

    def test_without_login_returns_to_list(self):
        self.db.tables['Sale'].append({'SaleID': 1, 'Customer_CustomerID': 2})
        r, _, flashes = self.delete(2)
        self.assertEqual(flashes, ['Cannot delete "Ben Test". This customer has 1 sale. '
                                   'Deleting would erase history. Nothing was deleted.'])
        self.assertTrue(r.headers['Location'].endswith(url('customer.index')))
        self.assertEqual(self.db.deletes, [])

    def test_history_lookup_failure_deletes_nothing(self):
        self.db.fail_tables.add('Online_Order')
        _, _, flashes = self.delete(1)
        self.assertEqual(flashes, ['Could not check the history of "Ana Test", so nothing was deleted. '
                                   'Please try again.'])
        self.assertEqual(self.db.deletes, [])
        self.assertEqual(self.admin.calls, [])


class DeleteModalAndList(P5Base):
    def test_modal_states_what_is_removed(self):
        _, body = self.get(url('customer.index'))
        self.assertIn('id="deleteModalDetails"', body)
        self.assertIn('This removes the customer record and their garage bikes that have no appointments, '
                      'and deletes their online login', body)
        self.assertIn('data-delete-details="This removes the customer record and their garage bikes that have '
                      'no appointments. A customer with', body)                 # Ben, no login

    def test_list_badge_without_auth_calls(self):
        _, body = self.get(url('customer.index'))
        self.assertEqual(body.count('>Online account</span>'), 5)
        self.assertEqual(self.admin.calls, [])
        self.assertNotIn(U_CUST, body)


# =============================================================================
# 2.3 Deactivate and reactivate
# =============================================================================

class Deactivation(P5Base):
    def test_deactivate_bans_for_about_100_years(self):
        r, _, flashes = self.post(url('customer.deactivate_login', customer_id=1))
        self.assertEqual(self.admin.attributes, [(U_CUST, {'ban_duration': '876000h'})])
        self.assertTrue(flashes[0].startswith('Online account of "Ana Test" deactivated.'))
        self.assertIn('ends within an hour', flashes[0])
        self.assertTrue(r.headers['Location'].endswith('#online-account'))
        self.assertEqual(len(self.rows('Customer')), 6)
        self.assertEqual(self.db.deletes, [])
        self.assertEqual(self.db.updates, [])

    def test_reactivate_removes_ban(self):
        self.admin.users[U_CUST]['banned_until'] = FUTURE
        _, _, flashes = self.post(url('customer.reactivate_login', customer_id=1))
        self.assertEqual(self.admin.attributes, [(U_CUST, {'ban_duration': 'none'})])
        self.assertEqual(flashes, ['Online account of "Ana Test" reactivated. They can sign in again.'])
        self.assertIsNone(self.admin.users[U_CUST]['banned_until'])

    def test_protected_logins_refused(self):
        for cid in (3, 4):
            for endpoint in ('customer.deactivate_login', 'customer.reactivate_login'):
                with self.subTest(cid=cid, endpoint=endpoint):
                    _, _, flashes = self.post(url(endpoint, customer_id=cid))
                    self.assertEqual(flashes, [accounts.PROTECTED_LOGIN_MSG])
        self.assertEqual(self.auth_ops('update_user_by_id'), [])

    def test_lookup_failure_refuses(self):
        self.db.fail_tables.add('Staff_User')
        _, _, flashes = self.post(url('customer.deactivate_login', customer_id=1))
        self.assertEqual(flashes, [accounts.PROTECTED_LOGIN_MSG])
        self.assertEqual(self.auth_ops('update_user_by_id'), [])

    def test_no_online_account(self):
        _, _, flashes = self.post(url('customer.deactivate_login', customer_id=2))
        self.assertEqual(flashes, ['"Ben Test" has no online account.'])
        self.assertEqual(self.admin.calls, [])

    def test_not_configured(self):
        harness.FAKE_ADMIN_MODULE.supabase_admin = None
        _, _, flashes = self.post(url('customer.deactivate_login', customer_id=1))
        self.assertEqual(flashes, [accounts.NOT_CONFIGURED_MSG])

    def test_update_failure_has_no_success_flash(self):
        self.admin.fail_ops.add('update_user_by_id')
        _, _, flashes = self.post(url('customer.deactivate_login', customer_id=1))
        self.assertEqual(flashes, ['Could not deactivate the online account: simulated update failure.'])

    def test_login_missing(self):
        del self.admin.users[U_CUST]
        _, _, flashes = self.post(url('customer.reactivate_login', customer_id=1))
        self.assertEqual(flashes, ['The online login of "Ana Test" no longer exists, so there is nothing to reactivate.'])

    def test_customer_not_found(self):
        r, _, flashes = self.post(url('customer.deactivate_login', customer_id=99))
        self.assertEqual(flashes, ['Customer ID 99 was not found.'])
        self.assertTrue(r.headers['Location'].endswith(url('customer.index')))


class StatusCard(P5Base):
    def card(self, cid):
        r, body = self.get(url('customer.edit', customer_id=cid))
        self.assertEqual(r.status_code, 200)
        return body[body.index('id="online-account"'):]     # the card is the last block on the page

    def test_active(self):
        card = self.card(1)
        self.assertIn('>Active</span>', card)
        self.assertIn('ana@example.mu', card)
        self.assertIn('Deactivate online account', card)
        self.assertNotIn('Reactivate online account', card)
        self.assertIn('up to an hour', card)
        self.assertEqual(self.admin.calls, [('get', U_CUST)])

    def test_deactivated(self):
        self.admin.users[U_CUST]['banned_until'] = FUTURE
        card = self.card(1)
        self.assertIn('>Deactivated</span>', card)
        self.assertIn('Reactivate online account', card)
        self.assertNotIn('Deactivate online account</button>', card)

    def test_expired_ban_is_active(self):
        self.admin.users[U_CUST]['banned_until'] = '2020-01-01T00:00:00.123456Z'
        self.assertIn('>Active</span>', self.card(1))

    def test_no_online_account(self):
        card = self.card(2)
        self.assertIn('>No online account</span>', card)
        self.assertIn('This customer has not registered online.', card)
        self.assertNotIn('<form', card)
        self.assertEqual(self.admin.calls, [])

    def test_login_missing(self):
        del self.admin.users[U_CUST]
        card = self.card(1)
        self.assertIn('>No online account</span>', card)
        self.assertIn('The linked online login no longer exists.', card)
        self.assertNotIn('<form', card)

    def test_protected_shows_no_buttons(self):
        for cid in (3, 4):
            with self.subTest(cid=cid):
                card = self.card(cid)
                self.assertIn('>Active</span>', card)
                self.assertIn('also used by staff or a supplier', card)
                self.assertNotIn('<form', card)

    def test_lookup_failure(self):
        self.admin.fail_ops.add('get')
        card = self.card(1)
        self.assertIn('Could not be checked', card)
        self.assertNotIn('<form', card)

    def test_card_forms_are_outside_the_customer_form(self):
        _, body = self.get(url('customer.edit', customer_id=1))
        self.assertLess(body.index('</form>'), body.index('id="online-account"'))

    def test_edit_still_saves(self):
        data = customer(1, 'Anna', U_CUST)
        data = {k: v or '' for k, v in data.items() if k not in ('CustomerID', 'AuthUserID')}
        r, _, flashes = self.post(url('customer.edit', customer_id=1), data)
        self.assertEqual(flashes, ['Customer "Anna Test" was updated successfully.'])
        self.assertEqual(self.rows('Customer', CustomerID=1)[0]['FirstName'], 'Anna')
        self.assertEqual(self.rows('Customer', CustomerID=1)[0]['AuthUserID'], U_CUST)

    def test_edit_validation_still_shown(self):
        r, body, _ = self.post(url('customer.edit', customer_id=1), {'FirstName': ''})
        self.assertEqual(r.status_code, 200)
        self.assertIn('First name is required.', body)
        self.assertIn('id="online-account"', body)


class Helpers(unittest.TestCase):
    def test_is_banned(self):
        now = datetime(2026, 11, 7, tzinfo=timezone.utc)
        self.assertFalse(accounts.is_banned({'banned_until': None}, now))
        self.assertFalse(accounts.is_banned({'banned_until': '2026-11-06T23:59:59Z'}, now))
        self.assertTrue(accounts.is_banned({'banned_until': '2126-10-01T00:00:00.5+00:00'}, now))
        self.assertTrue(accounts.is_banned({'banned_until': 'garbage'}, now))

    def test_fetch_login_fallback_and_bad_id(self):
        class _User:
            def model_dump(self):
                return {'email': 'x@y.mu', 'banned_until': FUTURE}

        class _Admin:
            def get_user_by_id(self, uid):
                return type('R', (), {'user': _User()})()

        client = type('C', (), {'auth': type('A', (), {'admin': _Admin()})()})()
        self.assertEqual(accounts.fetch_login(client, U_CUST), {'email': 'x@y.mu', 'banned_until': FUTURE})
        self.assertIsNone(accounts.fetch_login(client, 'not-a-uuid'))

    def test_protected_without_client(self):
        self.assertTrue(accounts.login_is_protected(U_CUST, None))
        self.assertFalse(accounts.login_is_protected(None, None))


# =============================================================================
# Methods and login
# =============================================================================

class MethodsAndLogin(P5Base):
    ACTIONS = ('customer.delete', 'customer.deactivate_login', 'customer.reactivate_login')

    def test_get_on_actions_is_405(self):
        for endpoint in self.ACTIONS:
            with self.subTest(endpoint=endpoint):
                r, _ = self.get(url(endpoint, customer_id=1))
                self.assertEqual(r.status_code, 405)
        self.assertEqual(self.db.deletes, [])
        self.assertEqual(self.admin.calls, [])

    def test_anonymous_redirects_to_login(self):
        anon = APP.test_client()
        for endpoint in self.ACTIONS:
            with self.subTest(endpoint=endpoint):
                r = anon.post(url(endpoint, customer_id=1))
                self.assertEqual(r.status_code, 302)
                self.assertIn(url('auth.login'), r.headers['Location'])
        r = anon.get(url('customer.edit', customer_id=1))
        self.assertIn(url('auth.login'), r.headers['Location'])
        self.assertEqual(self.db.deletes, [])
        self.assertEqual(self.admin.calls, [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
