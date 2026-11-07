"""
Fix Phase 2 tests: receiving gate for portal suppliers (ISS-06), DEC-1 A stock isolation,
compatibility duplicate feedback (ISS-19). Fake Supabase + Flask test client.

Run from the repo root:  venv/Scripts/python -W ignore tests/test_fix2.py
"""
import re
import unittest

from harness import APP, Base, url

STAGES = ('Draft', 'Sent', 'Accepted', 'Rejected')
NOT_ACCEPTED = 'This order has not been accepted by the supplier.'
NOT_SHIPPED = 'The supplier has not shipped this item yet.'
NONE_CREATED = 'No compatibility records were created because every selected combination already exists.'
DUP = 'A compatibility record for this stock item, model and year range already exists.'


def tables():
    return {
        'Supplier': [
            {'SupplierID': 1, 'SupplierName': 'Portal Parts Ltd', 'AuthUserID': 'portal-uid'},
            {'SupplierID': 2, 'SupplierName': 'Offline Traders', 'AuthUserID': None},
            {'SupplierID': 3, 'SupplierName': 'Second Portal Co', 'AuthUserID': 'portal-uid-2'},
        ],
        'Brand': [{'Brand_ID': 1, 'Brand_Name': 'Honda'}, {'Brand_ID': 2, 'Brand_Name': 'Yamaha'}],
        'Spare_Parts': [{'SP_id': 7, 'SP_name': 'Brake Pad'}],
        'Model': [{'Model_No': 1, 'Brand_Brand_ID': 1, 'Description': 'CB Shine'},
                  {'Model_No': 2, 'Brand_Brand_ID': 1, 'Description': 'Wave 110'},
                  {'Model_No': 3, 'Brand_Brand_ID': 2, 'Description': 'R15'}],
        'Supplier_Product': [
            {'SupplierProduct_ID': 100, 'Supplier_SupplierID': 1, 'SP_id': 7, 'Brand_Brand_ID': 1, 'BuyingPrice': 200},
            {'SupplierProduct_ID': 200, 'Supplier_SupplierID': 2, 'SP_id': 7, 'Brand_Brand_ID': 1, 'BuyingPrice': 210},
            {'SupplierProduct_ID': 300, 'Supplier_SupplierID': 3, 'SP_id': 7, 'Brand_Brand_ID': 2, 'BuyingPrice': 190},
        ],
        'PurchaseOrder': [],
        'PurchaseOrderItem': [],
        'PO_NewMotorBike': [],
        'Supplier_Model': [],
        'Color': [{'Color': 'Red'}],
        'Stock': [],
        'Compatibility': [],
        'New_MotorBike': [],
    }


class Fix2Base(Base):
    tables = staticmethod(tables)

    def make_po(self, po_id, supplier, stage='Accepted', status='Pending', item_shipped=False, bike_status='Ordered',
                size='M', product=None):
        self.db.tables['PurchaseOrder'].append({
            'PurchaseOrderID': po_id, 'Supplier_SupplierID': supplier, 'POrderDate': '2026-10-01',
            'ExpectedDate': '2026-10-20', 'Status': status, 'SupplierStage': stage})
        self.db.tables['PurchaseOrderItem'].append({
            'POItem_ID': po_id * 10, 'PurchaseOrder_ID': po_id, 'SP_id': 7,
            'SupplierProduct_ID': product or {1: 100, 2: 200, 3: 300}[supplier], 'Quantity_Ordered': 5,
            'BuyingPrice': 200, 'Size_Expected': size, 'Status': 'Ordered', 'Quantity_Received': None,
            'DateReceived': None, 'Stock_Stock_ID': None, 'DateShipped': '2026-10-05' if item_shipped else None})
        self.db.tables['PO_NewMotorBike'].append({
            'POBike_ID': po_id * 10 + 1, 'PurchaseOrder_ID': po_id, 'Model_Model_No': 1, 'Color_Color': 'Red',
            'BuyingPrice': 70000, 'Status': bike_status, 'SupplierModel_ID': None,
            'ShippedVIN': 'VIN-S' if bike_status == 'Shipped' else None,
            'ShippedYear': 2025 if bike_status == 'Shipped' else None,
            'DateShipped': '2026-10-05' if bike_status == 'Shipped' else None, 'New_MotorBike_NB_ID': None})

    def flash_of(self, response):
        with self.client.session_transaction() as s:
            msgs = [m for _, m in s.get('_flashes', [])]
            s.pop('_flashes', None)
        return msgs

    def item_receive_post(self, po_id, **form):
        data = {'receiving_mode': 'new', 'New_Size': 'M', 'S_Price': '250', 'Warranty': '6',
                'Quantity_Received': '2', 'DateReceived': '2026-10-08'}
        data.update(form)
        return self.post(url('purchase_order.receive_item', po_id=po_id, item_id=po_id * 10), data)


