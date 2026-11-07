"""
App-wide smoke test: every Admin GET route renders (no 500) against a small but complete fake
dataset, with route ids set to existing records. Regression net for modules a task does not touch.

Run from the repo root:  venv/Scripts/python -W ignore tests/test_smoke.py
"""
import unittest

from harness import APP, Base

AUDIT = {'Created_By': 'x@y', 'Date_Created': '2026-10-01T00:00:00+00:00'}


def tables():
    t = {
        'Color': [{'Color': 'Red'}],
        'Category': [{'CAT_ID': 1, 'CAT_desc': 'Brakes'}],
        'Brand': [{'Brand_ID': 1, 'Brand_Name': 'Honda', 'CountryOfOrigin': 'Japan'}],
        'Model': [{'Model_No': 1, 'Brand_Brand_ID': 1, 'Description': 'CB Shine', 'ImageUrl': None}],
        'Spare_Parts': [{'SP_id': 1, 'SP_name': 'Brake Pad', 'SP_desc': 'Front', 'Category_CAT_ID': 1,
                         'Model_Model_No': None, 'ImageUrl': None}],
        'Stock': [{'Stock_ID': 1, 'Spare_Parts_SP_id': 1, 'Brand_Brand_ID': 1, 'Size': None, 'QOH': 5,
                   'S_Price': 200, 'Warranty': 6}],
        'Compatibility': [{'Com_ID': 1, 'Stock_Stock_ID': 1, 'Model_Model_No': 1, 'Year_From': 2015, 'Year_To': 2020}],
        'Service': [{'ServiceID': 1, 'Service_Name': 'Oil change', 'Description': 'Oil', 'Cost': 350}],
        'Role': [{'Role_ID': 1, 'Role_Name': 'Salesperson', 'HourlyRate': 200}],
        'Employee': [{'EmployeeID': 1, 'FirstName': 'Sam', 'LastName': 'Seller', 'Phone': '5000', 'Role_Role_ID': 1,
                      'SupervisorID': None}],
        'Supplier': [{'SupplierID': 1, 'SupplierName': 'Parts Ltd', 'Phone': '2000', 'Email': 's@p.mu',
                      'Address': 'PL', 'Country': 'Mauritius', 'BRN': None, 'AuthUserID': None}],
        'Supplier_Product': [{'SupplierProduct_ID': 1, 'Supplier_SupplierID': 1, 'SP_id': 1, 'Brand_Brand_ID': 1,
                              'BuyingPrice': 150}],
        'Supplier_Model': [],
        'Customer': [{'CustomerID': 1, 'FirstName': 'Alice', 'LastName': 'Martin', 'PhoneNumber': '5123',
                      'Email': 'a@b.mu', 'Town': 'Curepipe', 'NIC': 'A1', 'Street': 'Royal', 'AuthUserID': None}],
        'Customer_bike': [{'BikeID': 1, 'RegistrationNumber': 'AB1', 'VIN': 'V1', 'Year': 2019, 'Model_Model_No': 1,
                           'Customer_CustomerID': 1}],
        'New_MotorBike': [{'NB_ID': 1, 'Model_Model_No': 1, 'Color_Color': 'Red', 'Year': 2025, 'VIN': 'NB1',
                           'Price': 90000, 'Status': 'Sold', 'Warranty_Months': 12, 'EngineCC': 125,
                           'FuelType': 'Petrol', 'Transmission': 'Manual', 'FuelTankCapacity': 9}],
        'Sale': [{'SaleID': 1, 'Customer_CustomerID': 1, 'New_MotorBike_NB_ID': 1, 'Employee_EmployeeID': 1,
                  'SaleDate': '2026-10-01', 'TotalAmount': 90000}],
        'Appointment': [{'AppointmentID': 1, 'Customer_bike_BikeID': 1, 'Employee_EmployeeID': 1,
                         'Appointment_Date': '2026-10-05', 'Appointment_time': '09:00:00',
                         'AppointmentType': 'Service', 'Status': 'Confirmed'}],
        'appointment_service': [{'Appointment_AppointmentID': 1, 'Service_ServiceID': 1, 'Quantity': 1}],
        'Appointment_Stock': [{'Appointment_AppointmentID': 1, 'Stock_Stock_ID': 1, 'Quantity': 1}],
        'Payment': [{'PaymentID': 1, 'Sale_SaleID': 1, 'Appointment_AppointmentID': None, 'Online_Order_OrderID': None,
                     'StripePaymentIntentID': None, 'PaymentDate': '2026-10-01', 'AmountPaid': 1000,
                     'PaymentMethod': 'Cash', 'PaymentType': 'Deposit'}],
        'Online_Order': [{'OrderID': 1, 'OrderDate': '2026-10-01', 'Customer_CustomerID': 1, 'Status': 'Paid',
                          'FulfilmentMethod': 'Pickup', 'OrderType': 'Parts', 'TotalAmount': 400,
                          'StripeSessionID': 'cs_1', 'PaidAt': '2026-10-01T10:00:00+00:00', 'Sale_SaleID': None}],
        'Online_Order_Item': [{'OrderItemID': 1, 'Online_Order_OrderID': 1, 'Stock_Stock_ID': 1,
                               'ItemDescription': 'Brake Pad', 'Quantity': 2, 'UnitPrice': 200}],
        'PurchaseOrder': [{'PurchaseOrderID': 1, 'Supplier_SupplierID': 1, 'POrderDate': '2026-10-01',
                           'ExpectedDate': '2026-10-10', 'Status': 'Pending', 'SupplierStage': 'Draft'}],
        'PurchaseOrderItem': [{'POItem_ID': 1, 'PurchaseOrder_ID': 1, 'SP_id': 1, 'SupplierProduct_ID': 1,
                               'Quantity_Ordered': 3, 'BuyingPrice': 150, 'Size_Expected': None, 'Status': 'Ordered'}],
        'PO_NewMotorBike': [{'POBike_ID': 1, 'PurchaseOrder_ID': 1, 'Model_Model_No': 1, 'Color_Color': 'Red',
                             'Year': 2025, 'Quantity': 1, 'BuyingPrice': 70000, 'Status': 'Ordered'}],
        'Supplier_Application': [{'ApplicationID': 1, 'CompanyName': 'New Co', 'ContactPerson': 'Z', 'Email': 'z@n.mu',
                                  'Phone': '1', 'Country': 'Mauritius', 'BRN': 'C1', 'Status': 'Pending',
                                  'SubmittedAt': '2026-10-01T08:00:00+00:00', 'AuthUserID': 'u1'}],
    }
    for rows in t.values():
        for r in rows:
            r.update(AUDIT)
    return t


ARG_VALUES = {'color_id': 'Red'}
SKIP = {'auth.logout', 'static'}


class SmokeAllPages(Base):
    tables = staticmethod(tables)

    def test_every_admin_get_route_renders(self):
        failures = []
        for rule in APP.url_map.iter_rules():
            if 'GET' not in rule.methods or rule.endpoint in SKIP or rule.endpoint.startswith('supplier_portal.'):
                continue
            path = rule.rule
            for arg in rule.arguments:
                path = path.replace(f'<int:{arg}>', '1').replace(f'<string:{arg}>', ARG_VALUES.get(arg, '1'))
                path = path.replace(f'<{arg}>', ARG_VALUES.get(arg, '1'))
            self.db.tables = tables()
            try:
                r = self.client.get(path)
            except Exception as e:      # TESTING propagates exceptions instead of a 500
                failures.append((path, f'{type(e).__name__}: {e}'))
                continue
            if r.status_code >= 500:
                failures.append((path, r.status_code))
        self.assertEqual(failures, [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
