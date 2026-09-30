# Admin Panel — Codebase Context and Developer Handoff

**Project:** Motorbike Sales and Servicing Management System  
**Component:** Admin Panel (staff-only internal web application)  
**Student:** Utsav Ramjattan — BSc (Hons) Software Engineering, UTM Mauritius  
**Supervisor:** Mr. Hansraj Seegobin  
**Document purpose:** Developer handoff context for future AI chats and Client Side development.  
**Primary reference:** `Motorbike_Admin_Panel_Technical_Report.md` covers full project history and design decisions. This document covers the **current source code implementation**.

---

## How to use this document

Attach both this file and `Motorbike_Admin_Panel_Technical_Report.md` at the start of a new AI chat. This file describes what the code actually does right now. The technical report provides the reasoning behind it. Together they give a complete picture without re-explaining the project from scratch.

---

## 1. Project Structure

```
motorbike-admin/
├── run.py                        Entry point — calls create_app(), starts Flask dev server
│                                 Run with: py run.py (Windows PowerShell)
├── config.py                     Loads SECRET_KEY, DEBUG from .env via python-dotenv
├── requirements.txt               Flask==3.1.0, python-dotenv==1.0.1, supabase==2.10.0
├── .env                           SUPABASE_URL, SUPABASE_KEY (anon key) — never committed
├── .gitignore
│
└── app/
    ├── __init__.py               APPLICATION FACTORY — create_app(), registers all 20 blueprints
    ├── supabase_client.py        Shared Supabase client instance (imported everywhere)
    │
    ├── auth/
    │   ├── routes.py             /auth/login (GET/POST), /auth/logout
    │   └── decorators.py        @login_required — wraps every protected route
    │
    ├── dashboard/
    │   └── routes.py             /dashboard — live count cards for all 18 modules
    │
    ├── modules/
    │   ├── color/                URL: /colors
    │   ├── category/             URL: /categories
    │   ├── brand/                URL: /brands
    │   ├── model/                URL: /models
    │   ├── spare_parts/          URL: /spare-parts
    │   ├── stock/                URL: /stock
    │   ├── service/              URL: /services
    │   ├── role/                 URL: /roles
    │   ├── employee/             URL: /employees
    │   ├── supplier/             URL: /suppliers
    │   ├── compatibility/        URL: /compatibility
    │   ├── purchase_order/       URL: /purchase-orders (covers PO and PO Items)
    │   ├── customer/             URL: /customers
    │   ├── customer_bike/        URL: /customer-bikes
    │   ├── new_motorbike/        URL: /new-motorbikes
    │   ├── appointment/          URL: /appointments (covers appointment + bridge tables)
    │   ├── sale/                 URL: /sales
    │   └── payment/              URL: /payments
    │       (each module folder contains: __init__.py + routes.py)
    │
    ├── utils/
    │   ├── validators.py         required_fields(), is_positive_number(),
    │   │                          is_positive_integer(), is_valid_email()
    │   ├── pagination.py         paginate(records, page, per_page=10)
    │   └── flash_messages.py     flash_success(), flash_error(), flash_warning()
    │
    ├── static/
    │   ├── css/admin.css         Single growing stylesheet for the whole panel
    │   └── js/admin.js           Single growing script for the whole panel
    │
    └── templates/
        ├── layout/
        │   ├── base.html          <head>, CDN links (Bootstrap 5.3, Font Awesome 6.5,
        │   │                       Google Fonts Inter), {% block body %}, {% block scripts %}
        │   └── admin_layout.html  Sidebar + header + flash messages + content + footer
        ├── auth/
        │   └── login.html
        ├── dashboard/
        │   └── index.html
        ├── components/            REUSABLE JINJA MACROS (built in Task 06)
        │   ├── table.html          search_bar(), data_table()
        │   ├── form_field.html     text_field, number_field, select_field,
        │   │                        textarea_field, readonly_field, date_field, time_field
        │   ├── modal_confirm.html  delete_modal()
        │   ├── alert.html          info_alert(), warning_alert()
        │   └── pagination.html     pagination_controls()
        └── modules/
            (one sub-folder per module, each with list.html + form.html,
             plus view.html / item_form.html / service_form.html /
             stock_form.html / receive_form.html where needed)
```

---

## 2. Application Architecture

### 2.1 Flask Application Factory

`app/__init__.py` defines `create_app()`. It creates the Flask instance, loads config, and registers every Blueprint with its URL prefix. `run.py` calls this factory and starts the dev server.

Each module Blueprint is registered in dependency order (simpler modules first so their dropdowns exist when more complex modules need them). The root `/` redirects to `/dashboard`.

### 2.2 Blueprint Pattern

Every module follows an identical two-file pattern:

**`app/modules/<module>/__init__.py`**
```python
from flask import Blueprint
bp = Blueprint('<module_name>', __name__)
from app.modules.<module> import routes  # noqa
```

**`app/modules/<module>/routes.py`** — contains all route functions, private helpers (`_get_form_options()`, `_validate_year()`, `_enrich_*()`, etc.), and predefined option lists.

This pattern means adding a new module never touches any other module's code — only a new folder, two files, and one registration line in `app/__init__.py`.

### 2.3 Supabase Client

`app/supabase_client.py` creates a single shared `supabase` client using the URL and anon key from `.env`. Every routes file imports it:

```python
from app.supabase_client import supabase
```

All database operations go through this client using the supabase-py query builder. There is no ORM (no SQLAlchemy). Typical pattern:

```python
result = supabase.table('Customer').select('*').order('LastName').execute()
records = result.data or []
```

### 2.4 Request Flow

```
Browser
  │
  ▼  HTTP request (GET or POST)
Flask route (Blueprint)
  │
  ├── @login_required checks Flask session → redirects to /auth/login if no session
  │
  ├── GET: fetch data from Supabase → enrich with lookups → paginate → render template
  │
  └── POST:
        ├── Read request.form.to_dict()
        ├── Validate fields in Python (collect all errors, show simultaneously)
        ├── If errors → re-render form with errors + retained form_data
        └── If valid → Supabase insert/update/delete → flash message → redirect
```

### 2.5 Templates

All pages extend `layout/base.html` (head, CDN scripts) → `layout/admin_layout.html` (sidebar, header, flash display, `{% block content %}`). Module templates extend `admin_layout.html` and fill `{% block content %}`. A `{% block scripts %}` in `base.html` is used by the Payment form for its inline JavaScript.

### 2.6 CSS and JS

`app/static/css/admin.css` — single file, grows as modules were added. CSS variables define the design system:

```css
:root {
    --sidebar-width: 260px;
    --sidebar-bg: #1a2332;
    --accent: #e67e22;
    --accent-hover: #d35400;
    --content-bg: #f0f2f5;
    --card-bg: #ffffff;
    --border-radius: 8px;
    --font-family: 'Inter', -apple-system, ...;
}
```

Key CSS classes: `.admin-card`, `.form-card`, `.form-section-title`, `.page-header`, `.btn-accent`, `.role-badge`, `.po-status-badge`, `.appt-type-badge`, `.appt-status-badge`, `.pay-type-badge`, `.bike-status-badge`, `.receive-mode-option`, `.sale-info-card`.

`app/static/js/admin.js` — single file, all inside one `DOMContentLoaded` listener. Contains:
- Delete modal population (data-* attribute pattern)
- Sidebar toggle/overlay for mobile
- Purchase Order receive-form mode toggle (existing/new stock radio buttons)
- Payment form reference type toggle (Sale/Appointment radio buttons)

**Important:** The Payment form's Sale auto-fill JS and the balance panel JS live inside a `{% block scripts %}` block in `app/templates/modules/payment/form.html` itself, not in `admin.js`.

### 2.7 Utilities

`app/utils/validators.py`:
- `required_fields(form_data, field_list)` — returns set of field names that are empty
- `is_positive_number(value)` — returns True if value can be parsed as a non-negative float
- `is_positive_integer(value)` — returns True if value can be parsed as a non-negative integer
- `is_valid_email(value)` — checks for exactly one `@`, non-empty local part, `.` in domain

`app/utils/pagination.py`:
- `paginate(records, page, per_page=10)` — returns an object with `.records`, `.total`, `.page`, `.total_pages`, `.has_prev`, `.has_next`. **Templates must use `pagination.records`** — not `pagination.items`.

`app/utils/flash_messages.py`:
- `flash_success(msg)`, `flash_error(msg)`, `flash_warning(msg)` — wrappers for Flask `flash()`

