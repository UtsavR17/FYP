"""
Fix Phase 7, item 2.1 (ISS-21, DEC-15): the Admin Panel shows record ids as plain numbers.

Covers the shared helper and normaliser, a scan of every rendered page (no letter-prefixed
ids anywhere), type badges, flash and modal texts, JSON endpoints, and searches: the queries
recorded before Phase 7 return exactly the same rows, and the new forms work too.

Run from the repo root:  venv/Scripts/python -W ignore tests/test_fix7_ids.py
"""
import re
import unittest

from harness import APP, Base, url
import fixtures_ids
import record_searches
import test_smoke

from app.utils import ids
from app.utils.order_ref import format_order_ref, parse_order_query

# Old id formats: SALE-5, APPT-#3, PO-12, NB-7, ORD-000012, PAY-4, SP-3, and "#5".
OLD_ID = re.compile(r'\b(?:SALE|APPT|PO|NB|ORD|PAY|SP)-#?\d|(?<![\w&/])#\d')
SCRIPT_STYLE = re.compile(r'<(script|style)\b.*?</\1>', re.S | re.I)
TAG = re.compile(r'<[^>]+>')
NAMED_ATTRS = re.compile(r'(?:data-record-name|title|aria-label|placeholder|onsubmit)="([^"]*)"')


def old_ids_in(body):
    """Old-format ids in the visible text and in the attributes people read (modal names, titles)."""
    body = SCRIPT_STYLE.sub(' ', body)
    hits = OLD_ID.findall(TAG.sub(' ', body))
    for value in NAMED_ATTRS.findall(body):
        hits += OLD_ID.findall(value)
    return hits


class Helper(unittest.TestCase):
    def test_display_id(self):
        self.assertEqual(ids.display_id(5), '5')
        self.assertEqual(ids.display_id('005'), '5')
        self.assertEqual(ids.display_id(None), '-')
        self.assertEqual(ids.display_id('x'), '-')

    def test_typed_id(self):
        self.assertEqual(ids.typed_id('sale', 5), 'Sale 5')
        self.assertEqual(ids.typed_id('order', 12), 'Online order 12')
        self.assertEqual(ids.typed_id('appointment', '3'), 'Appointment 3')

    def test_order_ref_wrappers(self):
        self.assertEqual(format_order_ref(12), '12')
        self.assertEqual(format_order_ref(None), '-')
        for text in ('ORD-000012', 'ord12', 'ORD12', '000012', '12', 'order 12', '#12'):
            self.assertEqual(parse_order_query(text), 12, text)
        self.assertIsNone(parse_order_query('SALE-12'))

    def test_normaliser_accepts_old_and_new_forms(self):
        cases = {
            'sale': ['5', '#5', '005', 'SALE-5', 'sale-5', 'Sale 5', 'sale5'],
            'appointment': ['3', 'APPT-#3', 'APPT-3', 'appt #3', 'Appointment 3'],
            'purchase_order': ['12', 'PO-12', 'po 12'],
            'motorbike': ['7', 'NB-7', 'nb7'],
            'payment': ['4', 'PAY-4', 'Payment 4'],
            'application': ['5', 'APP-5', 'Application 5', '#5'],
        }
        for kind, texts in cases.items():
            expected = int(re.sub(r'\D', '', texts[0]))
            for text in texts:
                self.assertEqual(ids.parse_id_query(text, kind), expected, (kind, text))

    def test_normaliser_rejects_other_text(self):
        for text in ('', '  ', 'PO-5', 'sale', '5a', 'SALE-', '0', 'SALE-0', '12-3', 'drop table', '1' * 10):
            self.assertIsNone(ids.parse_id_query(text, 'sale'), text)

    def test_legacy_ref(self):
        self.assertEqual(ids.legacy_ref('sale', 5), 'sale-5')
        self.assertEqual(ids.legacy_ref('appointment', 3), 'appt-#3')
        self.assertEqual(ids.legacy_ref('order', 12), 'ord-000012')
        self.assertEqual(ids.legacy_ref('sale', None), '')


