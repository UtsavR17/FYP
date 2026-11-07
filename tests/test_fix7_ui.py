"""
Fix Phase 7, items 2.2 to 2.4: collapsible sidebar (ISS-22), unpaid online order wording
(ISS-23) and the supplier portal brand hint (ISS-24).

The sidebar's behaviour (toggle, drawer, focus, persistence) was checked in a browser at
390, 768 and 1440 px; these tests pin the markup, the early-state script and the logic the
browser relies on, so they cannot silently disappear.

Run from the repo root:  venv/Scripts/python -W ignore tests/test_fix7_ui.py
"""
import re
import unittest

from harness import Base, url
import fixtures_ids


def read(path):
    return open(path, encoding='utf-8').read()


class Sidebar(Base):
    tables = staticmethod(fixtures_ids.tables)

    def page(self, endpoint, **kw):
        r, body = self.get(url(endpoint, **kw))
        self.assertEqual(r.status_code, 200, endpoint)
        return body

    def test_button_markup_on_every_kind_of_page(self):
        for endpoint, kw in (('dashboard.index', {}), ('sale.index', {}), ('customer.edit', {'customer_id': 1})):
            body = self.page(endpoint, **kw)
            button = re.search(r'<button[^>]*id="sidebarToggle"[^>]*>', body, re.S).group(0)
            self.assertIn('type="button"', button)
            self.assertIn('aria-label="Toggle navigation"', button)
            self.assertIn('aria-controls="sidebar"', button)
            self.assertIn('aria-expanded="true"', button)
            self.assertIn('<aside class="sidebar" id="sidebar">', body)
            self.assertIn('id="sidebarOverlay"', body)

    def test_early_state_script_runs_in_head_before_paint(self):
        body = self.page('dashboard.index')
        head = body[:body.index('<body')]
        self.assertIn("window.localStorage.getItem('adminSidebar') === 'collapsed'", head)
        self.assertIn("matchMedia('(min-width: 992px)')", head)
        self.assertIn("classList.add('sidebar-collapsed')", head)
        self.assertLess(head.index('css/admin.css'), head.index('adminSidebar'))

    def test_login_page_has_no_admin_sidebar_script(self):
        anon = self.client.application.test_client()
        body = anon.get(url('auth.login')).get_data(as_text=True)
        self.assertNotIn('adminSidebar', body)

    def test_active_link_highlighting_kept(self):
        body = self.page('sale.index')
        self.assertRegex(body, r'href="/sales/"\s+class="nav-link active"')


class SidebarAssets(unittest.TestCase):
    css = read('app/static/css/admin.css')
    js = read('app/static/js/admin.js')

    def test_desktop_collapse_css(self):
        block = self.css[self.css.index('COLLAPSIBLE SIDEBAR (Fix Phase 7'):]
        self.assertRegex(block, r'@media \(min-width: 992px\) \{\s*html\.sidebar-collapsed \.sidebar \{[^}]*translateX\(-100%\)[^}]*visibility: hidden')
        self.assertRegex(block, r'html\.sidebar-collapsed \.main-wrapper \{\s*margin-left: 0;')
        self.assertRegex(block, r'\.sidebar-toggle \{\s*display: flex;')
        self.assertIn('@media (prefers-reduced-motion: reduce)', block)
        self.assertIn('.sidebar-toggle:focus-visible', block)
        self.assertRegex(block, r'\.sidebar:not\(\.open\) \{\s*visibility: hidden;')

    def test_js_desktop_persistence(self):
        self.assertIn("const STORAGE_KEY   = 'adminSidebar';", self.js)
        self.assertIn("window.localStorage.setItem(STORAGE_KEY, collapsed ? 'collapsed' : 'open');", self.js)
        self.assertIn("rootEl.classList.toggle('sidebar-collapsed')", self.js)
        self.assertIn("window.dispatchEvent(new Event('resize'))", self.js)

    def test_js_drawer_behaviour(self):
        self.assertIn("sidebarToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');", self.js)
        self.assertIn("document.body.style.overflow = 'hidden';", self.js)
        self.assertIn("e.key === 'Escape' && drawerIsOpen()", self.js)
        self.assertIn("overlay.addEventListener('click', function () { closeSidebar(true); });", self.js)
        self.assertIn("e.target.closest('a[href]')", self.js)          # a chosen link closes the drawer
        self.assertIn('sidebarToggle.focus();', self.js)               # focus returns to the button
        self.assertIn("e.key !== 'Tab'", self.js)                      # focus stays in the drawer