### 2.8 Authentication

- Supabase Auth (`email + password`) — no third-party providers
- Login route calls `supabase.auth.sign_in_with_password()` and stores `access_token`, `refresh_token`, `user_email` in Flask session
- `@login_required` decorator in `app/auth/decorators.py`:
  1. Checks `session.get('access_token')`
  2. Calls `supabase.auth.set_session(access_token, refresh_token)` to restore the JWT
  3. Calls `supabase.auth.get_user(access_token)` to validate
  4. On failure: `session.clear()` → redirect to login
- `set_session()` before every request is what makes the audit trigger's `auth.uid()` resolve to the real logged-in staff member's email in `Created_By`/`Updated_By`
- Logout: `supabase.auth.sign_out()` + `session.clear()`

### 2.9 Audit Fields

Every substantive table carries `Date_Created`, `Created_By`, `Date_Updated`, `Updated_By`. These are **never set by application code** — they are auto-populated by a shared PostgreSQL trigger function `set_audit_fields()` that fires `BEFORE INSERT OR UPDATE` on every table. The trigger resolves `auth.uid()` to the logged-in user's email via the Supabase Auth JWT. Application code never passes audit fields in insert or update payloads.

### 2.10 Row Level Security

All tables have RLS enabled. A single policy `"admin_full_access"` on each table allows full CRUD for the `authenticated` role:

```sql
CREATE POLICY "admin_full_access" ON public."TableName"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);
```

The anon role has no grants (temporary development grants were revoked at Task 17 when auth was implemented). This means any database query made without a valid authenticated JWT returns no data — two-layer protection alongside `@login_required`.

---

## 3. Module-by-Module Code Map

### Convention shared by all modules

| Element | Pattern |
|---|---|
| Blueprint | `bp = Blueprint('<name>', __name__)` |
| List route | `@bp.route('/')` — fetches all, enriches, paginates, renders `list.html` |
| Create route | `@bp.route('/create', methods=['GET', 'POST'])` |
| Edit route | `@bp.route('/edit/<int:id>', methods=['GET', 'POST'])` |
| Delete route | `@bp.route('/delete/<int:id>', methods=['POST'])` |
| Validation | Collect all errors before re-rendering; `novalidate` on all `<form>` tags |
| FK dropdowns | Always built from live Supabase queries; raw ID entry never exposed |
| Audit fields | Never set in application code — trigger only |
| Pagination | `pagination = paginate(all_records, page, per_page=10)` |
| Delete errors | FK violation caught by string-matching `'foreign key'` in exception message |

---

### 3.1 Color — `/colors`

**Tables:** `Color`  
**PK:** `Color` (string — the color name itself is the PK, not a surrogate integer)  
**Special:** Because the PK is the color name string, Edit updates the PK directly. The Color FK on `New_MotorBike.Color_Color` means deleting a Color used by a New_MotorBike produces an FK error. The Color dropdown in New_MotorBike uses `(Color, Color)` tuples (value and label are the same string).

---

### 3.2 Category — `/categories`

**Tables:** `Category`  
**PK:** `CAT_ID` (integer)  
**UNIQUE:** `CAT_desc`  
**FK dependents:** `Spare_Parts.Category_CAT_ID`  
**Duplicate error:** "A category with this description already exists."

---

### 3.3 Role — `/roles`

**Tables:** `Role`  
**PK:** `Role_ID`  
**UNIQUE:** `Role_Name`  
**Fields:** `Role_Name` (VARCHAR 15), `HourlyRate` (NUMERIC 10,2 — internal payroll rate, not customer-facing)  
**FK dependents:** `Employee.Role_Role_ID`

---

### 3.4 Supplier — `/suppliers`

**Tables:** `Supplier`  
**PK:** `SupplierID`  
**UNIQUE:** `SupplierName`  
**Fields:** `SupplierName`, `Phone`, `Email` (validated with `is_valid_email`), `Address` (textarea), `Country`  
**FK dependents:** `PurchaseOrder.Supplier_SupplierID`

---

### 3.5 Brand — `/brands`

**Tables:** `Brand`  
**PK:** `Brand_ID`  
**UNIQUE:** `Brand_Name`  
**FK dependents:** `Model.Brand_Brand_ID`, `Stock.Brand_Brand_ID`  
**Delete error:** "...referenced by one or more models or stock entries."

---

### 3.6 Service — `/services`

**Tables:** `Service`  
**PK:** `ServiceID`  
**UNIQUE:** `Service_Name`  
**Fields:** `Service_Name`, `Description` (textarea, truncated to 60 chars in list view), `Cost` (NUMERIC 10,2 — customer-facing appointment service price)  
**FK dependents:** `appointment_service.Service_ServiceID`

---

### 3.7 Employee — `/employees`

**Tables:** `Employee`  
**PK:** `EmployeeID`  
**FK:** `Role_Role_ID` → `Role` (required); `SupervisorID` → `Employee` (self-referencing, nullable)  
**Special:** On Edit, the employee being edited is filtered out of the Supervisor dropdown to prevent self-reference. Empty `SupervisorID` stored as `None` (not empty string).  
**FK dependents:** `Appointment.Employee_EmployeeID`, `Sale.Employee_EmployeeID`

---

### 3.8 Model — `/models`