# --------------------------------------------------------------------------- 2.1 receiving gate
class G1PortalGate(Fix2Base):
    def check(self, kind, stage, shipped):
        po_id = len(self.db.tables['PurchaseOrder']) + 1
        self.make_po(po_id, 1, stage=stage, item_shipped=shipped, bike_status='Shipped' if shipped else 'Ordered')
        if kind == 'item':
            path = url('purchase_order.receive_item', po_id=po_id, item_id=po_id * 10)
        else:
            path = url('purchase_order.receive_motorbike', po_id=po_id, pobike_id=po_id * 10 + 1)
        r = self.client.get(path)
        get_flash = self.flash_of(r)
        r2, _, post_flash = self.post(path, {'receiving_mode': 'new', 'Quantity_Received': '1'})
        return r, get_flash, r2, post_flash

    def test_matrix_items_and_bikes(self):
        for kind in ('item', 'bike'):
            for stage in STAGES:
                for shipped in (False, True):
                    r, flashes, r2, post_flashes = self.check(kind, stage, shipped)
                    label = f'{kind} {stage} shipped={shipped}'
                    if stage == 'Accepted' and shipped:
                        self.assertEqual(r.status_code, 200, label)
                        continue
                    self.assertEqual(r.status_code, 302, label)
                    self.assertEqual(r2.status_code, 302, label)     # direct POST refused too
                    if stage == 'Sent':
                        expected = 'Wait for the supplier to accept this order before receiving.'
                    elif stage != 'Accepted':
                        expected = NOT_ACCEPTED
                    else:
                        expected = NOT_SHIPPED
                    self.assertEqual(flashes, [expected], label)
                    self.assertEqual(post_flashes, [expected], label)
        self.assertEqual(self.db.inserts, [])
        self.assertEqual([u for u in self.db.updates if u[0] in ('Stock', 'PurchaseOrderItem')], [])

    def test_closed_portal_order_refused(self):
        self.make_po(1, 1, stage='Accepted', status='Cancelled', item_shipped=True)
        self.client.get(url('purchase_order.receive_item', po_id=1, item_id=10))
        self.assertIn('cancelled', self.flash_of(None)[0])

    def test_shipped_item_receives_on_accepted_order(self):
        self.make_po(1, 1, stage='Accepted', item_shipped=True)
        r, page, flashes = self.item_receive_post(1)
        self.assertEqual(r.status_code, 302, re.findall(r'invalid-feedback">([^<]+)', page))
        self.assertEqual(self.rows('PurchaseOrderItem', POItem_ID=10)[0]['Status'], 'Received')

    def test_revert_shipment_then_receive_refused(self):
        self.make_po(1, 1, stage='Accepted', bike_status='Shipped')
        self.assertEqual(self.client.get(url('purchase_order.receive_motorbike', po_id=1, pobike_id=11)).status_code, 200)
        r, _, flashes = self.post(url('purchase_order.unship_motorbike', po_id=1, pobike_id=11))
        self.assertEqual(self.rows('PO_NewMotorBike', POBike_ID=11)[0]['Status'], 'Ordered')
        self.client.get(url('purchase_order.receive_motorbike', po_id=1, pobike_id=11))
        self.assertEqual(self.flash_of(None), [NOT_SHIPPED])


