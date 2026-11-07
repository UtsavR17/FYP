"""
Dataset and recorded searches for the Fix Phase 7 id tests (test_fix7_ids.py).

RECORDED holds the rows each list search returned BEFORE Fix Phase 7 (recorded on main
a1e7c05 with tests/record_searches.py). The new code must return exactly the same rows for
these queries, and may only add matches for new id forms (SEARCH_NEW).
No app imports here, so the recorder can also run against an older checkout.
"""
import test_smoke


def tables():
    t = test_smoke.tables()
    audit = {'Created_By': 'x@y', 'Date_Created': '2026-10-01T00:00:00+00:00'}
    extra = {
        'Customer': [{'CustomerID': 2, 'FirstName': 'Bob', 'LastName': 'Stone', 'PhoneNumber': '5777',
                      'Email': 'bob@b.mu', 'Town': 'Rose Hill', 'NIC': 'B2', 'Street': 'Main', 'AuthUserID': None}],
        'Sale': [{'SaleID': sid, 'Customer_CustomerID': 2, 'New_MotorBike_NB_ID': 1, 'Employee_EmployeeID': 1,
                  'SaleDate': '2026-10-02', 'TotalAmount': 50000} for sid in (2, 15)],
        'Payment': [
            {'PaymentID': 2, 'Sale_SaleID': None, 'Appointment_AppointmentID': 1, 'Online_Order_OrderID': None,
             'StripePaymentIntentID': None, 'PaymentDate': '2026-10-03', 'AmountPaid': 350,
             'PaymentMethod': 'Cash', 'PaymentType': 'Full'},
            {'PaymentID': 3, 'Sale_SaleID': None, 'Appointment_AppointmentID': None, 'Online_Order_OrderID': 1,
             'StripePaymentIntentID': 'pi_1', 'PaymentDate': '2026-10-01', 'AmountPaid': 400,
             'PaymentMethod': 'Online', 'PaymentType': 'Full'},
            {'PaymentID': 4, 'Sale_SaleID': 15, 'Appointment_AppointmentID': None, 'Online_Order_OrderID': None,
             'StripePaymentIntentID': None, 'PaymentDate': '2026-10-04', 'AmountPaid': 5000,
             'PaymentMethod': 'Card', 'PaymentType': 'Deposit'},
            {'PaymentID': 12, 'Sale_SaleID': 2, 'Appointment_AppointmentID': None, 'Online_Order_OrderID': None,
             'StripePaymentIntentID': None, 'PaymentDate': '2026-10-05', 'AmountPaid': 1000,
             'PaymentMethod': 'Cash', 'PaymentType': 'Deposit'},
        ],
        'Online_Order': [{'OrderID': 12, 'OrderDate': '2026-10-02', 'Customer_CustomerID': 2, 'Status': 'Paid',
                          'FulfilmentMethod': 'Pickup', 'OrderType': 'Parts', 'TotalAmount': 200,
                          'StripeSessionID': 'cs_12', 'PaidAt': '2026-10-02T10:00:00+00:00', 'Sale_SaleID': None}],
        'Appointment': [{'AppointmentID': 3, 'Customer_bike_BikeID': 1, 'Employee_EmployeeID': 1,
                         'Appointment_Date': '2026-10-08', 'Appointment_time': '10:00:00',
                         'AppointmentType': 'Repair', 'Status': 'Pending'}],
        'PurchaseOrder': [{'PurchaseOrderID': 12, 'Supplier_SupplierID': 1, 'POrderDate': '2026-10-02',
                           'ExpectedDate': '2026-10-20', 'Status': 'Pending', 'SupplierStage': 'Draft'}],
        'New_MotorBike': [{'NB_ID': 7, 'Model_Model_No': 1, 'Color_Color': 'Red', 'Year': 2026, 'VIN': 'NB7',
                           'Price': 95000, 'Status': 'Available', 'Warranty_Months': 12, 'EngineCC': 125,
                           'FuelType': 'Petrol', 'Transmission': 'Manual', 'FuelTankCapacity': 9}],
        'Supplier_Application': [{'ApplicationID': 5, 'CompanyName': 'Five Ltd', 'ContactPerson': 'F',
                                  'Email': 'f@f.mu', 'Phone': '5', 'Country': 'Mauritius', 'BRN': 'C5',
                                  'Status': 'Pending', 'SubmittedAt': '2026-10-02T08:00:00+00:00',
                                  'AuthUserID': 'u5'}],
    }
    for table, rows in extra.items():
        for r in rows:
            r.update(audit)
        t.setdefault(table, []).extend(rows)
    return t


# (list endpoint, primary key of the rows it lists)
LISTS = {
    'payment':     ('payment.index', 'PaymentID'),
    'sale':        ('sale.index', 'SaleID'),
    'order':       ('online_order.index', 'OrderID'),
    'appointment': ('appointment.index', 'AppointmentID'),
    'po':          ('purchase_order.index', 'PurchaseOrderID'),
    'motorbike':   ('new_motorbike.index', 'NB_ID'),
    'application': ('supplier_application.index', 'ApplicationID'),
}

# Queries that worked before Phase 7 (old prefixed forms, partial forms, text, numbers).
SEARCH_BEFORE = {
    'payment':     ['SALE-1', 'SALE-15', 'sale-1', 'sale', 'APPT-#1', 'appt', 'ORD-000001', 'ord1', '1',
                    'cash', 'Alice', '2026-10-04', 'Deposit'],
    'sale':        ['NB-1', 'nb-1', 'Bob', 'Alice', 'honda', '2026-10-02'],
    'order':       ['ORD-000012', 'ord12', '12', '000001', 'Bob', '5777'],
    'appointment': ['AB1', 'Repair', 'Pending', 'Sam', '2026-10-08'],
    'po':          ['Parts', 'Pending', '2026-10-20'],
    'motorbike':   ['NB7', 'Red', '2026', 'Available'],
    'application': ['Five', 'C5', 'f@f.mu'],
}

RECORDED = {'application': {'C5': [5], 'Five': [5], 'f@f.mu': [5]},
 'appointment': {'2026-10-08': [3], 'AB1': [1, 3], 'Pending': [3], 'Repair': [3], 'Sam': [1, 3]},
 'motorbike': {'2026': [7], 'Available': [7], 'NB7': [7], 'Red': [1, 7]},
 'order': {'000001': [1], '12': [12], '5777': [12], 'Bob': [12], 'ORD-000012': [12], 'ord12': [12]},
 'payment': {'1': [1, 2, 3, 4, 12],
             '2026-10-04': [4],
             'APPT-#1': [2],
             'Alice': [1, 3],
             'Deposit': [1, 4, 12],
             'ORD-000001': [3],
             'SALE-1': [1, 4],
             'SALE-15': [4],
             'appt': [2],
             'cash': [1, 2, 12],
             'ord1': [3],
             'sale': [1, 4, 12],
             'sale-1': [1, 4]},
 'po': {'2026-10-20': [12], 'Parts': [1, 12], 'Pending': [1, 12]},
 'sale': {'2026-10-02': [2, 15],
          'Alice': [1],
          'Bob': [2, 15],
          'NB-1': [1, 2, 15],
          'honda': [1, 2, 15],
          'nb-1': [1, 2, 15]}}