**Tables:** `Model`  
**PK:** `Model_No` (route param is `model_no`)  
**UNIQUE:** `Description`  
**FK:** `Brand_Brand_ID` → `Brand`  
**Label format in dropdowns:** `Brand_Name — Description`  
**FK dependents:** `Customer_bike.Model_Model_No`, `New_MotorBike.Model_Model_No`, `Compatibility.Model_Model_No`  
**Important note:** The direct `Spare_Parts → Model` relationship was removed during development (supervisor's ERD review). Model compatibility is now exclusively managed through the `Compatibility` table.

---

### 3.9 Spare Parts — `/spare-parts`

**Tables:** `Spare_Parts`  
**PK:** `SP_id`  
**FK:** `Category_CAT_ID` → `Category` (required)  
**Fields:** `SP_name`, `SP_desc` (textarea), `Category_CAT_ID`  
**Important:** `Model_Model_No` was originally on this table but was removed when the Compatibility bridge table was introduced. The Spare Parts form has **no Model dropdown**. Model compatibility is managed entirely through the Compatibility module.  
**FK dependents:** `Stock.Spare_Parts_SP_id`, `PurchaseOrderItem.SP_id`, `Compatibility` (via Stock)

---

### 3.10 Stock — `/stock`

**Tables:** `Stock`  
**PK:** `Stock_ID`  
**FK:** `Spare_Parts_SP_id` → `Spare_Parts` (required); `Brand_Brand_ID` → `Brand` (required)  
**Fields:** `Size` (VARCHAR 20, **nullable** — made optional per supervisor review), `QOH` (quantity on hand, integer), `S_Price` (NUMERIC 10,2), `Warranty` (integer, months)  
**List display:** QOH = 0 rows rendered with `.stock-zero` CSS class (red highlight)  
**QOH is modified by:**
  1. Admin directly editing a Stock record
  2. Purchase Order receiving workflow (PurchaseOrderItem receive_item route)
  3. Appointment completion (`_deduct_stock_for_appointment()` in appointment routes)  
**FK dependents:** `Appointment_Stock.Stock_Stock_ID`, `PurchaseOrderItem.Stock_Stock_ID`, `Compatibility.Stock_Stock_ID`

---

### 3.11 Compatibility — `/compatibility`

**Tables:** `Compatibility`  
**PK:** `Com_ID`  
**FK:** `Stock_Stock_ID` → `Stock` (required); `Model_Model_No` → `Model` (required)  
**Fields:** `Year_From` (integer, nullable), `Year_To` (integer, nullable)  
**UNIQUE constraint:** `(Stock_Stock_ID, Model_Model_No, Year_From, Year_To)`  
**Create form special:** Uses a `<select multiple>` for Model — one submission can link one Stock item to multiple Models. A loop inserts one row per selected Model, with per-row duplicate skipping and a combined success/duplicate count in the flash message.  
**Edit form:** Single-select only (editing one existing record).  
**Year validation:** `_validate_year()` helper — range 1900–2100, nullable. Cross-field: `Year_To >= Year_From` when both provided.  
**Label format:** Stock options: `SP_name [Size] — Brand_Name` (size omitted if null). Model options: `Brand_Name — Description`.  
**Enrichment:** List view builds `_stock_label` and `_model_label` via lookup dicts (3-table chain for Stock: Stock → Spare_Parts → Brand).

---

### 3.12 Purchase Order — `/purchase-orders`

This module manages both `PurchaseOrder` (header) and `PurchaseOrderItem` (line items). Items live in the PO detail view, not their own sidebar entry.

**PurchaseOrder table:** `PurchaseOrderID`, `POrderDate` (DATE), `ExpectedDate` (DATE), `Status` (VARCHAR 30), `Supplier_SupplierID`  
**Status options:** Pending, Partially Received, Received, Cancelled  
**Cross-field validation:** `ExpectedDate` must be on or after `POrderDate`

**PurchaseOrderItem table:** `POItem_ID`, `PurchaseOrder_ID`, `SP_id`, `Quantity_Ordered`, `BuyingPrice`, `Size_Expected` (optional VARCHAR 20), `Stock_Stock_ID` (NULL until received), `Quantity_Received`, `DateReceived`, `Status` (Ordered / Received)  
**Key design:** Items reference `Spare_Parts` at order time (`SP_id`), not `Stock`. `Stock_Stock_ID` is NULL when the item is created and only populated when the item is received.

**Item routes (all within the purchase_order blueprint, URL pattern `/<po_id>/items/...`):**
- `add_item` — add a new item to a PO (blocked if PO Status is Received or Cancelled)
- `edit_item` — edit an Ordered item (blocked if Status is Received)
- `delete_item` — delete an Ordered item (blocked if Status is Received)
- `receive_item` — the two-path receiving workflow (GET shows form, POST executes)

**Two-path receiving workflow:**
- **Path A (existing stock):** Admin selects existing Stock record for the same Spare Part. Route fetches current `QOH`, updates `Stock.QOH += Quantity_Received`, links `POItem.Stock_Stock_ID`.
- **Path B (new stock):** Admin fills in Brand, Size, Selling Price, Warranty. Route inserts new Stock row with `QOH = Quantity_Received`, uses the new `Stock_ID` as `POItem.Stock_Stock_ID`.
- In both paths: `POItem.Status` set to `'Received'`, `Quantity_Received` and `DateReceived` set.
- After any receive: `_auto_update_po_status(po_id)` recalculates PO Status (all received → Received; some received → Partially Received; none received → leave as Pending).

**Templates:** `list.html`, `form.html`, `view.html` (shows items table with Receive/Edit/Delete buttons), `item_form.html`, `receive_form.html`  
**Receive form toggle JS:** Lives in `admin.js` — radio button switches between "Add to Existing Stock" and "Create New Stock Entry" sections.

**PO_NewMotorBike (added post-Task 26 — motorcycle purchase ordering):** A supervisor review identified that PurchaseOrder only supported spare-part procurement (`PurchaseOrderItem`); there was no way to record a motorcycle unit as having been purchased through a PO. A new bridge table, `PO_NewMotorBike`, was added and wired into this same module, mirroring the two-path pattern already used for spare-parts receiving:

- **Table:** `PO_NewMotorBike` — composite PK `(PurchaseOrder_PurchaseOrderID, New_MotorBike_NB_ID)`. Columns: `BuyingPrice` (NUMERIC 10,2), `DateReceived` (DATE, nullable — a motorbike can be linked to a PO before it physically arrives). No audit columns, matching the other pure bridge tables (`appointment_service`, `Appointment_Stock`).
- **UNIQUE constraint:** `PO_NewMotorBike_unique_bike` on `New_MotorBike_NB_ID` — a single physical motorbike can only ever be linked to one PurchaseOrder.
- **No Quantity/Status split:** unlike `PurchaseOrderItem`, there is no "Ordered vs Received" tracking for motorbikes — a row simply records that a specific `New_MotorBike` unit was procured via that PO, at what price, and (once known) when it arrived.
- **Routes (all within the `purchase_order` blueprint, URL pattern `/<po_id>/motorbikes/...`):**
  - `add_motorbike` — link a motorcycle to a PO. Two modes toggled by radio buttons (reusing the existing `receive-mode-selector` JS wiring from `admin.js`): **Existing Motorcycle Record** (select an already-created `New_MotorBike` not yet linked to any PO), or **New Motorcycle Record** (create the `New_MotorBike` row inline, reusing `new_motorbike.routes._validate_form()` and `_get_form_options()` directly rather than duplicating that validation). Blocked if PO Status is Received or Cancelled.
  - `edit_motorbike` — edit only `BuyingPrice`/`DateReceived` for an already-linked motorcycle (the motorcycle itself is not re-selectable). Blocked if PO Status is Received or Cancelled.
  - `delete_motorbike` — unlink a motorcycle from the PO.
- **`view()` route addition:** fetches all `PO_NewMotorBike` rows for the PO via `_enrich_po_motorbikes()`, resolving each into a display label (`Brand_Name Model_Description (Year)`), VIN, and Status, shown in a new "Motorcycles Ordered" section on the PO detail page alongside the existing "Line Items" section.
- **Template:** new file `modules/purchase_order/motorbike_form.html` (shared by add/edit, following the same `is_edit` pattern as the rest of the codebase).
- **Known open item (identified during review, not yet resolved):** in `add_motorbike()`'s "New Motorcycle Record" path, the `New_MotorBike` insert and the `PO_NewMotorBike` insert are currently caught by a single `try/except`, so a VIN-uniqueness failure on the `New_MotorBike` insert can be misreported as "this motorcycle is already linked to another purchase order" instead of a VIN-duplicate error. Also, unlike `PurchaseOrderItem`'s `_auto_update_po_status()`, linking or editing a `PO_NewMotorBike` row does not currently recalculate the PO's own `Status` field — whether it should (and how, given motorbikes have no Ordered/Received split) is an open design question for the next review pass.

---

### 3.13 Customer — `/customers`

**Tables:** `Customer`  
**PK:** `CustomerID`  
**UNIQUE:** `NIC`, `PhoneNumber` (added post-Task 21 to prevent duplicates)  
**Required fields (7):** `FirstName`, `LastName`, `PhoneNumber`, `Email`, `Street`, `Town`, `NIC`  
**Optional fields:** `HomeNumber`, `PostCode` (stored as `None` when blank, not empty string)  
**Email validation:** `is_valid_email()` from validators  
**Form layout:** Two-card form — "Personal Information" card + "Address" card — single `<form>` tag spanning both cards  
**FK dependents:** `Customer_bike.Customer_CustomerID`, `Sale.Customer_CustomerID`  
**Delete error:** "...they have associated bike registrations or sales records."

---

### 3.14 Customer Bike — `/customer-bikes`

**Tables:** `Customer_bike`  
**PK:** `BikeID`  
**UNIQUE:** `VIN`, `RegistrationNumber` (added post-Task 22)  
**FK:** `Customer_CustomerID` → `Customer` (required); `Model_Model_No` → `Model` (required)  
**Fields:** `RegistrationNumber` (max 6 chars — Mauritius plate format), `Year` (1900–2100), `VIN` (max 50)  
**Dropdown labels:** Customer: `FirstName LastName`; Model: `Brand_Name — Description`  
**Ownership transfer:** When a bike changes owner, the existing `Customer_bike` record is edited and `Customer_CustomerID` is updated to the new owner. No new record is created. VIN and registration uniqueness constraints enforce this — attempting to insert a duplicate VIN fails.  
**Cross-table VIN note:** A `Customer_bike` and a `New_MotorBike` CAN share the same VIN — this is by design (dealer sells a bike → New_MotorBike marked Sold → Customer registers same bike for service → Customer_bike record with same VIN). No cross-table uniqueness constraint exists.  
**FK dependents:** `Appointment.Customer_bike_BikeID`

---

### 3.15 New MotorBike — `/new-motorbikes`

**Tables:** `New_MotorBike`  
**PK:** `NB_ID`  
**UNIQUE:** `VIN`  
**CHECK:** `Status IN ('Available', 'Sold')`  
**FK:** `Model_Model_No` → `Model`; `Color_Color` → `Color` (string FK — Color table's PK is the color name string)  
**Fields (11):** `Year` (1900–2100), `Price` (NUMERIC 10,2), `VIN` (max 50), `Status` (Available/Sold), `Model_Model_No`, `Color_Color`, `Warranty_Months` (integer), `EngineCC` (integer ≥ 1), `FuelType` (Petrol/Diesel/Electric/Hybrid), `Transmission` (Manual/Automatic/Semi-Automatic), `FuelTankCapacity` (NUMERIC 5,2, must be > 0)  
**Form layout:** Two cards — "Bike Details" + "Technical Specifications". Single `<form>` opens in Card 1 and closes at end of Card 2.  
**Status:** Normally controlled by the Sale module. When a Sale is created, the bike's Status is set to 'Sold'. When a Sale is deleted, it resets to 'Available'. Manually editable here but the authoritative transition is in Sale routes.  
**Sold warning:** Edit form shows a yellow alert banner if `record.Status == 'Sold'`.  
**VIN truncation:** List table shows first 20 chars + `...` for VINs longer than 20 chars. Full VIN visible in Edit form.  
**Color dropdown:** Options are `(Color, Color)` tuples — value and label are identical strings.  
**FK dependents:** `Sale.New_MotorBike_NB_ID`

---

### 3.16 Appointment — `/appointments`

This is the most complex module. It manages appointment headers plus two bridge tables via the detail view.

**Tables used:** `Appointment`, `appointment_service`, `Appointment_Stock`, `Service`, `Stock`, `Spare_Parts`, `Brand`, `Customer_bike`, `Customer`, `Employee`

**Appointment table fields:** `AppointmentID`, `Appointment_Date` (DATE), `AppointmentType` (Service/Repair/Inspection/Other), `Appointment_time` (TIME — stored as `HH:MM:SS` but HTML input requires `HH:MM`), `Status` (Pending/Confirmed/In Progress/Completed/Cancelled/No Show), `Customer_bike_BikeID`, `Employee_EmployeeID`  
**LOCKED_STATUSES = ('Completed', 'Cancelled')** — once an appointment reaches either status, services and stock cannot be added, edited, or deleted.

**`_truncate_time(time_str)`** — converts `HH:MM:SS` from Supabase to `HH:MM` for the `<input type="time">` pre-population on Edit form.

**Dropdown labels:** Customer Bike: `RegistrationNumber — FirstName LastName`; Employee: `FirstName LastName`

**`view()` route:** The most data-intensive route in the project. Fetches:
1. Appointment record
2. Bike label (Customer_bike → Customer lookup)
3. Employee name
4. All `appointment_service` rows, enriched with `_service_name` and `_service_cost` from the Service table
5. All `Appointment_Stock` rows, enriched with `_stock_label` (Spare_Parts + Brand) and `_stock_price` from the Stock table
6. Calculates `service_total`, `stock_total`, `appt_total` (Cost Summary)
7. Fetches all linked payments from `Payment` table, calculates `appt_total_paid` and `appt_remaining`

Passes to template: `appt_services`, `appt_stock`, `appt_payments` (list — multiple payments now supported), `service_total`, `stock_total`, `appt_total`, `appt_total_paid`, `appt_remaining`, `is_locked`, `appt_status`.

**`appointment_service` bridge table:**
- Composite PK: `(Appointment_AppointmentID, Service_ServiceID)`
- `Quantity` — nullable (a service can be logged without a count)
- Routes: `add_service`, `edit_service` (quantity only), `delete_service`
- Add form dropdown excludes services already linked to this appointment

**`Appointment_Stock` bridge table:**
- Composite PK: `(Appointment_AppointmentID, Stock_Stock_ID)`
- `Quantity` — NOT NULL
- Routes: `add_stock`, `edit_stock` (quantity only), `delete_stock`
- Add form dropdown built by `_build_stock_options(exclude_ids=...)` — shows `SP_name [Size] — Brand_Name (QOH: X)`, excludes already-added stock

**Stock deduction on completion (`_deduct_stock_for_appointment(appt_id)`):**
- Called from `edit()` exactly once — only when `Status` transitions INTO `'Completed'`
- Guard: `if status_value == 'Completed' and previous_status != 'Completed':`
- `previous_status` is fetched from `record.get('Status')` (the pre-POST database state) before `form_data` is overwritten
- For each `Appointment_Stock` row: fetches current `Stock.QOH`, updates `QOH = max(0, current_qoh - qty_used)`
- Re-saving an already-Completed appointment does NOT re-trigger deduction

**Estimated Cost Summary (Appointment view):**
- `service_total = Σ (service_cost × qty)` — qty defaults to 1 if null
- `stock_total = Σ (S_Price × qty)` — qty defaults to 0 if null
- `appt_total = service_total + stock_total`
- Never stored in the database — always recalculated live from current linked rows

**Payment section in Appointment view:**
- Shows a balance panel: Appointment Total / Already Paid / Remaining Balance
- Lists ALL payments for the appointment (multiple rows supported)
- "Add Payment" button links to `/payments/create?prefill_appt=<appt_id>`
- "Add Payment" is greyed out (disabled) when `is_locked` OR `appt_remaining <= 0.001`

**Templates:** `list.html`, `form.html`, `view.html`, `service_form.html`, `stock_form.html`

---

### 3.17 Sale — `/sales`

**Tables:** `Sale`, `Customer`, `New_MotorBike`, `Employee`, `Model`, `Brand`, `Payment`

**Sale table fields:** `SaleID`, `SaleDate` (DATE), `TotalAmount` (NUMERIC 10,2), `Customer_CustomerID`, `New_MotorBike_NB_ID`, `Employee_EmployeeID` (nullable)  
**UNIQUE:** `New_MotorBike_NB_ID` — each motorbike can only be sold once

**`_set_bike_status(nb_id, status)`** — updates `New_MotorBike.Status`. Called:
- After successful Create → sets to `'Sold'`
- After successful Delete → resets to `'Available'`
- On Edit, if bike changed → resets old bike to `'Available'`, sets new bike to `'Sold'`

**Create form bike dropdown:** Only bikes with `Status = 'Available'` appear. Filtered live from the database.

**Edit form bike dropdown:** Available bikes PLUS the currently-linked bike (re-admitted even though it is Sold, so the current selection pre-populates correctly). Implemented in `_get_form_options(current_nb_id=...)`.

**Sale price auto-fill (JavaScript):** On Create/Edit, selecting a motorbike from the dropdown auto-fills the `TotalAmount` field with that bike's `Price` from `New_MotorBike`. Uses `bike_prices | tojson` passed from the route into the template, with a JS `change` event listener. Value remains editable for negotiated prices.

**Delete protection:** If a Sale has a Payment, delete fails with FK error: "...linked to a sales record. Remove the associated sale before deleting this motorbike." / "...has an associated payment record."

**`view()` route:** Resolves customer name, bike label (NB_ID → Model → Brand), employee name, and fetches all linked payments.

**Templates:** `list.html`, `form.html`, `view.html`

**`_build_bike_label(nb_id, year, model_desc, brand_name)`** — formats as `NB-{id} — Brand_Name ModelDesc ({Year})`

---

### 3.18 Payment — `/payments`

The most business-logic-heavy module. Supports partial/deposit/instalment payments for both Sales and Appointments.

**Payment table fields:** `PaymentID`, `PaymentDate` (DATE), `AmountPaid` (NUMERIC 10,2), `PaymentMethod` (Cash/Card/Bank Transfer/Online), `PaymentType` (Full Payment/Deposit/Instalment), `Sale_SaleID` (nullable), `Appointment_AppointmentID` (nullable)  
**CHECK constraint:** `Sale_SaleID IS NOT NULL OR Appointment_AppointmentID IS NOT NULL`  
**Important:** The `UNIQUE ("Appointment_AppointmentID")` constraint was **dropped** via migration to enable multiple partial payments per appointment. SQL: `ALTER TABLE public."Payment" DROP CONSTRAINT IF EXISTS "unique_appointment_payment";`

**Reference type (Sale vs Appointment):** On Create, a two-card radio toggle selects which type. On Edit, the reference type is **locked** — a Sale payment cannot be changed to an Appointment payment or vice versa. The Edit form shows a read-only type indicator and a hidden `reference_type` input.

**Key helpers:**

`_get_sale_total_paid(sale_id, exclude_payment_id=None)` — sums `AmountPaid` for all payments linked to this Sale, optionally excluding the payment currently being edited.

`_get_appointment_total(appt_id)` — recalculates the appointment's total cost live (identical logic to the Appointment view's cost summary: services × qty + stock × S_Price). Used for Appointment payment balance validation.

`_get_appointment_total_paid(appt_id, exclude_payment_id=None)` — sums `AmountPaid` for all payments linked to this Appointment.

`_get_sale_options(exclude_sale_id=None)` — returns Sales with remaining balance > 0. Fully-paid Sales are excluded. The currently-linked Sale (on Edit) is always included. Label format: `SALE-{id} — Customer (Date) [Rs. X remaining]`.

`_get_appointment_options(exclude_appt_id=None)` — returns Appointments with remaining balance > 0 (calculated via `_get_appointment_total` and `_get_appointment_total_paid`). Fully-paid Appointments are excluded. Label format: `APPT-#{id} — RegistrationNo (Date) [Rs. X remaining]`.

**`_validate_form(form_data, current_appt_id, current_payment_id, locked_ref_type)`:**
- Validates reference selection (Sale or Appointment)
- Validates PaymentDate, AmountPaid, PaymentMethod, PaymentType
- For Sale payments: checks `AmountPaid <= remaining balance` (uses `_get_sale_total_paid` excluding current payment)
- For Appointment payments: checks same logic using `_get_appointment_total` and `_get_appointment_total_paid`
- Produces exact-figure error messages: "Amount paid (Rs. X) exceeds the remaining balance of Rs. Y..."

**JSON endpoints:**
- `GET /payments/sale-info/<sale_id>?exclude_payment_id=<id>` — returns `{sale_date, total_amount, total_paid, remaining}` as JSON for the balance panel
- `GET /payments/appointment-info/<appt_id>?exclude_payment_id=<id>` — returns `{total_amount, total_paid, remaining}` as JSON

**Duplicate-submission protection (Create only):**
- GET: `session['payment_form_token'] = str(uuid.uuid4())` — stored in Flask session
- Form: `<input type="hidden" name="form_token" value="{{ form_token }}">` (in template)
- POST: checks `submitted_token == session_token`; if mismatch and session has a token → reject with flash error
- Token consumed immediately after matching (popped from session)
- New token generated if validation fails so user can retry legitimately
- Client-side: `paySubmitBtn.disabled = true` on first submit click (JS in `{% block scripts %}`)

**Balance panel (JavaScript in `form.html` `{% block scripts %}`):**
- Fetches `sale-info` or `appointment-info` via `fetch()` when a Sale or Appointment is selected
- Populates `#bal-total`, `#bal-paid`, `#bal-remaining` divs
- Auto-fills `PaymentDate` from `sale_date` (Sale payments only, only if date field is currently empty)
- Auto-fills `AmountPaid` with remaining balance (only if amount field is currently empty)
- Sets `max` attribute on amount field to remaining balance
- Triggers on initial page load if a value is already selected (covers Edit form and validation-failure resubmit)

**Templates:** `list.html`, `form.html`

---

## 4. Important Routes and Functions Reference

| File | Function / Route | Purpose |
|---|---|---|
| `app/auth/decorators.py` | `login_required(f)` | Validates session, restores Supabase JWT, redirects to login on failure. Applied to every route. |
| `app/auth/routes.py` | `login()` | POST: sign_in_with_password, store tokens. GET: render login page. |
| `app/auth/routes.py` | `logout()` | sign_out, session.clear(), redirect to login. |
| `app/dashboard/routes.py` | `_get_dashboard_counts()` | Queries all 18 tables with `count='exact'`, each in its own try/except for resilience. |
| `app/modules/appointment/routes.py` | `view(appt_id)` | Fetches appointment + services + stock + payments, calculates totals, renders view page. |
| `app/modules/appointment/routes.py` | `_deduct_stock_for_appointment(appt_id)` | Decrements `Stock.QOH` for each `Appointment_Stock` row. Called once on Completed transition. |
| `app/modules/appointment/routes.py` | `_build_stock_options(exclude_ids)` | Builds enriched Stock dropdown for appointment stock forms. |
| `app/modules/sale/routes.py` | `_set_bike_status(nb_id, status)` | Updates `New_MotorBike.Status`. Called on Sale create/edit/delete. |
| `app/modules/sale/routes.py` | `_get_form_options(current_nb_id)` | Returns customer options, bike options (Available only + current bike on Edit), employee options, and `bike_prices` dict for JS auto-fill. |
| `app/modules/payment/routes.py` | `sale_info(sale_id)` | JSON endpoint for Sale balance panel. Returns `total_amount`, `total_paid`, `remaining`. |
| `app/modules/payment/routes.py` | `appointment_info(appt_id)` | JSON endpoint for Appointment balance panel. |
| `app/modules/payment/routes.py` | `_get_sale_total_paid(sale_id, exclude)` | Sums all payments for a Sale. `exclude_payment_id` used on Edit to get correct remaining. |
| `app/modules/payment/routes.py` | `_get_appointment_total(appt_id)` | Recalculates appointment cost live from services + stock. Must match Appointment view's calculation. |
| `app/modules/payment/routes.py` | `_validate_form(...)` | Central validation for all 6 payment fields + balance checks for both Sale and Appointment. |
| `app/modules/purchase_order/routes.py` | `receive_item(po_id, item_id)` | Two-path receiving: updates existing Stock QOH or creates new Stock row. Updates POItem and auto-recalculates PO status. |
| `app/modules/purchase_order/routes.py` | `_auto_update_po_status(po_id)` | Recalculates PO Status after any item is received. |
| `app/modules/compatibility/routes.py` | `create()` | Multi-select loop — inserts one Compatibility row per selected Model, skips duplicates. |

---

## 5. Database Integration

### 5.1 Full Table List

| # | Table | Type | Module |
|---|---|---|---|
| 1 | `Color` | Phase 1 master | color |
| 2 | `Category` | Phase 1 master | category |
| 3 | `Role` | Phase 1 master | role |
| 4 | `Supplier` | Phase 1 master | supplier |
| 5 | `Brand` | Phase 1 master | brand |
| 6 | `Employee` | Phase 1 master | employee |
| 7 | `Model` | Phase 1 master | model |
| 8 | `Service` | Phase 1 master | service |
| 9 | `Spare_Parts` | Phase 1 master | spare_parts |
| 10 | `Stock` | Phase 1 master | stock |
| 11 | `Compatibility` | Bridge | compatibility |
| 12 | `PurchaseOrder` | Purchasing | purchase_order |
| 13 | `PurchaseOrderItem` | Purchasing | purchase_order |
| 14 | `Customer` | Phase 3 transactional | customer |
| 15 | `Customer_bike` | Phase 3 transactional | customer_bike |
| 16 | `New_MotorBike` | Phase 3 transactional | new_motorbike |
| 17 | `Appointment` | Phase 3 transactional | appointment |
| 18 | `appointment_service` | Bridge | appointment |
| 19 | `Appointment_Stock` | Bridge | appointment |
| 20 | `Sale` | Phase 3 transactional | sale |
| 21 | `Payment` | Phase 3 transactional | payment |
| 22 | `PO_NewMotorBike` | Bridge | purchase_order |

Bridge tables (`Compatibility`, `appointment_service`, `Appointment_Stock`, `PO_NewMotorBike`) have composite PKs and no audit fields.

### 5.2 Key Supabase Query Patterns

**Select all with ordering:**
```python
supabase.table('Customer').select('*').order('LastName').execute()
```

**Select specific columns (for lookup dicts):**
```python
supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
```

**Filtered select:**
```python
supabase.table('New_MotorBike').select('*').eq('Status', 'Available').order('NB_ID').execute()
```

**Single record:**
```python
supabase.table('Sale').select('*').eq('SaleID', sale_id).single().execute()
```

**Insert:**
```python
supabase.table('Customer').insert({'FirstName': ..., 'NIC': ...}).execute()
```

**Update:**
```python
supabase.table('Stock').update({'QOH': new_qoh}).eq('Stock_ID', stock_id).execute()
```

**Delete:**
```python
supabase.table('Color').delete().eq('Color', color_value).execute()
```

**Count (dashboard):**
```python
supabase.table('Appointment').select('*', count='exact').execute()
# result.count gives the row count
```

### 5.3 Important Constraints

| Table | Constraint | Type | Effect |
|---|---|---|---|
| `Brand` | `unique_brand_name` | UNIQUE | No duplicate Brand_Name |
| `Category` | `unique_category_desc` | UNIQUE | No duplicate CAT_desc |
| `Role` | `unique_role_name` | UNIQUE | No duplicate Role_Name |
| `Service` | `unique_service_name` | UNIQUE | No duplicate Service_Name |
| `Supplier` | `unique_supplier_name` | UNIQUE | No duplicate SupplierName |
| `Model` | `unique_model_description` | UNIQUE | No duplicate Description |
| `Customer` | `NIC` unique, `PhoneNumber` unique | UNIQUE (2) | No duplicate customers by NIC or phone |
| `Customer_bike` | `VIN` unique, `RegistrationNumber` unique | UNIQUE (2) | No duplicate vehicle records |
| `New_MotorBike` | `New_MotorBike_VIN_unique` | UNIQUE | No duplicate VIN in inventory |
| `New_MotorBike` | `New_MotorBike_Status_check` | CHECK | Status must be 'Available' or 'Sold' |
| `Sale` | `Sale_unique_bike` | UNIQUE on `New_MotorBike_NB_ID` | One sale per bike |
| `Compatibility` | `unique_compatibility` | UNIQUE | No duplicate (Stock, Model, Year_From, Year_To) |
| `Payment` | `Payment_requires_reference` | CHECK | At least one of Sale_SaleID or Appointment_AppointmentID must be non-null |
| ~~`Payment`~~ | ~~`unique_appointment_payment`~~ | ~~UNIQUE~~ | **DROPPED** — removed to support partial appointment payments |
| `PO_NewMotorBike` | `PO_NewMotorBike_unique_bike` | UNIQUE on `New_MotorBike_NB_ID` | One purchase order per physical motorbike |

### 5.4 Payment-Related Queries (most complex)

The payment balance calculation requires querying three things:

1. **Sale total:** `Sale.TotalAmount` from the Sale table
2. **Already paid:** Sum of all `Payment.AmountPaid` rows where `Sale_SaleID = X` (excluding current payment on Edit)
3. **Appointment total:** Dynamically computed from `appointment_service` (join Service for Cost) + `Appointment_Stock` (join Stock for S_Price) — never stored in the database
4. **Appointment already paid:** Sum of all `Payment.AmountPaid` rows where `Appointment_AppointmentID = X`

---

## 6. Shared Components

### 6.1 Layouts

**`templates/layout/base.html`**
- `<head>` with meta, title (`{% block title %}`), Bootstrap 5.3 CDN, Font Awesome 6.5 CDN, Google Fonts Inter
- `{% block body %}` for page body
- `{% block scripts %}` at end of body — used by Payment form for inline JS
- All pages extend this file

**`templates/layout/admin_layout.html`**
- Extends `base.html`
- Sidebar (fixed width, `height: 100vh; overflow-y: auto;` for scrolling)
- Navigation sections: Management, Purchasing, Customers, Inventory, Appointments, Transactions
- Active state: `{% if request.blueprint == '<name>' %}active{% endif %}`
- Header bar with page title (`{% block page_title %}`) and sidebar toggle button
- Flash messages display area
- `{% block content %}` for page content
- `{% block body %}` filled with the sidebar + header + content layout

### 6.2 Jinja Macros (`templates/components/`)

**`table.html`**
- `search_bar(action_url, search_query, placeholder)` — GET form with q parameter
- `data_table(headers, total, empty_message)` — renders table with empty state (inbox icon). Content filled via `{% call data_table(...) %}...{% endcall %}`.

**`form_field.html`** — all macros share: label, required asterisk, error display, help text
- `text_field(name, label, value, required, error, placeholder, help_text)`
- `number_field(name, label, value, required, error, placeholder, step, min_val, help_text)`
- `select_field(name, label, options, selected, required, error, empty_label, help_text)` — options is list of `(value, label)` tuples; uses `|string` comparison for pre-selection
- `textarea_field(name, label, value, required, error, placeholder, rows, help_text)`
- `readonly_field(label, value)` — displays read-only audit info
- `date_field(name, label, value, required, error, help_text)` — `<input type="date">`
- `time_field(name, label, value, required, error, help_text)` — `<input type="time">`, value must be `HH:MM`

**`modal_confirm.html`**
- `delete_modal()` — single Bootstrap modal per page, populated from trigger button `data-*` attributes
- JS in `admin.js` listens for `show.bs.modal`, reads `data-delete-url` and `data-record-name` from the trigger button, sets the modal form action and confirmation text
- All delete buttons carry: `data-bs-toggle="modal"`, `data-bs-target="#deleteModal"`, `data-delete-url="{{ url_for(...) }}"`, `data-record-name="{{ ... }}"`

**`alert.html`**
- `info_alert(message)` — blue info banner (used for active search indication)
- `warning_alert(message)` — yellow warning banner (used for no-available-bikes warning on Sale form)

**`pagination.html`**
- `pagination_controls(pagination, endpoint, search_query)` — renders "Showing X to Y of Z" + page links
- Only rendered when `pagination.total_pages > 1`

### 6.3 JavaScript (`admin.js`)

Key blocks (all inside single `DOMContentLoaded` listener):

1. **Delete modal:** `deleteModal.addEventListener('show.bs.modal', ...)` — reads `data-delete-url` and `data-record-name` from the button that triggered the modal, sets `deleteModalForm.action`.

2. **Sidebar mobile toggle:** Button with class `.sidebar-toggle` shows/hides sidebar with `.sidebar-open` class. Dark overlay closes sidebar on click.

3. **Receive form mode toggle (Purchase Orders):** `modeExisting` / `modeNew` radio buttons toggle visibility of `#section-existing` / `#section-new` and active class on mode labels. `applyReceiveMode(mode)` function.

4. **Payment reference type toggle (Payments Create):** `refTypeSale` / `refTypeAppt` radio buttons toggle visibility of `#section-sale` / `#section-appt`. Note: the balance panel loading and Sale auto-fill JS live in the Payment `form.html` template `{% block scripts %}`, not here.

### 6.4 CSS Key Classes

| Class | Purpose |
|---|---|
| `.admin-card` | Main content cards (list tables, view sections) |
| `.form-card` | Form section cards |
| `.form-section-title` | Section label inside form cards |
| `.page-header` | Page title + action button row |
| `.record-count-badge` | Orange count badge next to titles |
| `.btn-accent` | Orange primary button |
| `.action-btn-group` | Wrapper for Edit/Delete button pairs |
| `.role-badge` | Orange label badge (reused for Model, Bike labels) |
| `.po-status-badge` | PO status: `.po-status-pending`, `...-received`, etc. |
| `.appt-type-badge` | Appointment type badge: `.appt-type-service`, etc. |
| `.appt-status-badge` | Appointment status badge: `.appt-status-completed`, etc. |
| `.pay-type-badge` | Payment type badge: `.pay-type-full-payment`, etc. |
| `.payment-ref-type-badge` | Sale/Appointment reference indicator in Payment list |
| `.bike-status-badge` | `.bike-status-available` (green), `.bike-status-sold` (grey) |
| `.po-status-ordered` | Grey badge for PO item Ordered status |
| `.receive-mode-option` | Two-card radio selector (PO receive + Payment reference) |
| `.stock-zero` | Red text for zero-QOH stock rows |

---

## 7. Business Logic — Current Implementation

### 7.1 Sale ↔ New MotorBike Status

`_set_bike_status(nb_id, status)` in `sale/routes.py`:
- **Create Sale:** After successful insert → `_set_bike_status(nb_id, 'Sold')`
- **Edit Sale (bike unchanged):** No status update
- **Edit Sale (bike changed):** `_set_bike_status(old_nb_id, 'Available')` then `_set_bike_status(new_nb_id, 'Sold')`
- **Delete Sale:** Before/after delete → `_set_bike_status(nb_id, 'Available')`

Database constraint `Sale_unique_bike` (UNIQUE on `New_MotorBike_NB_ID`) is the database-level backstop guaranteeing one bike cannot be linked to two Sales.

### 7.2 Payment Balance Logic

**Remaining = Total − SUM(existing payments)**

For Sales:
- Total = `Sale.TotalAmount`
- Paid = `_get_sale_total_paid(sale_id, exclude_payment_id=current_payment_id)`
- Remaining = `max(0.0, total - paid)`
- Overpayment blocked server-side in `_validate_form()`
- Sale disappears from dropdown when `remaining <= 0.001`

For Appointments:
- Total = `_get_appointment_total(appt_id)` (live calculation from services + stock)
- Paid = `_get_appointment_total_paid(appt_id, exclude_payment_id=current_payment_id)`
- Remaining = `max(0.0, total - paid)`
- Same overpayment block and dropdown filter as Sales

**The 0.001 tolerance** absorbs floating-point rounding — does not permit genuine overpayment.

### 7.3 Appointment Completion and Stock Deduction

`_deduct_stock_for_appointment(appt_id)`:
- Queries all `Appointment_Stock` rows for the appointment
- For each row, fetches current `Stock.QOH`
- Updates `Stock.QOH = max(0, current_qoh - qty_used)` (floor at 0)
- Called inside `edit()` guard: `if status_value == 'Completed' and previous_status != 'Completed'`
- `previous_status` is the database state before the POST, stored in `record.get('Status')` before `form_data` is overwritten

### 7.4 Customer / Customer Bike Duplication

**Customer:** `NIC` and `PhoneNumber` are UNIQUE in the database. Application catches the UNIQUE violation exception (string-matches `'duplicate'` or `'unique'` in exception message) and shows a user-friendly error.

**Customer Bike:** `VIN` and `RegistrationNumber` are UNIQUE. Same exception handling pattern.

**Ownership transfer:** Not a special code path — uses the normal Edit form to change `Customer_CustomerID` on the existing `Customer_bike` record. The UNIQUE constraints on VIN/RegistrationNumber enforce that no duplicate record can be inserted instead.

### 7.5 Purchase Order Receiving

Two paths in `receive_item(po_id, item_id)`:
- **Path A (`recv_mode == 'existing'`):** `Stock.QOH += qty_recv` on selected existing Stock row
- **Path B (`recv_mode == 'new'`):** Insert new Stock row with `QOH = qty_recv`, get the new `Stock_ID`
- Both paths: Update `POItem` with `Stock_Stock_ID`, `Quantity_Received`, `DateReceived`, `Status = 'Received'`
- Then: `_auto_update_po_status(po_id)` recalculates PO-level Status

Once a POItem reaches `Status = 'Received'`, it cannot be edited or deleted.

### 7.6 Compatibility and Year Ranges

`Compatibility` bridge table links `Stock` ↔ `Model` with optional `Year_From`/`Year_To`. The UNIQUE constraint `(Stock_Stock_ID, Model_Model_No, Year_From, Year_To)` prevents exact duplicates. NULL years are not treated as equal by PostgreSQL's UNIQUE constraint, so two rows with the same Stock/Model but both years NULL could theoretically be inserted — this is an accepted edge case.

---

## 8. Authentication and Security

### 8.1 Login Flow

1. User submits email + password to `POST /auth/login`
2. Route calls `supabase.auth.sign_in_with_password({'email': email, 'password': password})`
3. On success: stores `access_token`, `refresh_token`, `user_email` in Flask `session`
4. Redirects to `/dashboard`
5. On failure: re-renders login with error message

### 8.2 Protected Routes

Every route (except login/logout) is decorated with `@login_required`:

```python
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        access_token  = session.get('access_token')
        refresh_token = session.get('refresh_token', '')
        if not access_token:
            return redirect(url_for('auth.login'))
        try:
            supabase.auth.set_session(access_token, refresh_token)
            user_response = supabase.auth.get_user(access_token)
            if not user_response or not user_response.user:
                raise Exception('Session invalid or expired.')
        except Exception:
            session.clear()
            flash('Your session has expired. Please sign in again.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
```

`set_session()` is called on every protected request — this restores the Supabase JWT so that subsequent database calls on that request execute as the authenticated user, allowing the audit trigger's `auth.uid()` to resolve the real user's email.

### 8.3 Two-Layer Security

1. **Application layer:** `@login_required` blocks unauthenticated browser requests
2. **Database layer:** RLS policies block any database query without a valid authenticated JWT

Both layers must pass independently. A bug in application code cannot bypass the database.

### 8.4 Audit Trigger

`set_audit_fields()` is a shared PostgreSQL function attached via `BEFORE INSERT OR UPDATE` triggers to every substantive table. On INSERT: sets `Date_Created = NOW()` and `Created_By = email of auth.uid()`. On UPDATE: preserves `Date_Created`/`Created_By`, sets `Date_Updated = NOW()` and `Updated_By = email of auth.uid()`. Falls back to `'system'` if no authenticated session (e.g. SQL Editor). Function is `SECURITY DEFINER`.

**Application code never sets audit fields** — they are always populated by the trigger.

---

## 9. Significant Fixes and Fragile Areas

These are the non-obvious things that were fixed during development. Future changes near these areas should be careful.

### 9.1 Flask Duplicate Route Registration (`payment.sale_info`)

**What happened:** If `app/modules/payment/__init__.py` ever contains anything beyond the 4-line Blueprint setup + import, the `sale_info` route gets registered twice and Flask crashes with `AssertionError: View function mapping is overwriting an existing endpoint function`.

**Current state:** `__init__.py` contains only: Blueprint creation, import of routes. Nothing else.

**If this happens again:** `Ctrl+Shift+F` search for `def sale_info` — must return exactly one match. Search for `Blueprint('payment'` — must return exactly one match.

### 9.2 Jinja TemplateSyntaxError in Appointment View

**What happened:** Adding a new section to `appointment/view.html` after the `{% endblock %}` that closes `{% block content %}` causes Jinja to see a dangling `{% endblock %}` and crash.

**Current state:** `appointment/view.html` has exactly one `{% endblock %}` at the very end of the file. All sections (Services, Stock, Cost Summary, Payment) are inside `{% block content %}`. `{{ delete_modal() }}` is the last thing before `{% endblock %}`.

**If this happens again:** Check block structure from `{% extends %}` to the final `{% endblock %}`. Count `{% block %}` vs `{% endblock %}` occurrences.

### 9.3 Payment Duplicate-Submission Token

**What it protects against:** Rapid repeated clicks of "Confirm Payment" creating multiple Payment rows.

**How it works:** GET request generates a UUID token stored in Flask session AND embedded as `<input type="hidden" name="form_token">` in the form. POST checks token matches session value and consumes it immediately. If no session token exists (expired session), the check is skipped — backend balance validation still protects data integrity.

**Fragile scenario:** If the hidden field is ever accidentally removed from `form.html`, the token will never be submitted, the session check will be skipped, and the protection degrades to client-side only. The hidden input must always be present inside the `<form>` tag on Create (not Edit).

### 9.4 Appointment Stock Deduction Guard

**The guard:** `if status_value == 'Completed' and previous_status != 'Completed'`

`previous_status = record.get('Status')` must be captured from `record` (the database state fetched at the start of `edit()`, before `form_data = request.form.to_dict()` overwrites `form_data`). If `record` were used after `form_data` overwrite, the guard would break.

### 9.5 Payment Reference Type Locking on Edit

On Edit, `locked_ref_type` is determined from the existing record (`'appointment' if current_appt_id else 'sale'`) and passed to `_validate_form()` as `locked_ref_type`. The form renders a hidden input carrying this value instead of the radio buttons. This ensures the reference type can never be changed via an Edit submission, even by crafting a manual POST.

### 9.6 Appointment Payment Constraint Migration

The `UNIQUE ("Appointment_AppointmentID")` constraint on the Payment table was dropped to allow multiple payments per appointment. Without this migration, any second payment attempt for the same appointment fails at the database level regardless of application code. SQL to verify it's been dropped:

```sql
SELECT conname FROM pg_constraint
WHERE conrelid = '"Payment"'::regclass AND contype = 'u';
```
`unique_appointment_payment` must NOT appear in the results.

### 9.7 Sidebar Scrolling

`admin.css` `.sidebar` uses `height: 100vh` (not `min-height`). With `overflow-y: auto` also set, this clips the sidebar at viewport height and enables scrolling. If `min-height` is used instead, the sidebar grows beyond the viewport and overflow-y never activates.

### 9.8 Time Field Pre-population

Supabase returns `TIME` column values as `"HH:MM:SS"` strings. `<input type="time">` requires `"HH:MM"`. The `edit()` route in `appointment/routes.py` truncates: `form_data['Appointment_time'] = _truncate_time(form_data.get('Appointment_time', ''))` before rendering the template. Missing this causes the time field to appear empty on Edit.

### 9.9 Sale Dropdown on Edit (Bike Dropdown Asymmetry)

The Create form's bike dropdown shows only Available bikes. The Edit form must also show the currently-linked bike (which is Sold). If the `_get_form_options(current_nb_id=original_nb_id)` call doesn't include the current bike, the Edit form's dropdown appears blank for the current selection — appearing as if the bike has been de-selected.

### 9.10 Payment Type Duplication in List (Fixed)

`payment/list.html` previously had both a "Type" column (badge) and a "Payment Type" column (plain text) showing the same `row.PaymentType` value. The "Payment Type" column and its `<td>` were removed. Only the `pay-type-badge` in the "Type" column remains.

### 9.11 PO_NewMotorBike — Duplicate-Error Misattribution and PO Status Not Auto-Updated (Open, Not Yet Fixed)

Two items were flagged during review of the `PO_NewMotorBike` addition (Section 3.12) and are not yet resolved:

- In `add_motorbike()`'s "New Motorcycle Record" path, the `New_MotorBike` insert and the `PO_NewMotorBike` insert share one `try/except`. A VIN-uniqueness violation on the `New_MotorBike` insert is currently caught and reported as `"This motorcycle is already linked to another purchase order"` — the wrong field and the wrong message. Fix: split the two inserts into separate `try/except` blocks so each failure maps to the correct error (`errors['VIN']` vs `errors['New_MotorBike_NB_ID']`).
- Adding, editing, or deleting a `PO_NewMotorBike` row never calls anything equivalent to `_auto_update_po_status()` (Section 3.12), so a PO's `Status` field can remain `'Pending'` even after every motorcycle on it has been received. Whether motorbike rows should feed into the same status calculation as `PurchaseOrderItem` rows — and how, given motorbikes have no Ordered/Received split — is an open design decision for the next review pass, not yet implemented either way.

---

## 10. Client Side Integration Points

This section documents what the future Client Side (customer-facing portal or booking system) will need to interact with from the existing system.

### 10.1 Directly Relevant Database Tables

| Table | What Client Side needs | Notes |
|---|---|---|
| `Customer` | Register/lookup customers | `NIC` and `PhoneNumber` are UNIQUE — no duplicate customer records. Client Side must handle this gracefully. |
| `Customer_bike` | Customer's registered vehicles | `VIN` and `RegistrationNumber` UNIQUE. Ownership transfer is an edit, not a new record. |
| `New_MotorBike` | Display available motorbikes for purchase | Filter on `Status = 'Available'`. Sold bikes have `Status = 'Sold'`. |
| `Appointment` | Book appointments | References `Customer_bike.BikeID` (not Customer directly). Customers need a registered bike before booking. |
| `appointment_service` | Select services for appointment | References `Service.ServiceID`. |
| `Service` | Display available services + prices | `Cost` is the customer-facing price. |
| `Spare_Parts` + `Stock` | Browse or display available parts | `Stock.QOH > 0` for in-stock filtering. `S_Price` is the selling price. |
| `Compatibility` | Show which parts fit which models | Bridge between `Stock` and `Model` with optional `Year_From`/`Year_To`. |
| `Model` + `Brand` | Display motorbike models | Used in `New_MotorBike`, `Customer_bike`, `Compatibility`. |
| `Color` | Display color options for motorbikes | String PK. |
| `Sale` | Record a motorbike purchase | Must check `New_MotorBike.Status = 'Available'` before allowing purchase. |
| `Payment` | Record payments | Both Sale and Appointment payments are supported. Balance logic must be respected. |

### 10.2 Business Rules the Client Side Must Respect

**Customer registration:**
- `NIC` must be unique across all Customers
- `PhoneNumber` must be unique across all Customers
- A duplicate creates a 409/constraint violation — the Client Side should check before inserting or present a "customer already exists" flow

**Bike registration:**
- A customer must exist before a Customer Bike can be created
- `VIN` and `RegistrationNumber` must be unique
- A bike linked to appointments cannot be deleted — the Client Side should handle this

**Appointment booking:**
- Must reference a `Customer_bike.BikeID` (not CustomerID directly)
- `Employee_EmployeeID` is required in the current schema — the Client Side may need to auto-assign or allow the admin panel to assign post-booking
- `AppointmentType` must be one of: Service, Repair, Inspection, Other
- `Status` will likely be set to `'Pending'` on client-side booking
- Time slots are not managed by the current Admin Panel — no time-slot availability table exists. The Client Side would need to implement this independently (or against `Appointment_Date` + `Appointment_time` values).

**Motorbike purchase (Sale):**
- Only `New_MotorBike` records with `Status = 'Available'` can be sold
- Creating a Sale sets the bike to `Sold` — this is done by the Admin Panel's `_set_bike_status()`. The Client Side must either call the same logic or trigger the Admin Panel workflow
- `Sale_unique_bike` constraint means only one Sale per bike — attempting to insert a second sale for the same bike fails at the database level

**Payments:**
- `Payment_requires_reference` CHECK: every Payment must reference either a Sale or an Appointment
- `unique_appointment_payment` constraint has been **dropped** — multiple payments per Appointment are allowed (partial/deposit flow)
- Sale payments: multiple payments allowed until `SUM(AmountPaid) >= Sale.TotalAmount`
- Appointment payments: multiple payments allowed until `SUM(AmountPaid) >= appt_total` (dynamically calculated)
- Overpayment must be blocked by the Client Side as well, not only by the Admin Panel

**Stock:**
- `Stock.QOH` is decremented when an Appointment is marked `Completed` (done by the Admin Panel `_deduct_stock_for_appointment()`)
- The Client Side should not directly modify `Stock.QOH` — stock deduction is a result of appointment completion handled by the Admin Panel

### 10.3 What the Admin Panel Already Handles

The following are implemented in the Admin Panel and do NOT need to be reimplemented in the Client Side:

- All master data management (Colors, Categories, Brands, Models, Services, Roles, Employees, Suppliers)
- Spare Parts catalogue and Stock inventory management
- Stock-model compatibility management
- Purchase Order creation and stock receiving
- Appointment service and stock usage recording
- Appointment cost calculation
- Stock deduction on appointment completion
- Sale → bike status synchronisation
- Payment balance calculation and overpayment protection
- Audit fields on all records

### 10.4 What the Client Side Will Need to Implement

- Customer self-registration / account management
- Customer authentication (separate from the Admin Panel's Supabase Auth, or via a different Auth scheme)
- Browse available New MotorBikes (filter `Status = 'Available'`)
- Browse compatible spare parts (using `Compatibility` table + `Stock.QOH > 0`)
- Appointment booking (create `Appointment` record with Status = Pending)
- Time-slot availability (not in the current database — needs design)
- Payment initiation and tracking (respecting balance rules)
- Customer view of their appointments and payment history

### 10.5 Shared Database, Separate Applications

The Admin Panel and Client Side share the same Supabase PostgreSQL database. RLS policies currently grant access only to the `authenticated` role (Supabase Auth users). The Client Side will likely need:

- Separate RLS policies that allow customers to read only their own records
- Or a service-role API layer that the Client Side calls, which enforces row-level access in application code
- A decision on whether customers use Supabase Auth (same project, different role/policy) or a separate authentication system

**This architectural decision has not been made yet for the Client Side and should be discussed with the supervisor before implementation begins.**

---

## 11. Quick Reference

### Start the server

```powershell
# In Windows PowerShell, from the motorbike-admin/ directory
.\venv\Scripts\Activate
py run.py
```

### URL map

| Section | URL Prefix |
|---|---|
| Root | `/` → redirects to `/dashboard` |
| Auth | `/auth/login`, `/auth/logout` |
| Dashboard | `/dashboard` |
| Colors | `/colors` |
| Categories | `/categories` |
| Brands | `/brands` |
| Models | `/models` |
| Spare Parts | `/spare-parts` |
| Stock | `/stock` |
| Services | `/services` |
| Roles | `/roles` |
| Employees | `/employees` |
| Suppliers | `/suppliers` |
| Compatibility | `/compatibility` |
| Purchase Orders | `/purchase-orders` |
| Customers | `/customers` |
| Customer Bikes | `/customer-bikes` |
| New Motorbikes | `/new-motorbikes` |
| Appointments | `/appointments` |
| Sales | `/sales` |
| Payments | `/payments` |

### Key JSON endpoints (for client-side AJAX if needed)

- `GET /payments/sale-info/<sale_id>?exclude_payment_id=<id>` → `{sale_date, total_amount, total_paid, remaining}`
- `GET /payments/appointment-info/<appt_id>?exclude_payment_id=<id>` → `{total_amount, total_paid, remaining}`

Both require authenticated session (protected by `@login_required`).

---

*End of Admin Panel Codebase Context — current as of Task 26 + all post-Task-26 fixes including Payment balance logic, Appointment partial payment support, stock deduction, and duplicate submission protection.*