class G2OfflineUnchanged(Fix2Base):
    def test_offline_every_state(self):
        for i, stage in enumerate(STAGES, start=1):
            for shipped in (False, True):
                po_id = i * 2 + int(shipped)
                self.make_po(po_id, 2, stage=stage, item_shipped=shipped)
                r = self.client.get(url('purchase_order.receive_item', po_id=po_id, item_id=po_id * 10))
                self.flash_of(r)
                expected = 302 if stage == 'Sent' else 200
                self.assertEqual(r.status_code, expected, f'{stage} {shipped}')
                r = self.client.get(url('purchase_order.receive_motorbike', po_id=po_id, pobike_id=po_id * 10 + 1))
                self.flash_of(r)
                self.assertEqual(r.status_code, expected, f'bike {stage} {shipped}')

    def test_offline_view_has_no_shipment_markers(self):
        self.make_po(1, 2, stage='Draft')
        _, page = self.get(url('purchase_order.view', po_id=1))
        self.assertNotIn('Awaiting shipment', page)
        self.assertIn(url('purchase_order.receive_item', po_id=1, item_id=10), page)


class G3ViewMarkers(Fix2Base):
    def test_portal_awaiting_and_disabled_reason(self):
        self.make_po(1, 1, stage='Accepted')
        _, page = self.get(url('purchase_order.view', po_id=1))
        self.assertEqual(page.count('Awaiting shipment'), 2)          # item + bike
        self.assertNotIn(url('purchase_order.receive_item', po_id=1, item_id=10), page)
        self.assertIn(f'title="{NOT_SHIPPED}"', page)

    def test_portal_shipped_on_and_receive_link(self):
        self.make_po(1, 1, stage='Accepted', item_shipped=True, bike_status='Shipped')
        _, page = self.get(url('purchase_order.view', po_id=1))
        self.assertIn('Shipped on 05 Oct', page)
        self.assertIn(url('purchase_order.receive_item', po_id=1, item_id=10), page)
        self.assertIn(url('purchase_order.receive_motorbike', po_id=1, pobike_id=11), page)
        self.assertNotIn('Awaiting shipment', page)

    def test_portal_draft_shows_not_accepted(self):
        self.make_po(1, 1, stage='Draft')
        _, page = self.get(url('purchase_order.view', po_id=1))
        self.assertIn(f'title="{NOT_ACCEPTED}"', page)


class G4HeaderStatus(Fix2Base):
    def edit(self, po_id, status):
        return self.post(url('purchase_order.edit', po_id=po_id), {
            'Supplier_SupplierID': str(self.rows('PurchaseOrder', PurchaseOrderID=po_id)[0]['Supplier_SupplierID']),
            'POrderDate': '2026-10-01', 'ExpectedDate': '2026-10-20', 'Status': status})

    def test_portal_cannot_set_computed_statuses(self):
        self.make_po(1, 1, stage='Accepted')
        _, page = self.get(url('purchase_order.edit', po_id=1))
        sel = page.split('id="Status"')[1].split('</select>')[0]
        self.assertNotIn('value="Received"', sel)
        self.assertNotIn('value="Partially Received"', sel)
        for status in ('Received', 'Partially Received'):
            r, page, _ = self.edit(1, status)
            self.assertEqual(r.status_code, 200)
            self.assertIn(f'{status} is set automatically when the lines are received', page)
        self.assertEqual(self.rows('PurchaseOrder', PurchaseOrderID=1)[0]['Status'], 'Pending')
        r, _, _ = self.edit(1, 'Cancelled')
        self.assertEqual(r.status_code, 302)

    def test_portal_computed_status_can_be_kept(self):
        self.make_po(1, 1, stage='Accepted', status='Partially Received')
        _, page = self.get(url('purchase_order.edit', po_id=1))
        sel = page.split('id="Status"')[1].split('</select>')[0]
        self.assertRegex(sel, r'value="Partially Received"\s+selected')
        self.assertNotIn('value="Received"', sel)
        r, _, _ = self.edit(1, 'Partially Received')
        self.assertEqual(r.status_code, 302)

    def test_offline_unchanged(self):
        self.make_po(1, 2, stage='Draft')
        for status in ('Partially Received', 'Received', 'Pending'):
            r, _, _ = self.edit(1, status)
            self.assertEqual(r.status_code, 302, status)


