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


if __name__ == '__main__':
    unittest.main(verbosity=1)