def order_tables():
    t = fixtures_ids.tables()
    t['Online_Order'].append({'OrderID': 20, 'OrderDate': '2026-10-06', 'Customer_CustomerID': 1,
                              'Status': 'Pending Payment', 'FulfilmentMethod': 'Pickup', 'OrderType': 'Parts',
                              'TotalAmount': 400, 'StripeSessionID': 'cs_20', 'PaidAt': None, 'Sale_SaleID': None})
    t['Online_Order_Item'].append({'OrderItemID': 20, 'Online_Order_OrderID': 20, 'Stock_Stock_ID': 1,
                                   'ItemDescription': 'Brake Pad', 'Quantity': 2, 'UnitPrice': 200})
    return t


class UnpaidOrderWording(Base):
    """ISS-23: wording only. Pending Payment orders say they are unpaid and untouched."""
    tables = staticmethod(order_tables)

    def view(self, order_id):
        r, body = self.get(url('online_order.view', order_id=order_id))
        self.assertEqual(r.status_code, 200)
        return re.sub(r'\s+', ' ', body)

    def test_pending_payment_view(self):
        body = self.view(20)
        self.assertIn('This order has not been paid. Stock has not been changed.', body)
        self.assertRegex(body, r'Payment status</label> <div class="readonly-value">Not paid</div>')
        modal = body[body.index('id="cancelOrderModal"'):]
        self.assertIn('Cancel this unpaid order?', modal)
        self.assertIn('No stock or payment is affected.', modal)
        self.assertNotIn('refund', modal.lower()[:modal.lower().index('</form>')])

    def test_paid_view_keeps_refund_wording(self):
        body = self.view(1)
        self.assertNotIn('This order has not been paid.', body)
        self.assertRegex(body, r'Payment status</label> <div class="readonly-value">Paid</div>')
        modal = body[body.index('id="cancelOrderModal"'):]
        self.assertIn('Cancel online order 1?', modal)
        self.assertIn('refund the payment in the Stripe Dashboard', modal)
        self.assertNotIn('Cancel this unpaid order?', modal)

    def test_list_payment_status(self):
        _, body = self.get(url('online_order.index'))
        body = re.sub(r'\s+', ' ', body)
        self.assertIn('Payment: Not paid', body)
        self.assertIn('Payment: Paid', body)

    def test_cancelling_unpaid_order_changes_no_stock_and_calls_no_function(self):
        _, _, flashes = self.post(url('online_order.cancel', order_id=20), {'expected_status': 'Pending Payment'})
        self.assertEqual(self.rows('Online_Order', OrderID=20)[0]['Status'], 'Cancelled')
        self.assertEqual([u for u in self.db.updates if u[0] == 'Stock'], [])
        self.assertEqual(self.db.rpc_calls, [])
        self.assertEqual(self.rows('Stock', Stock_ID=1)[0]['QOH'], 5)
        self.assertTrue(any('was cancelled' in f for f in flashes), flashes)

    def test_cancelling_paid_order_still_restores_stock(self):
        def cancel_paid(db, params):          # stands in for the database function
            order_id = params['p_order_id']
            for item in [i for i in db.tables['Online_Order_Item'] if i['Online_Order_OrderID'] == order_id]:
                for stock in db.tables['Stock']:
                    if stock['Stock_ID'] == item['Stock_Stock_ID']:
                        stock['QOH'] += item['Quantity']
            for order in db.tables['Online_Order']:
                if order['OrderID'] == order_id:
                    order['Status'] = 'Cancelled'
            return True
        self.db.rpc_handlers['cancel_paid_online_order'] = cancel_paid
        self.post(url('online_order.cancel', order_id=1), {'expected_status': 'Paid'})
        self.assertEqual(self.db.rpc_calls, [('cancel_paid_online_order', {'p_order_id': 1})])
        self.assertEqual(self.rows('Stock', Stock_ID=1)[0]['QOH'], 7)


if __name__ == '__main__':
    unittest.main(verbosity=1)