# --------------------------------------------------------------------------- 2.2 DEC-1 A stock isolation
class I1StockIsolation(Fix2Base):
    def stock(self):
        return sorted((s['Brand_Brand_ID'], s['Size'], s['QOH']) for s in self.db.tables['Stock'])

    def test_different_brands_from_two_suppliers_stay_separate(self):
        self.make_po(1, 1, stage='Accepted', item_shipped=True)          # Honda
        self.make_po(2, 3, stage='Accepted', item_shipped=True)          # Yamaha
        self.item_receive_post(1, Quantity_Received='2')
        _, page = self.get(url('purchase_order.receive_item', po_id=2, item_id=20))
        self.assertIn('name="receiving_mode" value="new"', page)        # Honda row not offered
        self.item_receive_post(2, Quantity_Received='3')
        self.assertEqual(self.stock(), [(1, 'M', 2), (2, 'M', 3)])

    def test_same_brand_from_two_suppliers_shares_the_exact_variant(self):
        self.make_po(1, 1, stage='Accepted', item_shipped=True)          # Honda from portal supplier
        self.make_po(2, 2, stage='Draft')                                # Honda from offline supplier
        self.item_receive_post(1, Quantity_Received='2')
        row = self.db.tables['Stock'][0]
        _, page = self.get(url('purchase_order.receive_item', po_id=2, item_id=20))
        self.assertIn(f'name="Stock_Stock_ID" value="{row["Stock_ID"]}"', page)
        self.item_receive_post(2, receiving_mode='existing', Stock_Stock_ID=str(row['Stock_ID']), Quantity_Received='4')
        self.assertEqual(self.stock(), [(1, 'M', 6)])
        self.assertEqual(self.rows('PurchaseOrderItem', POItem_ID=20)[0]['Stock_Stock_ID'], row['Stock_ID'])

    def test_same_part_different_size_separate(self):
        self.make_po(1, 1, stage='Accepted', item_shipped=True, size='M')
        self.make_po(2, 1, stage='Accepted', item_shipped=True, size='L')
        self.item_receive_post(1, New_Size='M')
        r, page, _ = self.item_receive_post(2, receiving_mode='existing',
                                            Stock_Stock_ID=str(self.db.tables['Stock'][0]['Stock_ID']))
        self.assertEqual(r.status_code, 200)                              # other size never selectable
        self.item_receive_post(2, New_Size='L')
        self.assertEqual(self.stock(), [(1, 'L', 2), (1, 'M', 2)])

    def test_receive_page_shows_brand_and_supplier(self):
        self.make_po(1, 1, stage='Accepted', item_shipped=True)
        _, page = self.get(url('purchase_order.receive_item', po_id=1, item_id=10))
        self.assertIn('Portal Parts Ltd', page)
        self.assertIn('Honda', page)