class Pages(Base):
    tables = staticmethod(fixtures_ids.tables)

    def test_no_page_shows_an_old_id_format(self):
        offenders, rendered = {}, 0
        for rule in APP.url_map.iter_rules():
            if 'GET' not in rule.methods or rule.endpoint in test_smoke.SKIP:
                continue
            path = rule.rule
            for arg in rule.arguments:
                value = test_smoke.ARG_VALUES.get(arg, '1')
                path = path.replace(f'<int:{arg}>', '1').replace(f'<string:{arg}>', value)
                path = path.replace(f'<{arg}>', value)
            self.db.tables = fixtures_ids.tables()
            r = self.client.get(path)
            if r.status_code == 200:
                rendered += 1
                hits = old_ids_in(r.get_data(as_text=True))
                if hits:
                    offenders[path] = sorted(set(hits))
        self.assertEqual(offenders, {})
        self.assertGreater(rendered, 60)      # the scan really covered the Admin pages

    def test_source_builds_no_old_formats(self):
        """Every template and module, including the supplier portal pages the fake cannot sign in to."""
        import pathlib
        building = re.compile(r"(?:SALE|APPT|PO|NB|ORD|PAY|SP)-(?:\{|'\s*~|#\{)|#\{\{|'#'\s*~|f['\"][^'\"]*#\{")
        skip = {'ids.py', 'order_ref.py'}
        offenders = []
        for path in pathlib.Path('app').rglob('*'):
            if path.suffix not in ('.py', '.html', '.js') or path.name in skip or 'vendor' in path.parts:
                continue
            for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                code = line.split('#', 1)[0] if path.suffix == '.py' and line.lstrip().startswith('#') else line
                if building.search(code):
                    offenders.append(f'{path}:{n}: {line.strip()}')
        self.assertEqual(offenders, [])

    def test_list_id_columns_are_numbers(self):
        _, body = self.get(url('sale.index'))
        self.assertRegex(body, r'<strong>\s*15\s*</strong>')
        _, body = self.get(url('purchase_order.index'))
        self.assertRegex(body, r'<strong>\s*12\s*</strong>')
        _, body = self.get(url('new_motorbike.index'))
        self.assertRegex(body, r'<strong>\s*7\s*</strong>')

    def test_titles_use_words(self):
        for endpoint, kw, title in (('sale.view', {'sale_id': 1}, 'Sale 1'),
                                    ('purchase_order.view', {'po_id': 12}, 'Purchase Order 12'),
                                    ('appointment.view', {'appt_id': 3}, 'Appointment 3'),
                                    ('online_order.view', {'order_id': 12}, 'Online Order 12')):
            _, body = self.get(url(endpoint, **kw))
            self.assertRegex(body, r'page-header-title">\s*' + re.escape(title) + r'\b', endpoint)

    def test_type_badges_where_the_type_matters(self):
        _, body = self.get(url('payment.index'))
        self.assertRegex(body, r'payment-ref-sale">\s*Sale\s*</span>')
        self.assertRegex(body, r'payment-ref-appointment">\s*Appointment\s*</span>')
        self.assertIn('>Online order</a>', body)
        _, body = self.get(url('dashboard.index'))
        self.assertRegex(body, r'po-stage-draft me-1">(Sale|Appointment|Online order)</span>\d+')

    def test_dropdown_labels(self):
        _, body = self.get(url('sale.create'))
        self.assertIn('7 - Honda', body)

    def test_json_endpoints(self):
        for endpoint, kw in (('payment.sale_info', {'sale_id': 1}), ('payment.appointment_info', {'appt_id': 1})):
            r = self.client.get(url(endpoint, **kw))
            self.assertEqual(r.status_code, 200, endpoint)
            self.assertEqual(OLD_ID.findall(r.get_data(as_text=True)), [], endpoint)

    def test_modal_record_names(self):
        _, body = self.get(url('payment.index'))
        self.assertIn('data-record-name="Payment 12 (Sale 2 - Bob Stone)"', body)
        _, body = self.get(url('purchase_order.index'))
        self.assertIn('data-record-name="Purchase order 12 (Parts Ltd)"', body)


class Flashes(Base):
    tables = staticmethod(fixtures_ids.tables)

    def test_payment_deleted(self):
        _, _, flashes = self.post(url('payment.delete', payment_id=12))
        self.assertIn('Payment 12 was deleted successfully.', flashes)

    def test_sale_with_payment_cannot_be_deleted(self):
        self.db.raise_on[('Sale', 'delete')] = Exception('violates foreign key constraint "Payment_Sale_FK"')
        _, _, flashes = self.post(url('sale.delete', sale_id=2))
        self.assertTrue(any(f.startswith('Cannot delete sale 2 because') for f in flashes), flashes)

    def test_purchase_order_with_items_cannot_be_deleted(self):
        _, _, flashes = self.post(url('purchase_order.delete', po_id=1))
        self.assertTrue(any('purchase order 1' in f.lower() for f in flashes), flashes)
        self.assertFalse(any(OLD_ID.search(f) for f in flashes), flashes)


class Searches(Base):
    """The queries recorded before Phase 7 return the same rows; new id forms also work."""

    def setUp(self):
        self.client = record_searches.make_client()

    def test_recorded_queries_unchanged(self):
        self.assertEqual(record_searches.record(fixtures_ids.SEARCH_BEFORE), fixtures_ids.RECORDED)

    def test_new_forms(self):
        new = {
            'payment':     {'Sale 15': [4], 'PAY-12': [12], 'Payment 12': [12], 'appt #1': [2], 'order 1': [3]},
            'sale':        {'SALE-15': [15], 'sale 2': [2], '#15': [15], 'PO-15': []},
            'order':       {'Order 12': [12], '#12': [12]},
            'appointment': {'APPT-#3': [3], '#3': [3], 'Appointment 3': [3], '3': [3]},
            'po':          {'PO-12': [12], '#12': [12], '12': [12]},
            'motorbike':   {'NB-7': [7], '#7': [7], '7': [7]},
            'application': {'APP-5': [5], '#5': [5], 'Application 5': [5]},
        }
        self.assertEqual(record_searches.record(new), new)


if __name__ == '__main__':
    unittest.main(verbosity=1)
