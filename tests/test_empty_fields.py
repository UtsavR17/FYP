"""
Empty optional fields must render as empty inputs, never as the text "None".

The form macros printed {{ value }} straight into the input, and Jinja prints a database NULL
(Python None) as "None". Saving the edit form then stored the string "None" (for example as a
customer's post code).

Run from the repo root:  venv/Scripts/python -W ignore tests/test_empty_fields.py
"""
import re
import unittest

from harness import APP, Base, url
import test_smoke

NONE_IN_FIELD = re.compile(r'value="None"|>None</textarea>')
INPUT = re.compile(r'<input\b[^>]*>', re.S)
ATTR = re.compile(r'(\w+)="([^"]*)"')


def inputs(body, form_id):
    """name -> value of the text inputs and textareas inside the form with this id."""
    start = body.index(f'id="{form_id}"')
    form = body[start:body.index('</form>', start)]
    values = {}
    for tag in INPUT.findall(form):
        attrs = dict(ATTR.findall(tag))
        if attrs.get('type') in ('text', 'number', 'date', 'time', 'email') and 'name' in attrs:
            values[attrs['name']] = attrs.get('value', '')
    for name, text in re.findall(r'<textarea[^>]*name="(\w+)"[^>]*>(.*?)</textarea>', form, re.S):
        values[name] = text.strip()
    return values


def customer_tables():
    return {'Customer': [{'CustomerID': 1, 'FirstName': 'Ana', 'LastName': 'Test', 'PhoneNumber': '5001',
                          'HomeNumber': None, 'Email': 'ana@example.mu', 'Street': 'Royal Road',
                          'Town': 'Curepipe', 'PostCode': None, 'NIC': 'N1', 'AuthUserID': None}]}


class MacrosRenderNoneAsEmpty(unittest.TestCase):
    def render(self, call):
        with APP.test_request_context():
            src = "{% from 'components/form_field.html' import text_field, number_field, textarea_field, " \
                  "date_field, time_field %}" + call
            return APP.jinja_env.from_string(src).render()

    def test_each_value_macro(self):
        for macro in ('text_field', 'number_field', 'date_field', 'time_field'):
            with self.subTest(macro=macro):
                html = self.render(f"{{{{ {macro}('X', 'X', None) }}}}")
                self.assertIn('value=""', html)
                self.assertNotIn('None', html)
        html = self.render("{{ textarea_field('X', 'X', None) }}")
        self.assertNotIn('None', html)

    def test_real_values_unchanged(self):
        self.assertIn('value="0"', self.render("{{ number_field('X', 'X', 0) }}"))
        self.assertIn('value="74201"', self.render("{{ text_field('X', 'X', '74201') }}"))
        self.assertIn('>Front pad</textarea>', self.render("{{ textarea_field('X', 'X', 'Front pad') }}"))
        self.assertIn('value="None"', self.render("{{ text_field('X', 'X', 'None') }}"))   # typed text stays


class CustomerRoundTrip(Base):
    tables = staticmethod(customer_tables)

    def test_edit_page_shows_empty_optional_fields(self):
        _, body = self.get(url('customer.edit', customer_id=1))
        values = inputs(body, 'customerForm')
        self.assertEqual(values['PostCode'], '')
        self.assertEqual(values['HomeNumber'], '')
        self.assertEqual(values['FirstName'], 'Ana')

    def test_saving_unchanged_form_keeps_nulls(self):
        _, body = self.get(url('customer.edit', customer_id=1))
        _, _, flashes = self.post(url('customer.edit', customer_id=1), inputs(body, 'customerForm'))
        self.assertEqual(flashes, ['Customer "Ana Test" was updated successfully.'])
        row = self.rows('Customer', CustomerID=1)[0]
        self.assertIsNone(row['PostCode'])
        self.assertIsNone(row['HomeNumber'])


class NoPageShowsNone(Base):
    """Every Admin GET page, with the smoke data (which has NULL optional fields), shows no "None" input."""
    tables = staticmethod(test_smoke.tables)

    def test_sweep(self):
        offenders = []
        for rule in APP.url_map.iter_rules():
            if 'GET' not in rule.methods or rule.endpoint in test_smoke.SKIP \
                    or rule.endpoint.startswith('supplier_portal.'):
                continue
            path = rule.rule
            for arg in rule.arguments:
                value = test_smoke.ARG_VALUES.get(arg, '1')
                path = path.replace(f'<int:{arg}>', '1').replace(f'<string:{arg}>', value)
                path = path.replace(f'<{arg}>', value)
            self.db.tables = test_smoke.tables()
            r = self.client.get(path)
            if r.status_code == 200 and NONE_IN_FIELD.search(r.get_data(as_text=True)):
                offenders.append(path)
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