# --------------------------------------------------------------------------- 2.3 compatibility
class C1Compat(Fix2Base):
    def setUp(self):
        super().setUp()
        self.db.tables['Stock'] = [{'Stock_ID': 5, 'Spare_Parts_SP_id': 7, 'Brand_Brand_ID': 1, 'Size': None, 'QOH': 1}]
        self.db.tables['Compatibility'] = [
            {'Com_ID': 1, 'Stock_Stock_ID': 5, 'Model_Model_No': 1, 'Year_From': 2015, 'Year_To': 2020},
            {'Com_ID': 2, 'Stock_Stock_ID': 5, 'Model_Model_No': 2, 'Year_From': None, 'Year_To': None},
        ]

    def create(self, models, year_from='', year_to=''):
        return self.client.post(url('compatibility.create'), data={
            'Stock_Stock_ID': '5', 'Model_Model_No': [str(m) for m in models],
            'Year_From': year_from, 'Year_To': year_to})

    def flashes(self):
        with self.client.session_transaction() as s:
            out = [(c, m) for c, m in s.get('_flashes', [])]
            s.pop('_flashes', None)
        return out

    def compat_inserts(self):
        return [rows for t, rows in self.db.inserts if t == 'Compatibility']

    def test_new_combinations_created(self):
        r = self.create([3], '2018', '2022')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.flashes(), [('success', '1 compatibility record added successfully.')])

    def test_partial_duplicates(self):
        r = self.create([1, 3], '2015', '2020')
        self.assertEqual(r.status_code, 302)
        f = self.flashes()
        self.assertEqual(f[0], ('success', '1 compatibility record added successfully.'))
        self.assertEqual(f[1][0], 'warning')
        self.assertIn('Already exists: ', f[1][1])
        self.assertIn('CB Shine', f[1][1])
        self.assertIn('(2015 to 2020)', f[1][1])
        self.assertEqual(len(self.compat_inserts()), 1)                # the duplicate never reached the DB

    def test_all_duplicates_is_an_error_and_keeps_values(self):
        r = self.client.post(url('compatibility.create'), data={
            'Stock_Stock_ID': '5', 'Model_Model_No': ['1'], 'Year_From': '2015', 'Year_To': '2020'})
        self.assertEqual(r.status_code, 200)
        page = r.get_data(as_text=True)
        self.assertIn(NONE_CREATED, page)
        self.assertRegex(page, r'<option value="1"\s+selected>')
        self.assertIn('value="2015"', page)
        self.assertEqual(self.compat_inserts(), [])
        self.assertIn('Already exists:', page)                         # warning listed on the same page
        self.assertNotIn('alert-success', page)

    def test_blank_years_equal_blank_years(self):
        r = self.create([2])
        self.assertEqual(r.status_code, 200)
        self.assertIn(NONE_CREATED, r.get_data(as_text=True))
        self.assertEqual(self.compat_inserts(), [])
        r = self.create([2], '2019', '')                                 # a range is a different combination
        self.assertEqual(r.status_code, 302)

    def test_edit_into_duplicate(self):
        r = self.client.post(url('compatibility.edit', com_id=1), data={
            'Stock_Stock_ID': '5', 'Model_Model_No': '2', 'Year_From': '', 'Year_To': ''})
        self.assertEqual(r.status_code, 200)
        self.assertIn(DUP, r.get_data(as_text=True))
        self.assertEqual([u for u in self.db.updates if u[0] == 'Compatibility'], [])
        r = self.client.post(url('compatibility.edit', com_id=1), data={     # unchanged: excluded itself
            'Stock_Stock_ID': '5', 'Model_Model_No': '1', 'Year_From': '2015', 'Year_To': '2020'})
        self.assertEqual(r.status_code, 302)

    def test_database_violation_fallback(self):
        class Unique(Exception):
            pass
        self.db.raise_on[('Compatibility', 'insert')] = Unique("{'code': '23505', 'message': 'duplicate key'}")
        r = self.create([3])
        self.assertEqual(r.status_code, 200)
        self.assertIn(NONE_CREATED, r.get_data(as_text=True))
        self.db.raise_on[('Compatibility', 'update')] = Unique("{'code': '23505'}")
        r = self.client.post(url('compatibility.edit', com_id=1), data={
            'Stock_Stock_ID': '5', 'Model_Model_No': '3', 'Year_From': '', 'Year_To': ''})
        self.assertIn(DUP, r.get_data(as_text=True))

    def test_flash_visibility_rules(self):
        with open('app/static/js/admin.js', encoding='utf-8') as fh:
            js = fh.read()
        self.assertIn(".flash-container .alert-success, .flash-container .alert-info", js)
        self.assertNotIn("document.querySelectorAll('.flash-container .alert');", js)
        _, page = self.get(url('compatibility.create'))
        self.assertIn('Selecting several models creates one record per model; existing combinations are skipped.', page)


class X1Security(Fix2Base):
    def test_login_required(self):
        anon = APP.test_client()
        for method, path in (('get', url('purchase_order.receive_item', po_id=1, item_id=10)),
                             ('post', url('purchase_order.receive_motorbike', po_id=1, pobike_id=11)),
                             ('post', url('compatibility.create')), ('post', url('purchase_order.edit', po_id=1))):
            r = getattr(anon, method)(path)
            self.assertEqual(r.status_code, 302)
            self.assertIn('/auth/login', r.headers['Location'])


if __name__ == '__main__':
    unittest.main(verbosity=1)
