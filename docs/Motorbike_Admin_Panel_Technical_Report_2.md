# Motorbike Sales and Servicing Management System
## Admin Panel — Technical Report and Documentation

**Final Year Project**
**University of Technology, Mauritius (UTM)**
**BSc (Hons) Software Engineering**

**Prepared by:** Utsav Ramjattan
**Module Type:** Final Year Project — System Development
**Report Scope:** Admin Panel (Phase 1 through Phase 3 CRUD, Authentication, Payment and Appointment business logic)

---

`[INSERT IMAGE HERE — Project Title / Cover Page Graphic]`
*A cover graphic or the university's official cover page template, featuring the project title, student name, supervisor name, and submission date.*

---

## Table of Contents

1. Introduction
2. Objectives
3. Project Scope
4. Technology Stack
   4.1 Backend — Python and Flask
   4.2 Database — Supabase / PostgreSQL
   4.3 Frontend — Jinja2, Bootstrap 5, JavaScript
   4.4 Development Environment and Tools
5. System Architecture
   5.1 High-Level Architecture
   5.2 Project / Folder Structure
   5.3 Application Factory and Blueprint Pattern
6. Database Design
   6.1 Entity-Relationship Overview
   6.2 Phase 1 Tables (Reference / Master Data)
   6.3 Compatibility Table (Supervisor-Revised Design)
   6.4 Purchase Order and Purchase Order Item
   6.5 Phase 3 Tables (Transactional Data)
   6.6 Audit Fields and Triggers
   6.7 Row Level Security (RLS) and Grants
   6.8 Constraints, Uniqueness, and Data Integrity Rules
   6.9 Database Evolution — Changes Made During Development
   6.10 PO_NewMotorBike — Motorcycle Purchase Ordering Bridge (Post-Task 26 Addition)
7. Authentication and Security
   7.1 Supabase Auth Integration
   7.2 Session Management
   7.3 Protected Routes
   7.4 RLS and Application-Level Security Together
8. Admin Panel Modules
   8.1 Color
   8.2 Category
   8.3 Role
   8.4 Supplier
   8.5 Brand
   8.6 Service
   8.7 Employee
   8.8 Model
   8.9 Spare Parts
   8.10 Stock
   8.11 Compatibility
   8.12 Purchase Order and Purchase Order Item
   8.13 Customer
   8.14 Customer Bike
   8.15 New Motorbike
   8.16 Appointment (with Services and Stock Used)
   8.17 Sale
   8.18 Payment
   8.19 PO_NewMotorBike (Motorcycle Purchase Ordering)
9. UI / UX Design
   9.1 Layout and Visual Identity
   9.2 Sidebar and Navigation
   9.3 Dashboard
   9.4 Shared Components
   9.5 Responsive and Scrolling Behaviour
   9.6 Design Evolution
10. Business Logic
    10.1 Sale ↔ New Motorbike Status Linkage
    10.2 Payment Rules (Sale and Appointment)
    10.3 Appointment Completion and Stock Deduction
    10.4 Customer / Customer Bike Duplication Prevention and Ownership Transfer
    10.5 Purchase Order Receiving Workflow
    10.6 Stock ↔ Model Compatibility
11. Development History (Chronological)
12. Errors, Problems, and Solutions
13. Important Code Explained
14. Testing
15. Final System State
16. Conclusion
17. Appendices

---

## 1. Introduction

The Motorbike Sales and Servicing Management System is a Final Year Project developed for a Mauritian motorbike dealership. The system is designed to computerise the dealership's core operations, which previously would have relied on manual or fragmented record-keeping: managing spare parts inventory, motorbike stock, customer records, vehicle registrations, service appointments, motorbike sales, and payments.

This report documents the **Admin Panel** component of the system — the internal, authenticated web application used by dealership staff to manage all data in the system. The Admin Panel is built with Python (Flask) on the backend and Supabase (PostgreSQL) as the database and authentication provider, with Jinja2 templates, Bootstrap 5, and vanilla JavaScript on the frontend.

The original relational design was first modelled in Oracle SQL Developer Data Modeler, producing an Oracle-flavoured DDL export. Because the actual implementation target was Supabase (PostgreSQL), that DDL had to be converted, corrected, and in several cases restructured based on supervisor feedback before implementation could begin. This conversion process, and the subsequent revisions requested by the project supervisor, form an important part of the project's development history and are documented in detail in this report.

The system was developed incrementally, table by table and module by module, following a strict task-based workflow in which each Admin Panel module (Color, Category, Brand, Model, Spare Parts, Stock, Service, Role, Employee, Supplier, Compatibility, Purchase Order, Customer, Customer Bike, New Motorbike, Appointment, Sale, and Payment) was implemented, tested, and confirmed working before the next module was started. This report follows that same chronology.

`[INSERT IMAGE HERE — Admin Panel Login Screen]`
*Screenshot of the Admin Panel login page, showing the MotoAdmin branding, email/password form, and the dark navy background.*

---

## 2. Objectives

The objectives of the Admin Panel, as implemented, are to:

1. Provide dealership staff with a single, authenticated web interface to manage all core business data.
2. Digitise and enforce the dealership's master/reference data (colors, categories, brands, models, services, roles, employees, suppliers) with full CRUD (Create, Read, Update, Delete) functionality.
3. Manage a spare parts catalogue (Spare Parts) separately from its physical inventory variants (Stock), reflecting the real business distinction between "what a part is" and "which specific stocked version of it exists."
4. Track which spare part/stock variants are compatible with which motorbike models, including model year ranges, via a dedicated Compatibility bridge table — a design requested directly by the project supervisor after reviewing the original ERD.
5. Support supplier purchase ordering with a two-path receiving workflow: updating existing stock quantities, or creating new stock records, depending on whether a matching stock variant already exists.
6. Manage customer records and their registered motorbikes (Customer Bikes), including protection against duplicate customers and duplicate vehicle records, and support for ownership transfer when a bike changes hands.
7. Manage new motorbike inventory available for sale, automatically reflecting each unit's sale status (Available / Sold).
8. Record motorbike sales, automatically linking a sale to a specific in-stock motorbike and updating that motorbike's availability status.
9. Manage service and repair appointments, including the specific services performed and spare parts/stock consumed during each appointment, with an automatically calculated estimated cost.
10. Record and validate payments against both sales and appointments, correctly supporting full payments, partial payments/deposits, and multiple instalments up to (but never exceeding) the total amount owed.
11. Automatically deduct consumed stock quantities from inventory once an appointment is marked Completed.
12. Secure the entire Admin Panel behind Supabase Authentication and PostgreSQL Row Level Security (RLS), ensuring that only authenticated staff can read or write any data, and that every record change is attributed to the real staff member who made it via audit fields.

---

## 3. Project Scope

**In scope (implemented and documented in this report):**
- All 10 Phase 1 "master data" tables: Color, Category, Brand, Model, Spare_Parts, Stock, Service, Role, Employee, Supplier.
- The Compatibility table (a supervisor-requested addition connecting Stock and Model).
- PurchaseOrder and PurchaseOrderItem (order creation and the two-path stock-receiving workflow).
- Phase 3 transactional tables: Customer, Customer_bike, New_MotorBike, Appointment (with its `appointment_service` and `Appointment_Stock` bridge tables), Sale, and Payment.
- Full Supabase Authentication, session handling, and PostgreSQL RLS policies across all tables.
- A single unified Flask Admin Panel with a consistent sidebar, dashboard, and CRUD pattern across every module.

**Explicitly out of scope for this report / not yet implemented at the time of writing:**
- Customer-facing storefront or booking portal (the system described here is staff-only).
- Selling spare parts directly to customers as a first-class transaction type (raised as a discussion point during development but not implemented — see Section 12 and the Development History).
- Formal automated test suite (unit/integration tests) — testing performed was manual, structured, and is documented in Section 14.
- Reporting/analytics dashboards beyond the basic dashboard record-count cards.

---

## 4. Technology Stack

### 4.1 Backend — Python and Flask

**Language:** Python was selected as the backend language specifically because the developer had no prior programming experience, and Python (paired with the Flask framework) was assessed as the most beginner-accessible option compared to alternatives such as PHP. This decision was made and documented at the Initial Study stage of the project, prior to the work covered in this report, and is recorded here because it directly shaped every architectural decision that followed (for example, the choice not to introduce a JavaScript-heavy frontend framework such as React later in the project, when that option was considered and explicitly rejected — see Section 11).

**Framework:** Flask (a lightweight Python micro-framework) was used for:
- Routing (`@bp.route(...)`) — every module (Color, Customer, Sale, Payment, etc.) is implemented as its own Flask **Blueprint**, registered in the application factory.
- Server-side rendering via Jinja2 templates.
- Session management (`flask.session`) — used both for authentication state and for CSRF-style duplicate-submission protection tokens (see Section 12).
- Flash messaging (`flask.flash`) for user feedback after Create/Update/Delete operations.

No additional Flask extensions (Flask-Login, Flask-WTF, Flask-SQLAlchemy) were introduced. Authentication was handled directly through the Supabase Python client and Flask's built-in session, and form validation was written by hand in each route rather than through a forms library. This was a deliberate simplicity decision to keep the codebase small and fully understood by the developer.

**Supabase Python client (`supabase-py`):** used throughout as the sole means of talking to the database — there is no ORM (e.g. SQLAlchemy) layer. All queries are written using the Supabase client's query-builder syntax, for example:

```python
result = (
    supabase.table('Employee')
    .select('*')
    .order('LastName')
    .execute()
)
```

### 4.2 Database — Supabase / PostgreSQL

**Why Supabase:** Supabase was chosen over a traditional self-hosted MySQL/phpMyAdmin setup (which had been the original Initial Study plan) partway through the project, after the developer proposed the change and it was discussed and agreed upon. The reasoning included:
- Supabase provides a hosted PostgreSQL database with zero local server setup (no XAMPP/phpMyAdmin required).
- Built-in **Authentication** (Supabase Auth) — removing the need for a separate auth system or third-party provider such as Clerk (which was evaluated and explicitly rejected — see Section 11).
- Built-in **Row Level Security (RLS)**, a native PostgreSQL feature exposed cleanly through Supabase's dashboard and SQL editor.
- A Table Editor GUI for quick inspection and manual data entry during testing.
- Auto-generated REST access via PostgREST, accessed through the `supabase-py` client library.

**Trade-off acknowledged:** Because the original ERD/DDL was authored in Oracle SQL Developer Data Modeler, every table had to be manually converted from Oracle syntax (`NUMBER`, `NVARCHAR2`, Oracle `DATE`, sequence-based IDs) to PostgreSQL-correct syntax (`INTEGER`/`NUMERIC`, `VARCHAR`, `TIMESTAMPTZ`/`DATE`/`TIME`, `GENERATED ALWAYS AS IDENTITY`). This conversion process surfaced multiple genuine design errors in the original Oracle export (see Section 6.9 and Section 12).

### 4.3 Frontend — Jinja2, Bootstrap 5, JavaScript

- **Jinja2** (Flask's default template engine) is used exclusively for server-side rendering. A layout inheritance pattern (`{% extends %}`) with a base layout (`layout/base.html`) and an admin shell (`layout/admin_layout.html`) is used across all modules.
- **Reusable Jinja macros** were built early (Task 06) for shared UI elements — a data table with search, form fields (text/number/select/textarea/date/time/readonly), a delete-confirmation modal, alert banners, and pagination controls — and reused without duplication across all 18 modules.
- **Bootstrap 5.3** (loaded via CDN) supplies the grid system, form control base styles, and modal/alert component behaviour, with the Admin Panel then layering a custom design system on top via a single `admin.css` file (see Section 9).
- **Font Awesome 6.5** (via CDN) supplies all iconography throughout the sidebar, buttons, and status badges.
- **Vanilla JavaScript** (no framework) is used for all client-side interactivity: sidebar toggle behaviour, delete-modal population, receive-form mode toggling (Purchase Orders), Sale price auto-fill, and the dynamic Payment balance panel that fetches live remaining-balance data via `fetch()` calls to small JSON endpoints exposed by the Flask backend.

### 4.4 Development Environment and Tools

- **Code editor:** Visual Studio Code, used alongside Antigravity (an AI-assisted coding tool) for implementation of the generated task specifications.
- **Version control / local environment:** a Python virtual environment (`venv`), activated via PowerShell on Windows (`.\venv\Scripts\Activate`), with the app run via `py run.py`.
- **Database administration:** the Supabase web dashboard — specifically the SQL Editor (for running all DDL and migration scripts) and the Table Editor (for manual inspection and test-data entry).
- **Operating system:** Windows, with PowerShell as the primary terminal.

`[INSERT IMAGE HERE — Development Environment Screenshot]`
*VS Code / Antigravity working on the project, or the Supabase dashboard SQL Editor mid-script.*

---

## 5. System Architecture

### 5.1 High-Level Architecture

```
                    ┌─────────────────────────┐
                    │   Browser (Admin User)   │
                    └────────────┬────────────┘
                                 │ HTTPS
                                 ▼
                    ┌─────────────────────────┐
                    │   Flask Application      │
                    │  (Blueprints per module)  │
                    │                           │
                    │  - Routes (routes.py)     │
                    │  - Jinja2 Templates       │
                    │  - Session (Flask)        │
                    └────────────┬────────────┘
                                 │ supabase-py client
                                 ▼
                    ┌─────────────────────────┐
                    │        Supabase           │
                    │  - PostgreSQL Database    │
                    │  - Supabase Auth          │
                    │  - Row Level Security     │
                    │  - Audit Triggers         │
                    └─────────────────────────┘
```

`[INSERT IMAGE HERE — System Architecture Diagram]`
*A clean architecture diagram showing Browser → Flask (Blueprints) → Supabase (Postgres + Auth + RLS), matching the ASCII diagram above but polished for the report.*

There is no separate frontend framework and no client-side single-page-application layer: every page is fully server-rendered by Flask/Jinja2 on each request, and the browser receives complete HTML. The only client-side data fetching used is a small number of targeted `fetch()` calls to JSON endpoints (for example `/payments/sale-info/<id>` and `/payments/appointment-info/<id>`) used purely to populate a live balance panel without a full page reload.

### 5.2 Project / Folder Structure

The final folder structure of the Flask application (`motorbike-admin/`) is:

```
motorbike-admin/
├── run.py                        # Entry point — starts the Flask app
├── config.py                     # App config (secret key, debug mode, env loading)
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables (Supabase URL/key) — never committed
├── .gitignore
│
├── docs/                          # Living project documentation
│   ├── functionalities.md
│   └── requirements.md
│
└── app/
    ├── __init__.py                # Application factory — creates app, registers all Blueprints
    ├── supabase_client.py         # Shared Supabase client instance
    │
    ├── auth/                      # Authentication module
    │   ├── routes.py               # /login, /logout
    │   └── decorators.py           # @login_required route protection
    │
    ├── dashboard/                 # Dashboard module (record-count cards)
    │   └── routes.py
    │
    ├── modules/                   # One sub-folder per business entity/module
    │   ├── color/
    │   ├── category/
    │   ├── brand/
    │   ├── model/
    │   ├── spare_parts/
    │   ├── stock/
    │   ├── service/
    │   ├── role/
    │   ├── employee/
    │   ├── supplier/
    │   ├── compatibility/
    │   ├── purchase_order/
    │   ├── customer/
    │   ├── customer_bike/
    │   ├── new_motorbike/
    │   ├── appointment/
    │   ├── sale/
    │   └── payment/
    │       (each folder: __init__.py [Blueprint] + routes.py)
    │
    ├── utils/                     # Shared utility functions
    │   ├── validators.py           # required_fields, is_positive_number,
    │   │                            #   is_positive_integer, is_valid_email
    │   ├── pagination.py           # paginate() helper
    │   └── flash_messages.py       # flash_success/error/warning/info
    │
    ├── static/
    │   ├── css/admin.css           # Single growing stylesheet for the whole panel
    │   └── js/admin.js             # Single growing script file for the whole panel
    │
    └── templates/
        ├── layout/
        │   ├── base.html            # <head>, CDN links, {% block body %}
        │   └── admin_layout.html    # Sidebar + header + flash + content + footer
        ├── auth/
        │   └── login.html
        ├── dashboard/
        │   └── index.html
        ├── components/              # Reusable Jinja macros (Task 06)
        │   ├── table.html            # search_bar(), data_table()
        │   ├── form_field.html       # text_field, number_field, select_field,
        │   │                          #  textarea_field, readonly_field, date_field,
        │   │                          #  time_field
        │   ├── modal_confirm.html    # delete_modal()
        │   ├── alert.html            # info_alert(), warning_alert()
        │   └── pagination.html       # pagination_controls()
        └── modules/
            (one sub-folder per module, mirroring app/modules/,
             each with list.html + form.html, and view.html /
             item_form.html / service_form.html / stock_form.html /
             receive_form.html where the module requires them)
```

`[INSERT IMAGE HERE — Folder Structure Screenshot]`
*A VS Code Explorer panel screenshot showing the full `app/` tree expanded, corresponding to the structure above.*

### 5.3 Application Factory and Blueprint Pattern

The Flask application is constructed using the **application factory pattern**: `app/__init__.py` defines `create_app()`, which creates the Flask instance, loads configuration, and registers one Blueprint per module with its own URL prefix. `run.py` simply calls this factory:

```python
# run.py
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run()
```

```python
# app/__init__.py (excerpt — final state after all 26 tasks)
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    from app.modules.color import bp as color_bp
    app.register_blueprint(color_bp, url_prefix='/colors')
    # ... one such block per module ...

    from app.modules.payment import bp as payment_bp
    app.register_blueprint(payment_bp, url_prefix='/payments')

    @app.route('/')
    def index():
        return redirect(url_for('dashboard.index'))

    return app
```

Each module Blueprint follows an identical two-file pattern:

```python
# app/modules/<module>/__init__.py
from flask import Blueprint

bp = Blueprint('<module_name>', __name__)

from app.modules.<module> import routes  # noqa: E402, F401
```

This consistent pattern across 18 modules is one of the project's key architectural decisions: adding a new module never required touching any existing module's code, only adding a new folder and one new registration line in `app/__init__.py` and (where relevant) one new sidebar link.

`[INSERT IMAGE HERE — Blueprint Registration Diagram]`
*A simple diagram showing the app factory fanning out to each Blueprint module.*
## 6. Database Design

### 6.1 Entity-Relationship Overview

`[INSERT IMAGE HERE — Full Entity-Relationship Diagram (ERD)]`
*The complete, final ERD covering all Phase 1, Compatibility, Purchase Order, and Phase 3 tables, showing every foreign key relationship described below.*

The database originated from an Oracle SQL Developer Data Modeler export. It was implemented in Supabase (PostgreSQL) in three broad phases, matching the project's task structure:

- **Phase 1 — Master/reference data.** Ten tables with no dependency on customer-facing or transactional data: Color, Category, Role, Supplier, Brand, Employee, Model, Service, Spare_Parts, Stock. These were built first specifically because none of them depend on the transactional tables — they form the foundation everything else references.
- **Compatibility + Purchase Order layer.** Added after a supervisor design review identified problems in the original Spare_Parts ↔ Model relationship (see Section 6.3) and in the original Purchase Order design (see Section 6.4).
- **Phase 3 — Transactional data.** Customer, Customer_bike, New_MotorBike, Appointment (+ `appointment_service`, `Appointment_Stock`), Sale, Payment.

The dependency-first build order (master data before transactional data) was a deliberate architectural decision, confirmed explicitly during planning: transactional tables (Appointment, Sale, Payment) all have foreign keys pointing at master-data tables (Employee, Service, Model, Customer_bike, etc.), so those had to exist and be populated first, or none of the transactional CRUD screens would have any dropdown options to select from.

### 6.2 Phase 1 Tables (Reference / Master Data)

All ten Phase 1 tables share a common audit-field pattern (see Section 6.6) and were converted from the Oracle DDL with the following categories of correction:

| Oracle type | PostgreSQL/Supabase equivalent | Reason |
|---|---|---|
| `NUMBER` (ID columns) | `INTEGER GENERATED ALWAYS AS IDENTITY` | PostgreSQL native auto-increment; Oracle sequences do not exist in Postgres |
| `NUMBER(10,2)` (money) | `NUMERIC(10,2)` | Exact decimal storage for currency |
| `NVARCHAR2(n)` | `VARCHAR(n)` | Postgres has no NVARCHAR2 type |
| `DATE` (audit fields) | `TIMESTAMPTZ` | Oracle `DATE` stores date **and** time; Postgres `DATE` does not — `TIMESTAMPTZ` is the correct equivalent |

**Color** — the only Phase 1 table whose primary key is a natural string key rather than a surrogate integer:

```sql
CREATE TABLE IF NOT EXISTS "Color" (
    "Color"        VARCHAR(20)  NOT NULL,
    "Date_Created" TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"   VARCHAR(20)  NOT NULL DEFAULT 'system',
    "Date_Updated" TIMESTAMPTZ,
    "Updated_By"   VARCHAR(20),
    CONSTRAINT "Color_PK" PRIMARY KEY ("Color")
);
```

This design (the color name itself as the primary key) was preserved from the original Oracle model because no other Phase 1 table needed to reference Color via a surrogate key, and it naturally prevents duplicate color names without an additional UNIQUE constraint.

**Category, Role, Supplier, Brand, Service** all follow the standard surrogate-key pattern, e.g.:

```sql
CREATE TABLE IF NOT EXISTS "Role" (
    "Role_ID"      INTEGER      GENERATED ALWAYS AS IDENTITY,
    "Role_Name"    VARCHAR(15)  NOT NULL,
    "HourlyRate"   NUMERIC(10,2) NOT NULL,
    "Date_Created" TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"   VARCHAR(50)  NOT NULL DEFAULT 'system',
    "Date_Updated" TIMESTAMPTZ,
    "Updated_By"   VARCHAR(50),
    CONSTRAINT "Role_PK" PRIMARY KEY ("Role_ID")
);
```

**Employee** introduces the project's first self-referencing foreign key (a supervisor relationship):

```sql
CREATE TABLE IF NOT EXISTS "Employee" (
    "EmployeeID"   INTEGER     GENERATED ALWAYS AS IDENTITY,
    "FirstName"    VARCHAR(50) NOT NULL,
    "LastName"     VARCHAR(50) NOT NULL,
    "Phone"        VARCHAR(20) NOT NULL,
    "Role_Role_ID" INTEGER     NOT NULL,
    "SupervisorID" INTEGER,
    "Date_Created" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "Created_By"   VARCHAR(50) NOT NULL DEFAULT 'system',
    "Date_Updated" TIMESTAMPTZ,
    "Updated_By"   VARCHAR(50),
    CONSTRAINT "Employee_PK"   PRIMARY KEY ("EmployeeID"),
    CONSTRAINT "Employee_Role_FK" FOREIGN KEY ("Role_Role_ID")
        REFERENCES "Role" ("Role_ID"),
    CONSTRAINT "Employee_Supervisor_FK" FOREIGN KEY ("SupervisorID")
        REFERENCES "Employee" ("EmployeeID")
);
```

**Important correction made during conversion:** the original Oracle DDL contained a `SaleID` column directly on `Employee`, which was removed — this was identified as a modelling error, since `Sale` correctly references `Employee` (an employee processes a sale), not the other way around. Keeping the reverse column would have created a circular mandatory dependency that made it impossible to insert either table's first row. The `SupervisorID` self-reference, meanwhile, was present in the project's Relational diagram but *missing* from the Oracle DDL export, and was added back in during conversion.

**Model** and **Spare_Parts** and **Stock** complete Phase 1:

```sql
CREATE TABLE IF NOT EXISTS "Model" (
    "Model_No"       INTEGER     GENERATED ALWAYS AS IDENTITY,
    "Brand_Brand_ID" INTEGER    NOT NULL,
    "Description"    VARCHAR(50) NOT NULL,
    "Date_Created"   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "Created_By"     VARCHAR(20) NOT NULL DEFAULT 'system',
    "Date_Updated"   TIMESTAMPTZ,
    "Updated_By"     VARCHAR(20),
    CONSTRAINT "Model_PK"       PRIMARY KEY ("Model_No"),
    CONSTRAINT "Model_Brand_FK" FOREIGN KEY ("Brand_Brand_ID")
        REFERENCES "Brand" ("Brand_ID")
);

CREATE TABLE IF NOT EXISTS "Spare_Parts" (
    "SP_id"           INTEGER      GENERATED ALWAYS AS IDENTITY,
    "SP_name"         VARCHAR(50)  NOT NULL,
    "SP_desc"         VARCHAR(255) NOT NULL,
    "Category_CAT_ID" INTEGER      NOT NULL,
    "Model_Model_No"  INTEGER,        -- later REMOVED, see Section 6.3
    "Date_Created"    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"      VARCHAR(20)  NOT NULL DEFAULT 'system',
    "Date_Updated"    TIMESTAMPTZ,
    "Updated_By"      VARCHAR(20),
    CONSTRAINT "Spare_Parts_PK"          PRIMARY KEY ("SP_id"),
    CONSTRAINT "Spare_Parts_Category_FK" FOREIGN KEY ("Category_CAT_ID")
        REFERENCES "Category" ("CAT_ID")
);

CREATE TABLE IF NOT EXISTS "Stock" (
    "Stock_ID"          INTEGER       GENERATED ALWAYS AS IDENTITY,
    "Size"              VARCHAR(20),   -- made nullable, see Section 6.3
    "QOH"               INTEGER       NOT NULL,
    "S_Price"           NUMERIC(10,2) NOT NULL,
    "Warranty"          INTEGER       NOT NULL,
    "Spare_Parts_SP_id" INTEGER       NOT NULL,
    "Brand_Brand_ID"    INTEGER       NOT NULL,
    "Date_Created"      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"        VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated"      TIMESTAMPTZ,
    "Updated_By"        VARCHAR(20),
    CONSTRAINT "Stock_PK"            PRIMARY KEY ("Stock_ID"),
    CONSTRAINT "Stock_Spare_Parts_FK" FOREIGN KEY ("Spare_Parts_SP_id")
        REFERENCES "Spare_Parts" ("SP_id"),
    CONSTRAINT "Stock_Brand_FK"      FOREIGN KEY ("Brand_Brand_ID")
        REFERENCES "Brand" ("Brand_ID")
);
```

**Important corrections made during conversion:**
- `Spare_Parts.SP_desc` was `NVARCHAR2(1)` in the Oracle export (a Data Modeler sizing error) — corrected to `VARCHAR(255)`.
- `Spare_Parts.Updated_By` was `NUMBER(20)` in the Oracle export (wrong data type for a username string) — corrected to `VARCHAR(20)`.
- `Stock."Size"` was originally `NUMBER` in Oracle — corrected to `VARCHAR(20)` because real spare-part sizes are alphanumeric (e.g. `"90/90-17"`, `"XL"`, `"1L"`), confirmed against the project's own sample data.

### 6.3 Compatibility Table (Supervisor-Revised Design)

Partway through the project, the supervisor reviewed the ERD and identified a design problem in the direct `Spare_Parts → Model` relationship. The concern, in the supervisor's own framing (paraphrased from the project's design-review meeting): the same stock item (e.g. a specific size/brand variant of an air filter) can be compatible with **multiple** motorbike models, and that compatibility can additionally depend on the motorbike's **model year**. A single FK from `Spare_Parts` to one `Model` could not express this.

**Resolution — a new `Compatibility` bridge table**, implementing a logical `Model M:N Stock` relationship:

```sql
CREATE TABLE IF NOT EXISTS public."Compatibility" (
    "Com_ID"           INTEGER      GENERATED ALWAYS AS IDENTITY,
    "Stock_Stock_ID"   INTEGER      NOT NULL,
    "Model_Model_No"   INTEGER      NOT NULL,
    "Year_From"        INTEGER,
    "Year_To"          INTEGER,
    "Date_Created"     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"       VARCHAR(50)  NOT NULL DEFAULT 'system',
    "Date_Updated"     TIMESTAMPTZ,
    "Updated_By"       VARCHAR(50),
    CONSTRAINT "Compatibility_PK"
        PRIMARY KEY ("Com_ID"),
    CONSTRAINT "Compatibility_Stock_FK"
        FOREIGN KEY ("Stock_Stock_ID") REFERENCES public."Stock" ("Stock_ID"),
    CONSTRAINT "Compatibility_Model_FK"
        FOREIGN KEY ("Model_Model_No") REFERENCES public."Model" ("Model_No"),
    CONSTRAINT "unique_compatibility"
        UNIQUE ("Stock_Stock_ID", "Model_Model_No", "Year_From", "Year_To")
);
```

Two design decisions were explicitly reasoned through and confirmed here:

1. **`Year_From` / `Year_To` instead of a single `Year` column.** The supervisor's examples (e.g. "fits this model from this year to this year") described a *range*, not a single year, so two nullable integer columns were used instead of one, with both nullable so that open-ended ranges ("2020 onward", "up to 2019", or "no restriction at all") could be represented without duplicate rows.
2. **A `UNIQUE` constraint on the business key**, added on top of the surrogate `Com_ID` primary key. It was explicitly reasoned that a surrogate PK alone does *not* prevent two identical compatibility rows (same stock, same model, same years) from both being inserted — hence the additional composite `UNIQUE` constraint. (A known, accepted limitation: PostgreSQL treats `NULL = NULL` as not-equal in unique constraints, so two rows with the same Stock/Model but both years `NULL` could technically both be inserted; this was assessed as an acceptable edge case for the project's scope rather than something requiring a more complex constraint.)

**Consequential changes made to existing tables** as a direct result of this redesign:

```sql
-- Remove the now-obsolete direct relationship
ALTER TABLE public."Spare_Parts"
    DROP CONSTRAINT IF EXISTS "Spare_Parts_Model_FK";
ALTER TABLE public."Spare_Parts"
    DROP COLUMN IF EXISTS "Model_Model_No";

-- Per the same supervisor review: Size should not be mandatory
-- (Size belongs to Stock; Year belongs to Compatibility — they are not
-- interchangeable, and not every stock variant has a meaningful size)
ALTER TABLE public."Stock"
    ALTER COLUMN "Size" DROP NOT NULL;
```

The Admin Panel's Spare Parts module (Task 15) had already been built with a Model dropdown at this point, and had to be revised to remove it once the schema changed — this cross-cutting impact (a database change requiring a corresponding Admin Panel code change) is documented further in Section 12.

### 6.4 Purchase Order and Purchase Order Item

The same supervisor review also identified a problem in the originally-planned Purchase Order design. The supervisor's stated business rule (paraphrased): *"when doing an order, I reference the spare part — I don't reference stock."* A Purchase Order line item is created when an order is placed, at which point a matching `Stock_ID` may not exist yet at all (either because the exact size/brand variant has never been stocked, or because the spare part itself is only now being introduced).

This ruled out the originally-modelled `PO_Stock` bridge table (which required a `Stock_ID` to exist at order-creation time) and led to a new `PurchaseOrderItem` design:

```sql
CREATE TABLE IF NOT EXISTS public."PurchaseOrder" (
    "PurchaseOrderID"     INTEGER      GENERATED ALWAYS AS IDENTITY,
    "POrderDate"          DATE         NOT NULL,
    "ExpectedDate"        DATE         NOT NULL,
    "Status"              VARCHAR(30)  NOT NULL,
    "Supplier_SupplierID" INTEGER      NOT NULL,
    "Date_Created"        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"          VARCHAR(20)  NOT NULL DEFAULT 'system',
    "Date_Updated"        TIMESTAMPTZ,
    "Updated_By"          VARCHAR(20),
    CONSTRAINT "PurchaseOrder_PK" PRIMARY KEY ("PurchaseOrderID"),
    CONSTRAINT "PurchaseOrder_Supplier_FK" FOREIGN KEY ("Supplier_SupplierID")
        REFERENCES public."Supplier" ("SupplierID")
);

CREATE TABLE IF NOT EXISTS public."PurchaseOrderItem" (
    "POItem_ID"           INTEGER        GENERATED ALWAYS AS IDENTITY,
    "PurchaseOrder_ID"    INTEGER        NOT NULL,
    "SP_id"               INTEGER        NOT NULL,   -- references the spare part, NOT stock
    "Quantity_Ordered"    INTEGER        NOT NULL,
    "BuyingPrice"         NUMERIC(10,2)  NOT NULL,
    "Size_Expected"       VARCHAR(20),               -- optional hint at order time
    "Stock_Stock_ID"      INTEGER,                   -- NULL until received
    "Quantity_Received"   INTEGER,
    "DateReceived"        DATE,
    "Status"              VARCHAR(20)    NOT NULL DEFAULT 'Ordered',
    "Date_Created"        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    "Created_By"          VARCHAR(50)    NOT NULL DEFAULT 'system',
    "Date_Updated"        TIMESTAMPTZ,
    "Updated_By"          VARCHAR(50),
    CONSTRAINT "POItem_PK" PRIMARY KEY ("POItem_ID"),
    CONSTRAINT "POItem_PO_FK" FOREIGN KEY ("PurchaseOrder_ID")
        REFERENCES public."PurchaseOrder" ("PurchaseOrderID"),
    CONSTRAINT "POItem_SP_FK" FOREIGN KEY ("SP_id")
        REFERENCES public."Spare_Parts" ("SP_id"),
    CONSTRAINT "POItem_Stock_FK" FOREIGN KEY ("Stock_Stock_ID")
        REFERENCES public."Stock" ("Stock_ID")
);
```

The key design property: `Stock_Stock_ID` is **nullable** and is only populated when the item is actually received (see the receiving workflow in Section 10.5 and the module documentation in Section 8.12).

### 6.5 Phase 3 Tables (Transactional Data)

Once Phase 1, Compatibility, and Purchase Order were complete and working in the Admin Panel, the remaining transactional tables were created in a single script:

```sql
CREATE TABLE IF NOT EXISTS public."Customer" (
    "CustomerID"   INTEGER       GENERATED ALWAYS AS IDENTITY,
    "FirstName"    VARCHAR(50)   NOT NULL,
    "LastName"     VARCHAR(50)   NOT NULL,
    "HomeNumber"   VARCHAR(20),
    "PhoneNumber"  VARCHAR(20)   NOT NULL,
    "Email"        VARCHAR(100)  NOT NULL,
    "Street"       VARCHAR(50)   NOT NULL,
    "Town"         VARCHAR(60)   NOT NULL,
    "PostCode"     VARCHAR(10),
    "NIC"          VARCHAR(20)   NOT NULL,
    "Date_Created" TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"   VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated" TIMESTAMPTZ,
    "Updated_By"   VARCHAR(20),
    CONSTRAINT "Customer_PK" PRIMARY KEY ("CustomerID")
);
```

Note that `NIC`, `HomeNumber`, and `PostCode` were changed from Oracle `NUMBER` to `VARCHAR` — Mauritian NIC numbers and postal/home reference numbers are not arithmetic values and can legitimately contain non-numeric formatting, so storing them as text was the correct decision.

```sql
CREATE TABLE IF NOT EXISTS public."Customer_bike" (
    "BikeID"              INTEGER      GENERATED ALWAYS AS IDENTITY,
    "RegistrationNumber"  VARCHAR(6)   NOT NULL,
    "Year"                INTEGER      NOT NULL,
    "VIN"                 VARCHAR(50)  NOT NULL,
    "Model_Model_No"      INTEGER      NOT NULL,
    "Customer_CustomerID" INTEGER      NOT NULL,
    "Date_Created"        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"          VARCHAR(20)  NOT NULL DEFAULT 'system',
    "Date_Updated"        TIMESTAMPTZ,
    "Updated_By"          VARCHAR(20),
    CONSTRAINT "Customer_bike_PK"       PRIMARY KEY ("BikeID"),
    CONSTRAINT "Customer_bike_Model_FK" FOREIGN KEY ("Model_Model_No")
        REFERENCES public."Model" ("Model_No"),
    CONSTRAINT "Customer_bike_Customer_FK" FOREIGN KEY ("Customer_CustomerID")
        REFERENCES public."Customer" ("CustomerID")
);
```

```sql
CREATE TABLE IF NOT EXISTS public."New_MotorBike" (
    "NB_ID"              INTEGER       GENERATED ALWAYS AS IDENTITY,
    "Year"               INTEGER       NOT NULL,
    "Price"              NUMERIC(10,2) NOT NULL,
    "VIN"                VARCHAR(50)   NOT NULL,
    "Status"             VARCHAR(20)   NOT NULL DEFAULT 'Available',
    "Model_Model_No"     INTEGER       NOT NULL,
    "Color_Color"        VARCHAR(20)   NOT NULL,
    "Warranty_Months"    INTEGER       NOT NULL,
    "EngineCC"           INTEGER       NOT NULL,
    "FuelType"           VARCHAR(20)   NOT NULL,
    "Transmission"       VARCHAR(20)   NOT NULL,
    "FuelTankCapacity"   NUMERIC(5,2)  NOT NULL,
    "Date_Created"       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"         VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated"       TIMESTAMPTZ,
    "Updated_By"         VARCHAR(20),
    CONSTRAINT "New_MotorBike_PK"        PRIMARY KEY ("NB_ID"),
    CONSTRAINT "New_MotorBike_VIN_unique" UNIQUE ("VIN"),
    CONSTRAINT "New_MotorBike_Model_FK"  FOREIGN KEY ("Model_Model_No")
        REFERENCES public."Model" ("Model_No"),
    CONSTRAINT "New_MotorBike_Color_FK"  FOREIGN KEY ("Color_Color")
        REFERENCES public."Color" ("Color"),
    CONSTRAINT "New_MotorBike_Status_check"
        CHECK ("Status" IN ('Available', 'Sold'))
);
```

Notable conversion corrections: the Oracle column names `"Warranty(Months)"` and `"FuelTankCapacity(Litres)"` used parentheses, which are invalid/problematic in PostgreSQL identifiers — renamed to `Warranty_Months` and `FuelTankCapacity`. `VIN` was widened from `NVARCHAR2(1)` (an obvious Oracle Data Modeler sizing error) to `VARCHAR(50)`, and given its own `UNIQUE` constraint (see Section 6.8). `Price` and `FuelTankCapacity` were corrected from Oracle `NUMBER` to `NUMERIC(10,2)` / `NUMERIC(5,2)` for correct decimal handling. A `CHECK` constraint restricts `Status` to exactly `'Available'` or `'Sold'`, directly enforcing the business rule described in Section 10.1.

```sql
CREATE TABLE IF NOT EXISTS public."Sale" (
    "SaleID"                INTEGER       GENERATED ALWAYS AS IDENTITY,
    "SaleDate"              DATE          NOT NULL,
    "TotalAmount"           NUMERIC(10,2) NOT NULL,
    "Customer_CustomerID"   INTEGER       NOT NULL,
    "New_MotorBike_NB_ID"   INTEGER       NOT NULL,
    "Employee_EmployeeID"   INTEGER,
    "Date_Created"          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"            VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated"          TIMESTAMPTZ,
    "Updated_By"            VARCHAR(20),
    CONSTRAINT "Sale_PK"          PRIMARY KEY ("SaleID"),
    CONSTRAINT "Sale_unique_bike" UNIQUE ("New_MotorBike_NB_ID"),
    CONSTRAINT "Sale_Customer_FK" FOREIGN KEY ("Customer_CustomerID")
        REFERENCES public."Customer" ("CustomerID"),
    CONSTRAINT "Sale_New_MotorBike_FK" FOREIGN KEY ("New_MotorBike_NB_ID")
        REFERENCES public."New_MotorBike" ("NB_ID"),
    CONSTRAINT "Sale_Employee_FK" FOREIGN KEY ("Employee_EmployeeID")
        REFERENCES public."Employee" ("EmployeeID")
);
```

`Sale_unique_bike` — a `UNIQUE` constraint on `New_MotorBike_NB_ID` — is the database-level guarantee that a given motorbike can only ever be sold once, directly supporting the Sale module's business logic (Section 10.1). `Employee_EmployeeID` is nullable, allowing a sale to be recorded even when the specific salesperson is not tracked.

```sql
CREATE TABLE IF NOT EXISTS public."Appointment" (
    "AppointmentID"        INTEGER      GENERATED ALWAYS AS IDENTITY,
    "Appointment_Date"     DATE         NOT NULL,
    "AppointmentType"      VARCHAR(20)  NOT NULL,
    "Appointment_time"     TIME         NOT NULL,
    "Status"               VARCHAR(20)  NOT NULL,
    "Customer_bike_BikeID" INTEGER      NOT NULL,
    "Employee_EmployeeID"  INTEGER      NOT NULL,
    "Date_Created"         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"           VARCHAR(20)  NOT NULL DEFAULT 'system',
    "Date_Updated"         TIMESTAMPTZ,
    "Updated_By"           VARCHAR(20),
    CONSTRAINT "Appointment_PK" PRIMARY KEY ("AppointmentID"),
    CONSTRAINT "Appointment_CustomerBike_FK" FOREIGN KEY ("Customer_bike_BikeID")
        REFERENCES public."Customer_bike" ("BikeID"),
    CONSTRAINT "Appointment_Employee_FK" FOREIGN KEY ("Employee_EmployeeID")
        REFERENCES public."Employee" ("EmployeeID")
);

CREATE TABLE IF NOT EXISTS public."appointment_service" (
    "Appointment_AppointmentID" INTEGER NOT NULL,
    "Service_ServiceID"         INTEGER NOT NULL,
    "Quantity"                  INTEGER,        -- nullable
    CONSTRAINT "appointment_service_PK"
        PRIMARY KEY ("Appointment_AppointmentID", "Service_ServiceID"),
    CONSTRAINT "appt_service_Appointment_FK" FOREIGN KEY ("Appointment_AppointmentID")
        REFERENCES public."Appointment" ("AppointmentID"),
    CONSTRAINT "appt_service_Service_FK" FOREIGN KEY ("Service_ServiceID")
        REFERENCES public."Service" ("ServiceID")
);

CREATE TABLE IF NOT EXISTS public."Appointment_Stock" (
    "Appointment_AppointmentID" INTEGER NOT NULL,
    "Stock_Stock_ID"            INTEGER NOT NULL,
    "Quantity"                  INTEGER NOT NULL,  -- required, unlike services
    CONSTRAINT "Appointment_Stock_PK"
        PRIMARY KEY ("Appointment_AppointmentID", "Stock_Stock_ID"),
    CONSTRAINT "Appt_Stock_Appointment_FK" FOREIGN KEY ("Appointment_AppointmentID")
        REFERENCES public."Appointment" ("AppointmentID"),
    CONSTRAINT "Appt_Stock_Stock_FK" FOREIGN KEY ("Stock_Stock_ID")
        REFERENCES public."Stock" ("Stock_ID")
);
```

Two important design decisions here:
- `appointment_service` and `Appointment_Stock` are pure **bridge tables with composite primary keys** and, deliberately, **no audit fields** — they record simple many-to-many associations rather than independently significant business records.
- `appointment_service.Quantity` is nullable (a service can be logged without a countable quantity, e.g. "diagnostic check"), whereas `Appointment_Stock.Quantity` is `NOT NULL` (a physical part consumed must always have a count).
- `Appointment.Appointment_time` uses PostgreSQL's native `TIME` type — storing only a time-of-day value, distinct from `Appointment_Date`. The Oracle original had modelled this as `DATE`, which was corrected during conversion since a `DATE` type conflates a calendar date with a clock time.

```sql
CREATE TABLE IF NOT EXISTS public."Payment" (
    "PaymentID"                 INTEGER       GENERATED ALWAYS AS IDENTITY,
    "PaymentDate"               DATE          NOT NULL,
    "AmountPaid"                NUMERIC(10,2) NOT NULL,
    "PaymentMethod"             VARCHAR(20)   NOT NULL,
    "PaymentType"               VARCHAR(20)   NOT NULL,
    "Sale_SaleID"               INTEGER,
    "Appointment_AppointmentID" INTEGER,
    "Date_Created"              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"                VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated"              TIMESTAMPTZ,
    "Updated_By"                VARCHAR(20),
    CONSTRAINT "Payment_PK" PRIMARY KEY ("PaymentID"),
    CONSTRAINT "Payment_Sale_FK" FOREIGN KEY ("Sale_SaleID")
        REFERENCES public."Sale" ("SaleID"),
    CONSTRAINT "Payment_Appointment_FK" FOREIGN KEY ("Appointment_AppointmentID")
        REFERENCES public."Appointment" ("AppointmentID"),
    CONSTRAINT "Payment_requires_reference"
        CHECK ("Sale_SaleID" IS NOT NULL OR "Appointment_AppointmentID" IS NOT NULL)
);
```

**Important design correction (circular FK removal):** the original Oracle model had a **circular foreign key** — `Appointment` held a `Payment_PaymentID` column pointing at `Payment`, while `Payment` also pointed back at `Appointment`. This was identified as an anti-pattern (it makes it impossible to insert either row first without deferred constraints) and resolved by dropping `Appointment.Payment_PaymentID` entirely — the relationship is expressed only in one direction, from `Payment.Appointment_AppointmentID` to `Appointment`.

A `Payment` originally carried a `UNIQUE` constraint on `Appointment_AppointmentID` (limiting an appointment to exactly one payment). **This constraint was later dropped** once partial/deposit payment support was required for appointments — see Section 6.9 and Section 10.2 for the full reasoning.

### 6.6 Audit Fields and Triggers

Every substantive table (all Phase 1 tables, Compatibility, PurchaseOrder, PurchaseOrderItem, Customer, Customer_bike, New_MotorBike, Sale, Appointment, Payment — but *not* the two pure bridge tables) carries four audit columns:

| Column | Type | Purpose |
|---|---|---|
| `Date_Created` | `TIMESTAMPTZ` | When the row was first inserted |
| `Created_By` | `VARCHAR` | Who inserted it |
| `Date_Updated` | `TIMESTAMPTZ` | When the row was last modified (NULL if never updated) |
| `Updated_By` | `VARCHAR` | Who last modified it |

These are populated entirely by a single shared trigger function, never by application code:

```sql
CREATE OR REPLACE FUNCTION set_audit_fields()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        NEW."Date_Created" := NOW();
        NEW."Created_By"  := COALESCE(
            (SELECT email FROM auth.users WHERE id = auth.uid()),
            'system'
        );
        NEW."Date_Updated" := NULL;
        NEW."Updated_By"   := NULL;

    ELSIF (TG_OP = 'UPDATE') THEN
        NEW."Date_Created" := OLD."Date_Created";
        NEW."Created_By"   := OLD."Created_By";
        NEW."Date_Updated" := NOW();
        NEW."Updated_By"   := COALESCE(
            (SELECT email FROM auth.users WHERE id = auth.uid()),
            'system'
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

One trigger per table attaches this function, e.g.:

```sql
CREATE OR REPLACE TRIGGER audit_color
    BEFORE INSERT OR UPDATE ON "Color"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();
```

`auth.uid()` resolves to the currently authenticated Supabase user's ID from the request's JWT. Before Supabase Auth was implemented (Tasks 01–16), no user was ever authenticated, so `Created_By`/`Updated_By` always fell back to the literal string `'system'` — this was expected, working-as-designed behaviour during that phase, and is discussed further in Section 12 (it was raised as a concern and correctly explained rather than "fixed" prematurely).

An important architectural point verified explicitly during the Authentication task (Task 17): the trigger function is declared `SECURITY DEFINER`, meaning it always executes with the function owner's privileges regardless of who triggered it — but `auth.uid()` inside it still resolves from the *calling request's* JWT, not the function owner. This means RLS (which evaluates *before* the row operation) and the audit trigger (which fires *after* RLS has allowed the operation, populating the audit columns) coexist without conflict — a design detail that was reasoned through and confirmed correct before implementation, rather than discovered by trial and error.

### 6.7 Row Level Security (RLS) and Grants

RLS was implemented in three stages as the project progressed:

**Stage 1 (Tasks 01–16, development):** No authentication existed yet. To allow the Flask app (using the Supabase `anon` key) to perform CRUD during development, broad temporary grants were issued directly to the `anon` role:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Color"       TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Category"    TO anon;
-- ... repeated for all 10 Phase 1 tables ...
```

This was explicitly documented in the SQL as a temporary development measure, to be replaced once authentication was implemented.

**Stage 2 (Task 17 — permanent hardening):** once Supabase Auth was implemented, the anon grants were revoked and replaced with `authenticated`-role grants plus RLS policies:

```sql
-- Grant to authenticated users
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Color" TO authenticated;
-- (repeated per table)

-- Revoke the temporary anon grants
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Color" FROM anon;
-- (repeated per table)

-- Enable RLS
ALTER TABLE public."Color" ENABLE ROW LEVEL SECURITY;

-- Policy: only authenticated users may read/write
CREATE POLICY "admin_full_access" ON public."Color"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);
```

This same three-step pattern (grant to `authenticated`, revoke from `anon`, enable RLS + policy) was applied to every one of the 10 Phase 1 tables in one migration.

**Stage 3 (ongoing, per new table):** every table created after Task 17 (Compatibility, PurchaseOrder, PurchaseOrderItem, and all Phase 3 tables) had its RLS policy and `authenticated` grant added at creation time, following the identical `admin_full_access` policy pattern, rather than being retrofitted later.

The order of operations here mattered and was explicitly reasoned through: **UNIQUE constraints were added before RLS was enabled**, because if duplicate data already existed in a table (e.g. from earlier ad-hoc testing), attempting to add a UNIQUE constraint afterward would fail outright. The duplicate-check-then-constrain-then-secure sequence is documented in the SQL comments themselves (see Section 6.8).

### 6.8 Constraints, Uniqueness, and Data Integrity Rules

The following UNIQUE constraints were added specifically to prevent real duplicate-data problems identified during testing (see Section 12 for the incidents that prompted each one):

```sql
ALTER TABLE public."Brand"
    ADD CONSTRAINT "unique_brand_name" UNIQUE ("Brand_Name");

ALTER TABLE public."Category"
    ADD CONSTRAINT "unique_category_desc" UNIQUE ("CAT_desc");

ALTER TABLE public."Role"
    ADD CONSTRAINT "unique_role_name" UNIQUE ("Role_Name");

ALTER TABLE public."Service"
    ADD CONSTRAINT "unique_service_name" UNIQUE ("Service_Name");

ALTER TABLE public."Supplier"
    ADD CONSTRAINT "unique_supplier_name" UNIQUE ("SupplierName");

ALTER TABLE public."Model"
    ADD CONSTRAINT "unique_model_description" UNIQUE ("Description");
```

Later, when reviewing the Customer and Customer_bike modules specifically for duplicate-data risk, two more rounds of UNIQUE constraints were added:

- **Customer:** `NIC` and `PhoneNumber` were each made unique (two different customers cannot share a National Identity Card number or the same phone number), while `FirstName`/`LastName` were deliberately **left non-unique**, since two genuinely different customers can share a common name.
- **Customer_bike:** `VIN` and `RegistrationNumber` were each made unique — a real motorbike's VIN and licence plate are, in reality, one-of-a-kind identifiers.

An explicit design question was raised and resolved during this same review: *could a `Customer_bike` and a `New_MotorBike` legitimately share the same VIN?* The conclusion (documented in Section 10.1 and Section 12) was that this is not a bug but the expected lifecycle of a bike the dealership itself sold — `New_MotorBike` represents dealer inventory, `Customer_bike` represents a customer-owned, service-eligible vehicle, and the same physical VIN correctly appears in both once a dealer-sold bike returns for servicing. No cross-table uniqueness constraint was added, and this was explicitly confirmed as by-design rather than left unresolved.

**The `Sale_unique_bike` and `New_MotorBike_VIN_unique` constraints** (Section 6.5) were reasoned through at schema-design time rather than retrofitted, since the "one bike sold once" and "one VIN per motorbike" rules were understood as core business invariants from the start of Phase 3 design.

**The most consequential constraint change made during the entire project** was the later removal of `unique_appointment_payment` from `Payment`:

```sql
ALTER TABLE public."Payment"
    DROP CONSTRAINT IF EXISTS "unique_appointment_payment";
```

This constraint had originally limited an Appointment to exactly one Payment row. Once the business requirement was clarified — an appointment, like a sale, should support partial/deposit payments followed by a further payment for the remaining balance — this constraint became directly incompatible with the required behaviour and had to be dropped. This is documented in full, including the reasoning for why it was safe to remove without other schema changes, in Section 10.2 and Section 12.

### 6.9 Database Evolution — Changes Made During Development

Summarising the database's evolution chronologically:

| Stage | Change | Reason |
|---|---|---|
| Initial conversion | Oracle types → PostgreSQL types across all Phase 1 tables | Target database changed from planned MySQL to Supabase/Postgres |
| Initial conversion | Removed `Employee.SaleID` | Modelling error; created a circular/impossible dependency |
| Initial conversion | Added `Employee.SupervisorID` | Present in diagram but missing from Oracle DDL export |
| Initial conversion | Corrected `Spare_Parts.SP_desc`, `Spare_Parts.Updated_By`, `Stock.Size` types | Oracle DDL sizing/type errors |
| Supervisor review | Removed `Spare_Parts.Model_Model_No`; added `Compatibility` table | Direct FK could not express multi-model, year-ranged compatibility |
| Supervisor review | Made `Stock.Size` nullable | Not every stock variant has a meaningful size |
| Supervisor review | Replaced planned `PO_Stock` with `PurchaseOrderItem` (Stock_Stock_ID nullable) | Orders reference spare parts, not pre-existing stock rows |
| Phase 3 design | Removed circular `Appointment.Payment_PaymentID` | Anti-pattern; resolved by keeping only `Payment → Appointment` |
| Post-Phase-3 review | Added UNIQUE on Brand/Category/Role/Service/Supplier/Model names | Prevent duplicate master-data entry (see Section 12) |
| Post-Phase-3 review | Added UNIQUE on Customer.NIC, Customer.PhoneNumber | Prevent duplicate customer records |
| Post-Phase-3 review | Added UNIQUE on Customer_bike.VIN, Customer_bike.RegistrationNumber | Prevent duplicate vehicle records |
| Payment logic review | Dropped `unique_appointment_payment` from Payment | Required to support partial/deposit Appointment payments |
| Post-Task-26 supervisor review | Added `PO_NewMotorBike` bridge table (PurchaseOrder ↔ New_MotorBike) | PurchaseOrder previously only supported spare-part procurement; no table existed to record a motorcycle unit purchased through a PO |

`[INSERT IMAGE HERE — Database Version/Evolution Timeline Diagram]`
*A simple horizontal timeline showing the schema at each of the stages listed above.*

### 6.10 PO_NewMotorBike — Motorcycle Purchase Ordering Bridge (Post-Task 26 Addition)

A subsequent supervisor review identified a gap symmetrical to the one that originally produced `PurchaseOrderItem` (Section 6.4): `PurchaseOrder` could record spare-part procurement, but there was no equivalent way to record that a specific `New_MotorBike` unit had been purchased through a Purchase Order. A new bridge table was added to close this gap:

```sql
CREATE TABLE IF NOT EXISTS public."PO_NewMotorBike" (
    "PurchaseOrder_PurchaseOrderID" INTEGER       NOT NULL,
    "New_MotorBike_NB_ID"           INTEGER       NOT NULL,
    "BuyingPrice"                   NUMERIC(10,2),
    "DateReceived"                  DATE,

    CONSTRAINT "PO_NewMotorBike_PK"
        PRIMARY KEY ("PurchaseOrder_PurchaseOrderID", "New_MotorBike_NB_ID"),

    CONSTRAINT "PO_NewMotorBike_PurchaseOrder_FK"
        FOREIGN KEY ("PurchaseOrder_PurchaseOrderID")
        REFERENCES public."PurchaseOrder" ("PurchaseOrderID"),

    CONSTRAINT "PO_NewMotorBike_NewMotorBike_FK"
        FOREIGN KEY ("New_MotorBike_NB_ID")
        REFERENCES public."New_MotorBike" ("NB_ID"),

    -- Not shown explicitly in the ERD, but added for data integrity: without
    -- it, the same physical motorbike could be linked to two different
    -- purchase orders, which cannot happen for a single physical unit.
    CONSTRAINT "PO_NewMotorBike_unique_bike"
        UNIQUE ("New_MotorBike_NB_ID")
);
```

Design differences from `PurchaseOrderItem`, deliberate rather than oversights:

- **No audit columns.** Matching the other pure link-only bridge tables (`appointment_service`, `Appointment_Stock`) rather than the fully audited transactional tables.
- **No `Quantity_Ordered` / `Status` split.** A motorbike is a single physical unit, not a countable line item — a row in `PO_NewMotorBike` simply records that one specific `New_MotorBike` (identified by `NB_ID`) was procured through that PO, at what `BuyingPrice`, and (once known) on what `DateReceived`. There is no "Ordered but not yet Received" state to track the way `PurchaseOrderItem.Status` tracks for spare parts.
- **`DateReceived` is nullable**, so a motorbike can be linked to a PO — and its buying price recorded — before it physically arrives at the dealership, with the date filled in later via Edit.

At the Admin Panel level, this table is managed entirely inside the existing Purchase Order module (Section 8.12/8.19) rather than as a separate module — motorcycle procurement lines, like spare-part items, are always viewed and edited in the context of the Purchase Order they belong to.

Two items were flagged during review and are documented as open, unresolved issues rather than fixed defects: the "New Motorcycle Record" creation path can currently misattribute a VIN-uniqueness error as a PO-linkage error (because both inserts share one exception handler), and linking or editing a `PO_NewMotorBike` row does not feed into the PO's own `Status` recalculation the way receiving a `PurchaseOrderItem` does. These are recorded here for the next development/review cycle rather than left undocumented.

## 7. Authentication and Security

### 7.1 Supabase Auth Integration

Authentication was deliberately deferred until after all CRUD modules (Phase 1 through Phase 3) were built and individually tested — a decision made explicitly during planning, on the reasoning that the Admin Panel should be developed and verified against a stable, unauthenticated baseline first, then have security retrofitted as one focused, testable unit (Task 17), rather than interleaving auth concerns into every earlier module.

Before Task 17, all 18 CRUD modules operated with a **pass-through** `login_required` decorator:

```python
# app/auth/decorators.py — BEFORE Task 17 (pass-through placeholder)
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function
```

This let every route be written, from the beginning, as if authentication already existed (`@bp.route(...)` followed by `@login_required` on every view function), so that activating real authentication later required changing only the decorator's internals — not touching a single one of the 17+ already-written route files.

**Clerk vs Supabase Auth — a decision explicitly evaluated and rejected in favour of Supabase Auth.** Clerk was considered as an authentication provider but rejected because:
- Clerk's first-class integration path is for Next.js/React; Flask support is comparatively unmaintained.
- The project's audit triggers (Section 6.6) already depend on `auth.uid()` — a **Supabase Auth**-native function. Using Clerk would have meant `auth.uid()` inside the trigger could never resolve to the real logged-in user, permanently breaking the `Created_By`/`Updated_By` audit trail.
- Supabase Auth requires no additional third-party account, and integrates directly with the RLS policies already planned for every table.

### 7.2 Session Management

Once implemented (Task 17), login is handled via the Supabase Python client's `sign_in_with_password`, with the resulting tokens stored in Flask's server-side session:

```python
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('access_token'):
        return redirect(url_for('dashboard.index'))

    error = None
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            error = 'Email and password are required.'
        else:
            try:
                response = supabase.auth.sign_in_with_password({
                    'email': email, 'password': password,
                })
                session['access_token']  = response.session.access_token
                session['refresh_token'] = response.session.refresh_token
                session['user_email']    = response.user.email
                return redirect(url_for('dashboard.index'))
            except Exception:
                error = 'Invalid email or password. Please try again.'

    return render_template('auth/login.html', error=error)
```

Logging out clears both the Supabase Auth session and the Flask session:

```python
@bp.route('/logout')
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    session.clear()
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('auth.login'))
```

### 7.3 Protected Routes

The `login_required` decorator was then given its real implementation:

```python
# app/auth/decorators.py — AFTER Task 17 (real session check)
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

Restoring the Supabase session (`set_session`) before validating it means every subsequent database call made during that same request executes under the authenticated user's JWT — which is what allows the audit trigger's `auth.uid()` to correctly resolve to the real logged-in staff member from this point onward, rather than falling back to `'system'`.

### 7.4 RLS and Application-Level Security Together

The Admin Panel is protected at **two independent layers**, deliberately:

1. **Application layer** — the `@login_required` decorator on every route, which redirects an unauthenticated browser to the login page before any template is even rendered.
2. **Database layer** — PostgreSQL RLS policies (Section 6.7), which reject any query from a connection that is not carrying a valid `authenticated` JWT, regardless of what the Flask application code does or fails to do.

This two-layer design was a deliberate defence-in-depth decision: even if a bug in the Flask route code somehow bypassed the decorator, the database itself would still refuse the query.

`[INSERT IMAGE HERE — Authentication Flow Diagram]`
*A sequence diagram: Browser → /auth/login (POST) → Supabase Auth → Flask session populated → subsequent request → @login_required checks session → set_session() restores Supabase JWT → RLS-protected query succeeds.*

---
## 8. Admin Panel Modules

Every module in the Admin Panel follows the same architectural pattern, established with the first module (Color) and reused, with proportional additions, all the way through to Payment:

- A Flask Blueprint (`app/modules/<module>/__init__.py` + `routes.py`).
- A `list.html` (search + paginated table + delete confirmation modal) and `form.html` (shared Create/Edit template, toggled by an `is_edit` flag).
- Server-side validation in Python before any Supabase call — never relying on HTML `required` attributes alone (in fact every form uses `novalidate` specifically so the server-side validation and its error messages are what the user actually sees).
- All errors for a submission are collected and shown **simultaneously**, not one at a time.
- Foreign keys are always presented as dropdowns (never raw ID entry), with dropdown options built from a small `_get_form_options()`-style helper.
- Audit fields (`Date_Created`, `Created_By`, `Date_Updated`, `Updated_By`) are always displayed **read-only** on the Edit form and never set by application code — the database trigger (Section 6.6) is the only writer.
- Pagination via a shared `paginate()` utility, 10 records per page.
- Delete confirmation via a single shared modal component, populated per-row via `data-*` attributes.

### 8.1 Color

**Purpose:** Manage the catalogue of available motorbike/part colors.

**Structural note:** Color is the one module whose primary key is the color name itself (a string), not a surrogate integer — this affects every route in the module, since `<string:color_id>` is used in place of `<int:...>` elsewhere, and both Edit and Delete operate by matching on the `Color` column directly rather than a numeric ID.

**CRUD:**
- **Create:** single required text field (`Color`, max 20 characters).
- **List:** alphabetical, searchable by color name, showing all four audit columns.
- **Edit:** because the primary key is user-editable text, renaming a color updates the PK value directly (`UPDATE ... WHERE "Color" = <old_value>`) — a design implication accepted because, at the time, no other Phase 1 table held a hard FK to Color. This constraint was later introduced when `New_MotorBike.Color_Color` was added in Phase 3, creating a dependency on the Color string primary key.
- **Delete:** simple delete with a generic FK-violation catch, later meaningfully triggered once `New_MotorBike` referenced Color.
- **Validation:** required, max 20 characters, and duplicate-name detection (Color's own PK constraint naturally prevents duplicates without needing an extra UNIQUE constraint).

### 8.2 Category

**Purpose:** Categorise spare parts (e.g. "Engine Parts", "Electrical").

**CRUD:** Standard single-field (`CAT_desc`, max 20 characters) module with an auto-generated integer PK (`CAT_ID`). Later given a `unique_category_desc` UNIQUE constraint (Section 6.8) after the duplicate-master-data review, with the corresponding route code updated to catch the resulting database exception and turn it into a friendly message: *"A category with this description already exists."*

**Relationships:** Referenced by `Spare_Parts.Category_CAT_ID` — every spare part must belong to exactly one category.

### 8.3 Role

**Purpose:** Define employee job roles and their hourly pay rate.

**Fields:** `Role_Name` (max 15 chars) and `HourlyRate` (a `NUMERIC(10,2)` money field, displayed throughout the Admin Panel formatted as `Rs. X.XX`). This was the first module to introduce a numeric/money field and the `number_field` Jinja macro.

**Validation:** `HourlyRate` validated with the shared `is_positive_number()` utility before being cast to `float()` — deliberately validated *before* casting, so a non-numeric submission cannot crash the route with an unhandled `ValueError`.

**Relationships:** Referenced by `Employee.Role_Role_ID`. Deleting a Role that is still assigned to an Employee correctly surfaces a friendly error naming the conflict rather than a raw database exception:

```python
if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
    flash_error(
        f'Cannot delete "{name_value}" because it is assigned to '
        f'one or more employees. Reassign those employees first.'
    )
```

This same pattern — catch the FK violation string, translate it into a specific, actionable sentence naming the actual dependent table — is repeated consistently across every module in the system whenever a Delete could be blocked by a foreign key.

### 8.4 Supplier

**Purpose:** Manage supplier company records used later by Purchase Orders.

**Fields (5):** `SupplierName`, `Phone`, `Email`, `Address` (a `textarea_field`, the first use of that macro), `Country`.

**Validation:** the first module requiring a dedicated `is_valid_email()` utility, written without a regex dependency:

```python
def is_valid_email(value):
    if not isinstance(value, str):
        return False
    if value.count('@') != 1:
        return False
    local, domain = value.split('@')
    if not local:
        return False
    if '.' not in domain:
        return False
    return True
```

All five fields are validated and any resulting errors shown together — the first module to demonstrate the "collect every field error before re-rendering" pattern used throughout the rest of the project.

### 8.5 Brand

**Purpose:** Manage motorbike/parts manufacturer brands (e.g. Honda, Yamaha).

**Fields (2):** `Brand_Name` (max 50), `CountryOfOrigin` (max 40).

**Relationships — the first module with *two* FK dependents simultaneously:** both `Model.Brand_Brand_ID` and `Stock.Brand_Brand_ID` reference Brand. Deleting a brand with either dependency correctly reports both possibilities in one message:

```python
flash_error(
    f'Cannot delete "{name_value}" because it is referenced by '
    f'one or more models or stock entries. '
    f'Remove those records first before deleting this brand.'
)
```

Later given a `unique_brand_name` UNIQUE constraint (Section 6.8).

### 8.6 Service

**Purpose:** The dealership's catalogue of workshop services (e.g. "Basic Service A") and their fixed cost.

**Fields (3):** `Service_Name`, `Description` (textarea), `Cost` (money field).

**UI detail:** the list table truncates `Description` to 60 characters with a trailing `...`, while the full untruncated text remains visible in the Edit form textarea — a small but deliberate UX decision to keep the list table scannable without losing the full description when actually editing.

**Relationships:** referenced later by `appointment_service.Service_ServiceID` — this is the join used to calculate an appointment's estimated service cost (Section 10.3).

### 8.7 Employee

**Purpose:** Manage dealership staff records, including their role and (optionally) their supervisor.

This was the most structurally complex Phase 1 module, introducing **two simultaneous FK dropdowns** — one required (`Role_Role_ID`) and one optional/self-referencing (`SupervisorID`).

**Key implementation detail — excluding an employee from their own Supervisor dropdown on Edit:**

```python
def _get_form_options(exclude_employee_id=None):
    ...
    supervisor_options = [
        (e['EmployeeID'], f"{e['FirstName']} {e['LastName']}")
        for e in (emp_result.data or [])
        if e['EmployeeID'] != exclude_employee_id
    ]
    return role_options, supervisor_options
```

On the Create form, every employee is a valid supervisor option; on the Edit form, the employee currently being edited is filtered out of their own Supervisor dropdown, preventing an employee from being set as their own manager. The Supervisor dropdown's empty option is explicitly labelled `"— No Supervisor (Senior Staff) —"` rather than a bare blank, so choosing "no supervisor" is a clear, intentional action rather than an accidental omission.

**Optional-to-NULL handling:** submitting the form with no Supervisor selected must store SQL `NULL`, not an empty string:

```python
supervisor_id = None
if supervisor_id_raw:
    try:
        supervisor_id = int(supervisor_id_raw)
    except ValueError:
        errors['SupervisorID'] = 'Invalid supervisor selection.'
```

**Delete behaviour:** deleting an employee who is currently listed as someone else's supervisor is blocked with a targeted message ("...listed as a supervisor for one or more other employees. Reassign those employees to a different supervisor first.").

### 8.8 Model

**Purpose:** Manage specific motorbike models within a Brand (e.g. "Honda CB Shine 125cc").

**Fields:** `Brand_Brand_ID` (required FK dropdown) and `Description` (max 50).

**PK naming note:** the primary key column is named `Model_No`, not `ModelID` — every route parameter, `url_for()` call, and Supabase filter in this module deliberately uses `model_no` throughout to stay consistent with the actual database column name, avoiding the confusion of a route parameter named differently from the column it maps to.

**A significant post-launch change (Section 6.3):** this module originally also had a `Model_Model_No`-linked Spare Parts relationship exposed via a dropdown on the Spare Parts form; that direct relationship was later removed from the database entirely and replaced by the Compatibility module (Section 8.11), requiring the corresponding dropdown to be stripped out of the Spare Parts Create/Edit forms after the fact — this is documented in full in Section 12.

Later given a `unique_model_description` UNIQUE constraint.

### 8.9 Spare Parts

**Purpose:** Manage the spare parts *catalogue* — the definition of a part (name, description, category), independent of any specific stocked variant.

**Fields (originally 4, later reduced to 3):** `SP_name`, `SP_desc` (textarea), `Category_CAT_ID` (required FK dropdown), and originally `Model_Model_No` (optional FK dropdown, later **removed entirely** — see Section 6.3 and Section 12).

**Key conceptual distinction (explicitly defined and preserved throughout the project):** `Spare_Parts` represents *what a part is* (e.g. "Air Filter"); `Stock` (Section 8.10) represents *a specific physical variant of it* (e.g. "Air Filter, Medium, Honda brand, QOH 10"). One Spare_Parts row can have many Stock rows. This distinction is the foundation the Compatibility module and the Purchase Order receiving workflow are both built on top of.

**Relationships:** `Category_CAT_ID` required; `Stock.Spare_Parts_SP_id` is the 1:M dependent relationship in the other direction.

### 8.10 Stock

**Purpose:** Manage physical inventory — specific size/brand/price variants of a Spare Part, with quantity-on-hand tracking.

**Fields (6):** `Spare_Parts_SP_id` (required FK), `Brand_Brand_ID` (required FK), `Size` (originally required, later made optional — Section 6.3), `QOH` (integer), `S_Price` (money), `Warranty` (integer, months).

**The most field-rich Phase 1 module**, combining every field-type macro built up to that point: two required FK dropdowns simultaneously, an alphanumeric text field, two integer number fields, and one money field.

**Validation detail:** `QOH` and `Warranty` are validated with `is_positive_integer()`, `S_Price` with `is_positive_number()`, each before the corresponding type cast — the same "validate-before-cast" discipline established in the Role module.

**List display detail:** a `QOH` of exactly `0` is rendered in red (`.stock-zero` CSS class) to visually flag out-of-stock items at a glance, without needing a separate "low stock" report.

**Later change (Section 6.3):** `Size` was made nullable at the supervisor's request, and the corresponding form field's `required` flag and help text were updated to say "Optional." — a small template change that had to be kept in lockstep with the database migration that dropped the `NOT NULL` constraint.

`[INSERT IMAGE HERE — Stock Module List View]`
*Screenshot of the Stock list page, showing the red-highlighted zero-QOH row, the resolved Spare Part / Brand labels, and the Rs.-formatted price column.*

---
### 8.11 Compatibility

**Purpose:** Record which Stock variants are compatible with which motorbike Models, optionally restricted to a year range. This module exists specifically because of the supervisor's ERD review (Section 6.3) and did not exist in the original project plan.

**Structural distinctiveness:** unlike every module before it, Compatibility's folder, Blueprint, sidebar link, and dashboard card were all created **from scratch** in a single task, rather than replacing a pre-existing placeholder — because Compatibility was not part of the original folder scaffold built in Task 03.

**Enrichment complexity:** this is the most query-intensive module in the system. Displaying a single Compatibility row's dropdown label requires a three-table join chain done manually via lookup dictionaries (since no ORM is used):

```python
def _build_stock_label(sp_name, size, brand_name):
    if size:
        return f"{sp_name} [{size}] \u2014 {brand_name}"
    return f"{sp_name} \u2014 {brand_name}"
```

`Stock → Spare_Parts (for SP_name) → Brand (for Brand_Name)` are all fetched and joined in Python to build labels like `Air Filter [Medium] — Honda`, and similarly `Model → Brand` for labels like `Honda — CB Shine 125cc`.

**Year range validation** (`_validate_year()`): both `Year_From` and `Year_To` are optional integers, each individually range-checked (1900–2100), with a cross-field rule enforced only once both individual fields pass: `Year_To` must be greater than or equal to `Year_From`.

**Multi-model selection (added after initial feedback):** the Create form was later enhanced so a single Stock item can be linked to **multiple** Models in one submission, via a multi-select `<select multiple>` control, iterating the insert per selected model and reporting a combined success/duplicate/failure count in the flash message:

```python
for model_no_str in selected_model_nos:
    try:
        model_no = int(model_no_str)
        supabase.table('Compatibility').insert({...}).execute()
        success_count += 1
    except Exception as e:
        if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
            duplicate_count += 1
        else:
            fail_count += 1
```

The Edit form deliberately remains single-select, since editing always concerns one specific existing Compatibility row.

**Relationships:** `Stock_Stock_ID` and `Model_Model_No`, both required FKs; the `unique_compatibility` composite constraint prevents duplicate stock/model/year-range combinations at the database level, with the route catching the resulting exception and translating it to: *"A compatibility record for this stock item, model, and year range already exists."*

### 8.12 Purchase Order and Purchase Order Item

**Purpose:** Record supplier orders (PurchaseOrder) and their individual line items (PurchaseOrderItem), and implement the two-path stock receiving workflow.

This module was implemented across two tasks: the PurchaseOrder header CRUD first, then item management and receiving logic added afterward once the header module was confirmed working.

**PurchaseOrder fields:** `Supplier_SupplierID` (required FK), `POrderDate` and `ExpectedDate` (both date fields, using a new `date_field` Jinja macro built specifically for this module), `Status` (a fixed four-value select: Pending, Partially Received, Received, Cancelled).

**Cross-field date validation:** `ExpectedDate` must be on or after `POrderDate` — the first module requiring a two-date ordering check.

**PurchaseOrderItem — the "order references a spare part, not stock" rule in code.** Adding an item requires only `SP_id`, `Quantity_Ordered`, `BuyingPrice`, and an optional `Size_Expected` hint; `Stock_Stock_ID` is left `NULL` at this stage and is only ever set by the receiving workflow.

**The receiving workflow (`receive_item` route) implements exactly the two paths reasoned through at schema-design time (Section 6.4):**

```python
if recv_mode == 'existing':
    # CASE A — Update existing stock QOH
    existing_result = (
        supabase.table('Stock')
        .select('QOH')
        .eq('Stock_ID', stock_id_to_link)
        .single()
        .execute()
    )
    current_qoh = existing_result.data.get('QOH', 0)
    supabase.table('Stock').update(
        {'QOH': current_qoh + qty_recv}
    ).eq('Stock_ID', stock_id_to_link).execute()

elif recv_mode == 'new':
    # CASE B — Create new stock record
    new_stock_result = supabase.table('Stock').insert({
        'Spare_Parts_SP_id': sp_id,
        'Brand_Brand_ID':    new_brand_id,
        'Size':              new_size,
        'QOH':              qty_recv,
        'S_Price':           new_price,
        'Warranty':          new_warranty,
    }).execute()
    stock_id_to_link = new_stock_result.data[0]['Stock_ID']

# In both cases, the PO Item is finalised:
supabase.table('PurchaseOrderItem').update({
    'Quantity_Received': qty_recv,
    'DateReceived':      date_recv,
    'Stock_Stock_ID':    stock_id_to_link,
    'Status':           'Received',
}).eq('POItem_ID', item_id).execute()
```

The receive form presents these two paths as a radio-button toggle (mirroring the same UI pattern later reused for the Payment module's Sale/Appointment reference toggle): "Add to Existing Stock" (a dropdown of existing Stock variants for the same spare part, labelled with current QOH) versus "Create New Stock Entry" (a fresh Brand/Size/Price/Warranty form).

**Automatic PO status rollup:** after any item is received, the parent PurchaseOrder's `Status` is automatically recalculated:

```python
def _auto_update_po_status(po_id):
    items = ...  # all PurchaseOrderItem rows for this PO
    total    = len(items)
    received = sum(1 for i in items if i.get('Status') == 'Received')
    if received == total:
        new_status = 'Received'
    elif received > 0:
        new_status = 'Partially Received'
    else:
        return  # leave as Pending
    supabase.table('PurchaseOrder').update({'Status': new_status}).eq(...)
```

**Item lifecycle rule:** an item with Status `'Ordered'` can be freely edited or deleted; once Status becomes `'Received'`, both actions are blocked, because a received item has already changed live Stock quantities and deleting or editing it after the fact would silently desynchronise inventory from its purchase history.

`[INSERT IMAGE HERE — Purchase Order Receiving Flow]`
*Screenshot or flow diagram of the receive-item form, showing the "Existing Stock" vs "New Stock" radio toggle.*

### 8.13 Customer

**Purpose:** Manage customer personal and contact records — the first Phase 3 module.

**Fields (9):** `FirstName`, `LastName`, `PhoneNumber` (required), `HomeNumber` (optional), `Email` (validated with `is_valid_email`), `Street`, `Town`, `PostCode` (optional), `NIC` (required).

**Two-card form layout:** the Create/Edit form is the first module to visually split fields into two logical groups ("Personal Information" and "Address") within a single `<form>` element that spans both cards — a UI refinement introduced here and not needed in earlier, simpler modules.

**Duplicate-prevention (added in a follow-up review, not the initial build):** `NIC` and `PhoneNumber` were each given UNIQUE constraints after the initial Customer module was already working, specifically to prevent the same real person being entered twice under two different Customer records. `FirstName`/`LastName` were deliberately left unconstrained, since two unrelated customers can share a common name — uniqueness was applied only to fields that genuinely identify a unique individual.

**Relationships:** referenced by `Customer_bike.Customer_CustomerID` and `Sale.Customer_CustomerID`; deleting a Customer with either dependency is blocked with a message naming both possibilities.

### 8.14 Customer Bike

**Purpose:** Register a specific motorbike as belonging to a specific Customer, referencing a Model.

**Fields (5):** `Customer_CustomerID` (required FK), `Model_Model_No` (required FK), `RegistrationNumber` (max 6, Mauritius plate format), `Year` (1900–2100), `VIN` (max 50).

**Dropdown label patterns established here and reused later:**
- Customer dropdown: `"FirstName LastName"`.
- Model dropdown: `"Brand_Name — Description"` (the same enriched-label pattern first built for Compatibility).

**Duplicate-prevention and ownership transfer (added in the same follow-up review as Customer's):** `VIN` and `RegistrationNumber` were each given UNIQUE constraints, so the same physical vehicle cannot exist as two separate Customer_bike rows. This directly created the need for an explicit **ownership transfer** workflow: rather than creating a *new* Customer_bike row when a registered bike changes owner (which the UNIQUE constraints would now reject as a duplicate VIN/registration), the correct operation is to **edit the existing Customer_bike record** and reassign its `Customer_CustomerID` to the new owner, leaving `VIN`, `RegistrationNumber`, `Model_Model_No`, and every other bike attribute unchanged. This is not a separate code path — it is simply the normal Edit form used with intent, and is documented as a deliberate business rule rather than a code feature (see Section 10.4).

`[INSERT IMAGE HERE — Customer Bike Edit Form]`
*Screenshot showing the Edit form being used to change the Customer dropdown for an ownership transfer, with VIN/Registration/Model fields visibly unchanged.*

---
### 8.15 New Motorbike

**Purpose:** Manage the dealership's own sellable motorbike inventory (as distinct from Customer_bike, which represents customer-owned vehicles).

**Fields (11) — the most field-rich module in the entire system:** `Model_Model_No`, `Color_Color` (both required FK dropdowns), `Year`, `VIN` (unique), `Price`, `Status` (Available/Sold), `Warranty_Months`, `EngineCC` (must be ≥ 1), `FuelType` (fixed 4-value select: Petrol/Diesel/Electric/Hybrid), `Transmission` (fixed 3-value select: Manual/Automatic/Semi-Automatic), `FuelTankCapacity` (must be > 0).

**Color dropdown detail:** because `Color`'s primary key *is* the color name string (Section 8.1), the Color dropdown for New Motorbike is built as `(Color, Color)` tuples — value and label are identical — which the shared `select_field` macro's `|string` comparison handles correctly for pre-selection on Edit.

**Two-card form layout:** "Bike Details" (Model, Color, Status, Year, VIN, Price) and "Technical Specifications" (EngineCC, FuelType, Transmission, FuelTankCapacity, Warranty), following the same two-card pattern introduced for Customer.

**Sold-bike warning banner:** if a bike's `Status` is `'Sold'`, opening its Edit form displays an explicit warning banner ("This motorbike has been sold. Edit with caution — changes may affect associated sales records.") — a UX safeguard against accidentally altering the specification of a bike that a Sale record already references.

**Status field — manually editable here, but authoritatively controlled elsewhere:** while the Status dropdown is technically editable on this module's own form, the *authoritative* Available↔Sold transition is actually driven by the Sale module (Section 8.17, Section 10.1) — creating, editing, or deleting a Sale is what correctly flips this value in normal operation.

### 8.16 Appointment (with Services and Stock Used)

**Purpose:** Schedule and manage service/repair appointments, track which Services were performed and which Stock items were consumed, and calculate an estimated total cost.

**Header fields (6):** `Customer_bike_BikeID`, `Employee_EmployeeID` (both required FKs), `Appointment_Date`, `Appointment_time` (a new `time_field` macro, built specifically for this module), `AppointmentType` (fixed 4-value select: Service/Repair/Inspection/Other), `Status` (fixed 6-value select: Pending/Confirmed/In Progress/Completed/Cancelled/No Show).

**Time-format conversion detail:** Supabase returns a `TIME` column as an `"HH:MM:SS"` string, while the HTML `<input type="time">` element expects `"HH:MM"`. The Edit route explicitly truncates this before rendering:

```python
def _truncate_time(time_str):
    if time_str and len(time_str) >= 5:
        return time_str[:5]
    return time_str or ''
```

**Locked statuses — the appointment's most important cross-cutting rule:** `Status` values `'Completed'` and `'Cancelled'` are treated as **locked**. Once an appointment reaches either status, its Services Used and Stock Used sections can no longer be added to, edited, or deleted — every relevant button in the view page checks `is_locked` and either renders a disabled, non-clickable control or performs a server-side redirect-with-error if the URL is visited directly:

```python
if record.get('Status') in LOCKED_STATUSES:
    flash_error(f'Cannot add services to a {record.get("Status")} appointment.')
    return redirect(url_for('appointment.view', appt_id=appt_id))
```

This same `is_locked` check was later extended to the Payment section of the appointment view (see Section 12) after an initial oversight left that one section clickable while the visually identical Services/Stock sections were correctly locked.

**Services Used (`appointment_service` bridge table):** the Add Service dropdown excludes services already linked to the appointment, so the same service cannot be added twice; the Quantity field is optional (matching the nullable `Quantity` column).

**Stock Used (`Appointment_Stock` bridge table):** similarly filters out already-used stock items from the Add Stock dropdown; Quantity here is required (matching the `NOT NULL` column).

**Estimated Cost Summary — automatic calculation:** the appointment's total cost is computed entirely server-side, by summing (Service cost × Quantity) across all linked services, plus (Stock unit price × Quantity) across all linked stock:

```python
service_total = sum(
    float(svc.get('_service_cost') or 0) * int(svc.get('Quantity') or 1)
    for svc in appt_services
)
stock_total = sum(
    float(stk.get('_stock_price') or 0) * int(stk.get('Quantity') or 0)
    for stk in appt_stock
)
appt_total = service_total + stock_total
```

This total updates automatically on every page load of the Appointment view — it is not stored anywhere, always recalculated live from the current Services Used and Stock Used rows, meaning adding, editing, or removing a service or stock item is immediately reflected the next time the view page is opened, with no separate "recalculate" step required.

**Stock deduction on completion — a business rule added after a defect was found (see Section 12):** marking an appointment's Status as `'Completed'` triggers a one-time deduction of every linked Stock item's `QOH`, guarded so it can only ever fire on the exact transition *into* Completed, never on a later re-save of an already-Completed appointment:

```python
if status_value == 'Completed' and previous_status != 'Completed':
    _deduct_stock_for_appointment(appt_id)
```

```python
def _deduct_stock_for_appointment(appt_id):
    used_rows = supabase.table('Appointment_Stock').select(
        'Stock_Stock_ID, Quantity'
    ).eq('Appointment_AppointmentID', appt_id).execute()

    for row in (used_rows.data or []):
        stock_id, qty_used = row.get('Stock_Stock_ID'), int(row.get('Quantity') or 0)
        if not stock_id or qty_used <= 0:
            continue
        current = supabase.table('Stock').select('QOH').eq(
            'Stock_ID', stock_id
        ).single().execute()
        new_qoh = max(0, int(current.data.get('QOH') or 0) - qty_used)
        supabase.table('Stock').update({'QOH': new_qoh}).eq(
            'Stock_ID', stock_id
        ).execute()
```

The `previous_status != 'Completed'` guard is what makes this safe: because the appointment's *prior* Status (fetched before the POST body overwrites it) is compared against the incoming value, saving an already-Completed appointment a second time (with no actual status change) correctly does nothing, preventing the same stock from being deducted twice.

**Delete protection:** deleting an appointment with an associated Payment record is blocked (see Section 8.18).

`[INSERT IMAGE HERE — Appointment View Page, Full]`
*Full-length screenshot of the Appointment view: header info, audit info, Services Used table, Stock Used table, Estimated Cost Summary cards, and the Payments section, in that order.*

### 8.17 Sale

**Purpose:** Record the sale of a specific New Motorbike unit to a Customer, and keep that motorbike's Available/Sold status synchronised automatically.

**Fields (5):** `Customer_CustomerID` (required FK), `New_MotorBike_NB_ID` (required FK, filtered to Available bikes only), `Employee_EmployeeID` (optional FK — the salesperson), `SaleDate`, `TotalAmount`.

**The core business rule of this module — automatic bike status synchronisation:**

- **On Create:** after the Sale row is inserted, the linked bike's `Status` is immediately set to `'Sold'`.
- **On Delete:** the linked bike's `Status` is reset to `'Available'`.
- **On Edit, if the selected bike is changed:** the *previous* bike is reset to `'Available'` and the *newly selected* bike is set to `'Sold'`; if the bike is left unchanged, no status update is triggered.

```python
def _set_bike_status(nb_id, status):
    try:
        supabase.table('New_MotorBike').update(
            {'Status': status}
        ).eq('NB_ID', nb_id).execute()
    except Exception:
        pass
```

```python
# inside edit()
if nb_id != original_nb_id:
    _set_bike_status(original_nb_id, 'Available')
    _set_bike_status(nb_id, 'Sold')
```

**Bike dropdown filtering — asymmetric between Create and Edit:** the Create form's Motorbike dropdown shows **only** bikes currently `Status = 'Available'`, since a Sold bike genuinely cannot be sold again. The Edit form's dropdown additionally re-admits the bike **currently linked to this specific sale** (even though its Status is `'Sold'`), specifically so the Edit form can correctly pre-select and display the bike the sale already refers to:

```python
if current_nb_id is not None:
    ids_in_options = {bid for bid, _ in bike_options}
    if current_nb_id not in ids_in_options:
        # fetch and re-insert the currently-linked (Sold) bike as an option
```

**Sale price auto-fill (a UX enhancement added after initial testing):** selecting a motorbike in the Create/Edit form automatically populates the `TotalAmount` field with that bike's `Price` from `New_MotorBike`, via a small client-side script that reads a JSON map of `{NB_ID: price}` passed into the template and rendered with Jinja's `tojson` filter:

```javascript
const bikePrices  = {{ bike_prices | tojson }};
const bikeSelect  = document.getElementById('New_MotorBike_NB_ID');
const amountField = document.getElementById('TotalAmount');

bikeSelect.addEventListener('change', function () {
    const selectedId = parseInt(this.value, 10);
    if (!isNaN(selectedId) && bikePrices[selectedId] !== undefined) {
        amountField.value = bikePrices[selectedId].toFixed(2);
    }
});
```

The value remains editable after auto-fill, so a negotiated price different from list price can still be entered manually.

**Delete protection:** deleting a Sale that has an associated Payment record is blocked (Section 8.18); deleting an unpaid Sale correctly resets its bike to Available and confirms this explicitly in the success message.

`[INSERT IMAGE HERE — Sale Create Form with Auto-Filled Price]`
*Screenshot showing a motorbike selected in the dropdown and the Total Amount field auto-populated with its price.*

### 8.18 Payment

**Purpose:** Record payments against either a Sale or an Appointment, correctly supporting full payment, deposits/partial payments, and instalments, without ever allowing the total paid to exceed what is actually owed.

This is the most business-logic-heavy module in the entire Admin Panel, and the one that went through the most rounds of correction after initial delivery (documented fully in Section 12). Its final, correct behaviour is:

**Reference type — one Payment always belongs to exactly one Sale OR one Appointment**, never both and never neither, enforced by the database `Payment_requires_reference` CHECK constraint (Section 6.5) and mirrored in application logic via a `reference_type` radio toggle on the Create form:

```html
<input type="radio" name="reference_type" value="sale" ...>
<input type="radio" name="reference_type" value="appointment" ...>
```

**Reference type is locked on Edit** — a Payment created against a Sale can never be edited into an Appointment payment, or vice versa, closing off a data-integrity loophole that was identified and fixed during development (Section 12):

```python
locked_ref_type = 'appointment' if current_appt_id else 'sale'
# ...
form_data['reference_type'] = locked_ref_type
# the Edit template renders reference_type as a hidden input plus a
# read-only visual indicator — no radio buttons are shown at all on Edit
```

**Balance calculation — the central business rule, applied identically to both Sales and Appointments:**

```
Remaining Balance = Total Amount Owed − Sum of All Existing Payments
```

For a Sale, "Total Amount Owed" is `Sale.TotalAmount`. For an Appointment, it is the live-calculated Estimated Cost Summary total (Section 8.16) — the two reference types were made to share the exact same conceptual rule, even though the "total owed" is sourced differently in each case.

```python
def _get_sale_total_paid(sale_id, exclude_payment_id=None):
    result = supabase.table('Payment').select(
        'PaymentID, AmountPaid'
    ).eq('Sale_SaleID', sale_id).execute()
    total = 0.0
    for p in (result.data or []):
        if exclude_payment_id and p.get('PaymentID') == exclude_payment_id:
            continue
        total += float(p.get('AmountPaid') or 0)
    return total
```

The `exclude_payment_id` parameter is essential on Edit: when editing an existing payment's amount, that payment's own current value must be excluded from the "already paid" total, otherwise a payment being edited would incorrectly count against its own remaining balance.

**Overpayment prevention — server-side, on every Create and every Edit:**

```python
remaining = max(0.0, sale_total - total_paid_so_far)
if amount_paid > remaining + 0.001:
    errors['AmountPaid'] = (
        f'Amount paid (Rs. {amount_paid:,.2f}) exceeds the remaining '
        f'balance of Rs. {remaining:,.2f} for this sale. ...'
    )
```

(The `+ 0.001` tolerance absorbs floating-point rounding rather than allowing a genuinely larger overpayment.) The identical structure is applied for the Appointment branch using `_get_appointment_total()` and `_get_appointment_total_paid()` in place of the Sale equivalents.

**Dropdown filtering — "still owed" rather than "never paid":** both the Sale and Appointment dropdowns on the Create form show only records with a remaining balance **greater than zero**, with the remaining amount shown directly in the option label:

```
SALE-7 — Jane Doe (2026-09-10) [Rs. 25,000.00 remaining]
APPT-#12 — ABC123 (2026-09-15) [Rs. 1,500.00 remaining]
```

Once fully paid, a Sale or Appointment disappears from the Create dropdown entirely — but, critically, the currently-linked reference is still re-admitted into the *Edit* form's dropdown, using the same `exclude_sale_id` / `exclude_appt_id` pattern as the Sale module's bike dropdown (Section 8.17), so an existing fully-paid payment can still be opened and edited.

**Live balance panel (client-side, backed by two dedicated JSON endpoints):** rather than only validating on submit, the form fetches and displays the Total/Already Paid/Remaining figures the moment a Sale or Appointment is selected, and again on page load if a value is already selected (e.g. returning to a failed-validation form):

```python
@bp.route('/sale-info/<int:sale_id>')
@login_required
def sale_info(sale_id):
    ...
    return jsonify({
        'sale_date': ..., 'total_amount': total,
        'total_paid': total_paid, 'remaining': remaining,
    })

@bp.route('/appointment-info/<int:appt_id>')
@login_required
def appointment_info(appt_id):
    ...
    return jsonify({'total_amount': total, 'total_paid': total_paid, 'remaining': remaining})
```

```javascript
function loadBalanceInfo(kind, refId) {
    let url = kind === 'sale'
        ? '/payments/sale-info/' + refId
        : '/payments/appointment-info/' + refId;
    if (isEdit && currentPayId) url += '?exclude_payment_id=' + currentPayId;
    fetch(url).then(r => r.json()).then(data => {
        showBalancePanel(data);   // populates Total / Already Paid / Remaining
    });
}
```

The `Amount Paid` field is also auto-filled with the remaining balance (editable, so a smaller deposit can still be entered manually) and given an HTML `max` attribute matching the remaining balance as an additional (non-authoritative) client-side hint — the server-side check remains the actual enforcement.

**Duplicate-submission protection:** a one-time server-generated token is embedded as a hidden form field on GET and consumed on the first valid POST, guarding against the same payment being created twice from rapid double-clicks:

```python
if request.method == 'GET':
    form_token = str(uuid.uuid4())
    session['payment_form_token'] = form_token
...
if session_token is not None and (
    not submitted_token or submitted_token != session_token
):
    flash_error('This payment appears to have already been submitted. ...')
    return redirect(url_for('payment.index'))
if session_token is not None:
    session.pop('payment_form_token', None)
```

This is paired with a client-side submit-button disable-on-click:

```javascript
payForm.addEventListener('submit', function () {
    if (submitBtn.disabled) return;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i>Processing...';
});
```

**Appointment "Add Payment" pre-fill:** clicking "Add Payment" from an Appointment's own view page pre-selects that appointment on the Payment Create form via a query parameter, rather than dropping the user into a blank form where the appointment has to be found and re-selected manually:

```python
prefill_appt = request.args.get('prefill_appt', type=int)
if prefill_appt:
    form_data = {
        'reference_type': 'appointment',
        'Appointment_AppointmentID': str(prefill_appt),
    }
```

```html
<a href="{{ url_for('payment.create', prefill_appt=appt_id) }}">Add Payment</a>
```

**Table display:** the Payment list shows Payment ID, a resolved Reference (`SALE-7` or `APPT-#12`, with a colour-coded type badge), the payment's `PaymentType` (Full Payment / Deposit / Instalment) shown once via a single colour-coded badge, date, amount, and method.

`[INSERT IMAGE HERE — Payment Create Form with Live Balance Panel]`
*Screenshot of the Record Payment form with a Sale selected, showing the populated Sale Total / Already Paid / Remaining Balance panel.*

`[INSERT IMAGE HERE — Payment List Table]`
*Screenshot of the Payments list showing the Reference column with its colour-coded Sale/Appointment badge and the single Type badge.*

---

### 8.19 PO_NewMotorBike (Motorcycle Purchase Ordering)

**Purpose:** Record that a specific `New_MotorBike` unit was procured through a `PurchaseOrder`, at what buying price, and when it was received — closing the gap identified in Section 6.10, where `PurchaseOrder` could previously only account for spare-part procurement via `PurchaseOrderItem`.

**No separate sidebar entry.** Like `PurchaseOrderItem`, `PO_NewMotorBike` rows are managed entirely inside the existing Purchase Order module, under a new "Motorcycles Ordered" section on the PO detail (`view()`) page, sitting alongside the existing "Line Items" section rather than replacing or restructuring it.

**Two-mode "Add Motorcycle" form**, mirroring the existing two-path receiving pattern used for spare parts (Section 10.5) and reusing the same `receive-mode-selector` radio-toggle JavaScript already registered in `admin.js`:

- **Existing Motorcycle Record** — select a `New_MotorBike` that has not yet been linked to any Purchase Order, from a dropdown built by excluding every `NB_ID` already present in `PO_NewMotorBike`.
- **New Motorcycle Record** — create the `New_MotorBike` row at the same time as linking it to the PO. Rather than duplicating New Motorbike's own field validation and dropdown-building logic, this path imports and reuses it directly from the `new_motorbike` module:

```python
from app.modules.new_motorbike.routes import (
    _validate_form as _validate_new_motorbike_fields,
    _get_form_options as _get_new_motorbike_dropdown_options,
    FUEL_TYPE_OPTIONS as NB_FUEL_TYPE_OPTIONS,
    TRANSMISSION_OPTIONS as NB_TRANSMISSION_OPTIONS,
    STATUS_OPTIONS as NB_STATUS_OPTIONS,
)
```

Both modes converge on the same `PurchaseOrderItem`-style structure: after the motorcycle is resolved (either selected or newly created), a single `PO_NewMotorBike` row is inserted with the buying price and, if already known, the date received.

**Routes** (URL pattern `/<po_id>/motorbikes/...`, within the existing `purchase_order` blueprint):

- `add_motorbike` — the two-mode form above. Blocked with a flash error if the PO's `Status` is `Received` or `Cancelled`.
- `edit_motorbike` — edits only `BuyingPrice`/`DateReceived` on an already-linked motorcycle; the motorcycle link itself cannot be changed after creation. Also blocked on a Received/Cancelled PO.
- `delete_motorbike` — unlinks a motorcycle from the PO (does not delete the `New_MotorBike` record itself).

**Enrichment for display:** `_enrich_po_motorbikes()` resolves each linked motorcycle's Model/Brand chain into a display label (`Brand_Name Model_Description (Year)`), plus its VIN and current Available/Sold status, using the same lookup-dictionary pattern used throughout the codebase (Section 13).

**Duplicate-purchase protection:** the `PO_NewMotorBike_unique_bike` constraint (Section 6.10) means attempting to link a motorcycle already tied to a different PO fails at the database level; the route catches this and surfaces `"This motorcycle is already linked to another purchase order."` — though, as noted in Section 6.10, this same error text can currently also (incorrectly) surface for an unrelated VIN-uniqueness failure in the "New Motorcycle Record" path, which is documented as an open item rather than silently left unexplained.

**Template:** `modules/purchase_order/motorbike_form.html`, shared by the add and edit flows via the same `is_edit` conditional pattern used by every other module's form template.

`[INSERT IMAGE HERE — Purchase Order Detail Page, Motorcycles Ordered Section]`
*Screenshot of a Purchase Order's detail page showing the new "Motorcycles Ordered" table alongside the existing Line Items table.*

---
## 9. UI / UX Design

### 9.1 Layout and Visual Identity

The Admin Panel deliberately avoids an unstyled, generic Bootstrap look. A small custom design system was layered on top of Bootstrap 5 via CSS variables defined once in `admin.css`:

```css
:root {
    --sidebar-width: 260px;
    --sidebar-bg: #1a2332;
    --accent: #e67e22;
    --accent-hover: #d35400;
    --content-bg: #f0f2f5;
    --card-bg: #ffffff;
    --text-primary: #1a2332;
    --text-secondary: #6b7280;
    --text-muted: #9ca3af;
    --border-color: #e5e7eb;
    --border-radius: 8px;
    --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
```

A dark navy sidebar (`#1a2332`) paired with a single warm orange accent (`#e67e22`) forms the panel's entire visual identity — used consistently for active nav items, primary buttons, badges, and the dashboard's phase indicator. The Inter font (loaded from Google Fonts) was chosen deliberately over the browser default sans-serif for a more professional, "real product" feel appropriate for a business administration system, per the explicit design brief given at the start of Phase 2: simple, professional, modern, no unnecessary gradients or decorative elements, and no generic-template appearance.

### 9.2 Sidebar and Navigation

The sidebar is fixed to the left, grouped into labelled sections that grew as modules were added:

- **Dashboard**
- **Management** — Colors, Categories, Brands, Models, Spare Parts, Stock, Services, Roles, Employees, Suppliers, Compatibility
- **Purchasing** — Purchase Orders
- **Customers** — Customers, Customer Bikes
- **Inventory** — New Motorbikes
- **Appointments** — Appointments
- **Transactions** — Sales, Payments

Each new module's sidebar link was added incrementally, task by task, always using the same active-state pattern based on the current Flask Blueprint:

```html
<a href="{{ url_for('color.index') }}"
   class="nav-link {% if request.blueprint == 'color' %}active{% endif %}">
```

**Sidebar scrolling bug and fix:** as more sections were added, the sidebar grew taller than the viewport and became unreachable without the browser's zoom-out shortcut. The root cause was that `.sidebar` used `min-height: 100vh` (which lets the element grow past the viewport rather than clip it) instead of a fixed `height: 100vh` combined with `overflow-y: auto`. The fix was a single property change:

```css
/* BEFORE */
.sidebar { min-height: 100vh; ... }

/* AFTER */
.sidebar { height: 100vh; ... }   /* overflow-y: auto was already present */
```

This is documented further as a specific incident in Section 12.

### 9.3 Dashboard

The dashboard shows a responsive grid of stat cards, one per module, each showing a live Supabase `count='exact'` record count, an icon, a short description, and a "View all" link into that module:

```python
def _get_dashboard_counts():
    queries = [('color', 'Color'), ('category', 'Category'), ...]
    counts = {}
    for key, table_name in queries:
        try:
            result = supabase.table(table_name).select('*', count='exact').execute()
            counts[key] = result.count if result.count is not None else 0
        except Exception:
            counts[key] = 0
    return counts
```

Each individual table's count query is wrapped in its **own** `try/except`, so a single failing query (e.g. a table that is briefly unreachable) never prevents the other 16 cards from rendering — an explicit resilience decision made at the time the dashboard was first built.

The dashboard grid is responsive via Bootstrap's column classes (`col-xl-3 col-lg-4 col-sm-6`), giving 4 cards per row on large screens down to 1 per row on mobile, and every new module added a new card + a new entry in `_get_dashboard_counts()` as it was built.

### 9.4 Shared Components

Built once in Task 06 and reused, unmodified, by all subsequent CRUD modules — this reuse is one of the project's most significant time-saving architectural decisions:

- **`search_bar()` / `data_table()`** (`components/table.html`) — a GET-based search form plus a table wrapper that shows a friendly empty state (inbox icon + message) when there are zero records, instead of an empty `<table>`.
- **`text_field / number_field / select_field / textarea_field / readonly_field / date_field / time_field`** (`components/form_field.html`) — every form input type used anywhere in the system, all sharing the same label/required-asterisk/error-message/help-text structure.
- **`delete_modal()`** (`components/modal_confirm.html`) — one Bootstrap modal per page, populated dynamically via `data-delete-url` / `data-record-name` attributes on each row's Delete button and a shared JavaScript listener (Section 13).
- **`pagination_controls()`** (`components/pagination.html`) — "Showing X to Y of Z records" plus page links, only rendered when more than one page exists.
- **`info_alert() / warning_alert()`** (`components/alert.html`) — inline banners distinct from flash messages, used for e.g. active-search-term indicators.

### 9.5 Responsive and Scrolling Behaviour

Below 992px width, the sidebar collapses off-screen (`transform: translateX(-100%)`), a hamburger toggle appears in the header, and a dark overlay appears behind the sidebar when opened on mobile — all controlled by a small shared script in `admin.js` and CSS media queries in `admin.css`.

### 9.6 Design Evolution

Several UI elements were introduced only when the module that needed them was built, rather than up front:

- Status **badges** (color-coded by category) were introduced with Purchase Order status (Pending / Partially Received / Received / Cancelled), then reused with variations for Appointment status/type and New MotorBike Available/Sold status, then Payment reference-type and payment-type badges.
- The **receive-mode radio selector** (used in Purchase Order receiving and later reused, visually, for the Payment reference-type toggle) was designed as a two-card side-by-side radio group rather than a plain `<select>`, specifically because the two paths (existing stock vs new stock; Sale vs Appointment) represent meaningfully different subsequent form sections, not just different values of the same field.
- A **balance information panel** (Sale Total / Already Paid / Remaining Balance) was added to the Payment form specifically to solve the ambiguity around what "Amount Paid" means once partial payments were introduced (Section 10.2) — populated live via JavaScript `fetch()` calls rather than a full page reload.

`[INSERT IMAGE HERE — Dashboard Screenshot]`
*Full dashboard view showing the welcome row, phase badge, and the complete grid of module count cards.*

`[INSERT IMAGE HERE — Mobile / Collapsed Sidebar View]`
*Screenshot at a narrow viewport width showing the hamburger toggle and the sidebar overlay.*

---
## 10. Business Logic

### 10.1 Sale ↔ New Motorbike Status Linkage

A `New_MotorBike.Status` is either `'Available'` or `'Sold'` (enforced by a database `CHECK` constraint, Section 6.5). The Admin Panel keeps this in sync with the `Sale` table automatically, at three points:

**On Sale create** — immediately after the `Sale` row is inserted, the linked bike is marked Sold:

```python
supabase.table('Sale').insert({...}).execute()
_set_bike_status(nb_id, 'Sold')
```

**On Sale edit, if the bike selection changes** — the *old* bike is reset to Available and the *new* bike is marked Sold:

```python
if nb_id != original_nb_id:
    _set_bike_status(original_nb_id, 'Available')
    _set_bike_status(nb_id, 'Sold')
```

**On Sale delete** — the linked bike is reset to Available:

```python
supabase.table('Sale').delete().eq('SaleID', sale_id).execute()
if nb_id:
    _set_bike_status(nb_id, 'Available')
flash_success(f'Sale SALE-{sale_id} was deleted and the motorbike has been reset to Available.')
```

The Sale Create form's Motorbike dropdown is filtered to show **only** bikes with `Status = 'Available'`, sourced live from the database on every page load. The Edit form's dropdown additionally re-admits the *currently linked* bike (even though its status is Sold) so the existing selection can still render correctly — implemented by inserting that one bike back into the options list if it would otherwise have been filtered out.

The database's `Sale_unique_bike` UNIQUE constraint (Section 6.5) is the ultimate backstop guaranteeing one bike can never be linked to two Sale rows, independent of whether the application-layer status flag is ever somehow out of sync.

**Price auto-fill:** selecting a motorbike in the Sale Create/Edit form automatically populates the Total Amount field from that bike's `Price` in `New_MotorBike`, via a small inline script that reads a JSON map of `{NB_ID: Price}` passed from the Flask route into the template:

```javascript
bikeSelect.addEventListener('change', function () {
    const selectedId = parseInt(this.value, 10);
    if (!isNaN(selectedId) && bikePrices[selectedId] !== undefined) {
        amountField.value = bikePrices[selectedId].toFixed(2);
    }
});
```

The field remains editable afterward, so staff can still override it for a negotiated price.

### 10.2 Payment Rules (Sale and Appointment)

This is the most heavily revised piece of business logic in the entire project, refined over multiple rounds of testing and correction.

**What `AmountPaid` represents:** the actual cash amount received in *this specific* payment transaction — not the sale/appointment total, and not the cumulative amount paid to date. A Sale or Appointment can have **multiple** Payment rows, each representing one instalment.

**Balance calculation**, computed fresh from the database on every relevant request (never cached or stored):

```
Total       = Sale.TotalAmount   (or the calculated Appointment total — see 10.3)
Already Paid = SUM(Payment.AmountPaid) for all payments linked to this Sale/Appointment
              (excluding the payment currently being edited, if editing)
Remaining   = MAX(0, Total − Already Paid)
```

```python
def _get_sale_total_paid(sale_id, exclude_payment_id=None):
    result = supabase.table('Payment').select('PaymentID, AmountPaid').eq('Sale_SaleID', sale_id).execute()
    total = 0.0
    for p in result.data or []:
        if exclude_payment_id and p.get('PaymentID') == exclude_payment_id:
            continue
        total += float(p.get('AmountPaid') or 0)
    return total
```

**Overpayment is blocked server-side**, with a specific, figures-quoting error message rather than a generic rejection:

```python
if amount_paid > remaining + 0.001:
    errors['AmountPaid'] = (
        f'Amount paid (Rs. {amount_paid:,.2f}) exceeds the remaining '
        f'balance of Rs. {remaining:,.2f} for this sale. '
        f'The sale total is Rs. {sale_total:,.2f} and '
        f'Rs. {total_paid_so_far:,.2f} has already been paid.'
    )
```

(The small `0.001` tolerance exists to absorb floating-point rounding noise, not to permit genuine overpayment.)

**A Sale or Appointment with zero remaining balance disappears from the "select a reference" dropdown** on the Payment Create form, preventing further payments once fully paid — while a *partially*-paid reference remains selectable, with its dropdown label showing the live remaining balance:

```
SALE-14 — J. Ramgoolam (2026-09-10) [Rs. 45,000.00 remaining]
```

**Reference type is locked once a Payment exists** — an existing Sale payment cannot be edited into an Appointment payment, or vice versa. This is enforced by never rendering the reference-type radio buttons on the Edit form at all; instead, a hidden field carries the original, unchangeable type:

```python
locked_ref_type = 'appointment' if current_appt_id else 'sale'
```

```html
<input type="hidden" name="reference_type" value="{{ locked_ref_type }}">
```

**Why Appointment payments originally behaved differently from Sale payments, and the fix:** a UNIQUE constraint (`unique_appointment_payment`) originally limited an Appointment to exactly one Payment row — meaning an Appointment vanished from the dropdown after its *first* payment, whether or not that payment covered the full amount, which made partial/deposit payments impossible for Appointments even though they already worked correctly for Sales. Once this inconsistency was identified, the constraint was dropped (Section 6.9) and the Appointment side of the payment logic was rewritten to mirror the Sale side exactly — computing an Appointment's own total (Section 10.3), its own cumulative paid amount, and its own remaining balance, using the identical "disappears only at zero remaining" rule.

**Duplicate rapid-submission protection** — described fully with code in Section 13 — uses a one-time session token embedded as a hidden form field, checked and consumed on the server before the insert is attempted, combined with immediately disabling the Confirm Payment button client-side on first click.

### 10.3 Appointment Completion and Stock Deduction

**Estimated cost calculation** — an Appointment's total cost is computed, live, from its linked services and stock usage, never stored as a static column:

```python
service_total = sum(
    float(svc.get('_service_cost') or 0) * int(svc.get('Quantity') or 1)
    for svc in appt_services
)
stock_total = sum(
    float(stk.get('_stock_price') or 0) * int(stk.get('Quantity') or 0)
    for stk in appt_stock
)
appt_total = service_total + stock_total
```

Note the differing default multiplier: a service with no recorded `Quantity` is treated as quantity **1** (a service performed once), while stock with no recorded `Quantity` contributes **0** to the total (a stock-usage row is only meaningful if a count is actually recorded, matching the database's `NOT NULL` constraint on `Appointment_Stock.Quantity`).

**Stock deduction on completion** — the most significant piece of Appointment business logic, and one that was **missing entirely** for a period of development (documented as a distinct bug in Section 12). Neither adding stock to an appointment, nor marking it Completed, originally touched `Stock.QOH` at all — the `Appointment_Stock` table only ever *recorded* what was used, without ever consuming it from inventory.

The fix decrements `Stock.QOH` exactly once, at the precise moment an appointment's `Status` transitions **into** `'Completed'` — guarded by comparing the *previous* status (fetched before the update) against the newly submitted one:

```python
def _deduct_stock_for_appointment(appt_id):
    used_rows = supabase.table('Appointment_Stock').select(
        'Stock_Stock_ID, Quantity'
    ).eq('Appointment_AppointmentID', appt_id).execute()

    for row in used_rows.data or []:
        stock_id = row.get('Stock_Stock_ID')
        qty_used = int(row.get('Quantity') or 0)
        if not stock_id or qty_used <= 0:
            continue
        current = supabase.table('Stock').select('QOH').eq(
            'Stock_ID', stock_id
        ).single().execute()
        current_qoh = int(current.data.get('QOH') or 0)
        new_qoh = max(0, current_qoh - qty_used)
        supabase.table('Stock').update({'QOH': new_qoh}).eq('Stock_ID', stock_id).execute()
```

```python
# inside Appointment edit():
previous_status = record.get('Status')       # fetched BEFORE this POST's changes
supabase.table('Appointment').update({..., 'Status': status_value}).eq(...).execute()

if status_value == 'Completed' and previous_status != 'Completed':
    _deduct_stock_for_appointment(appt_id)
```

The `previous_status != 'Completed'` guard is what makes this safe to call every time the Edit form is submitted: re-saving an already-Completed appointment (e.g. to fix a typo elsewhere on the form) will never trigger a second deduction, because `previous_status` will already read `'Completed'` on that subsequent save.

**Locked statuses** — `Completed` and `Cancelled` appointments cannot have services or stock added, edited, or removed (`LOCKED_STATUSES = ('Completed', 'Cancelled')`, checked at the top of every services/stock-mutating route), and the Payment section's "Add Payment" button is likewise disabled once an appointment is either locked or its remaining balance reaches zero.

### 10.4 Customer / Customer Bike Duplication Prevention and Ownership Transfer

**Duplicate customer prevention:** `NIC` and `PhoneNumber` are UNIQUE at the database level (Section 6.8); attempting to insert or update a Customer with a clashing value produces a specific, field-relevant flash message rather than a generic database error.

**Duplicate vehicle prevention:** `VIN` and `RegistrationNumber` on `Customer_bike` are similarly UNIQUE.

**Ownership transfer:** when a physical motorbike changes owner, the correct action is to **edit the existing `Customer_bike` row's `Customer_CustomerID`** field to point at the new owner — not to create a second `Customer_bike` row for the same vehicle (which the UNIQUE VIN/Registration constraints would reject outright if attempted). This was confirmed and tested explicitly as the intended workflow: VIN, Registration Number, Model, and all other vehicle details remain untouched during a transfer; only the customer link changes.

**Cross-table VIN — explicitly not a duplication bug.** It was raised as a question whether a `Customer_bike` and a `New_MotorBike` could legitimately carry the same VIN, and confirmed that this is correct, expected behaviour rather than a defect: `New_MotorBike` represents dealer sales inventory, `Customer_bike` represents a customer-owned, service-eligible vehicle, and once the dealership itself sells a bike, the same physical VIN correctly exists in both tables — one row describing it as inventory (now marked Sold), one describing it as a serviceable customer asset. No cross-table uniqueness constraint was added, by design.

### 10.5 Purchase Order Receiving Workflow

Reflecting the supervisor's stated rule that ordering references a spare part, not a stock row (Section 6.4), the receiving process branches into exactly two paths, both triggered from a single "Receive" action on a `PurchaseOrderItem` still in `'Ordered'` status:

**Path A — a matching stock variant already exists:** the admin selects the existing `Stock` row from a dropdown (populated only with stock rows for the same spare part), and the received quantity is **added to** that row's existing `QOH`:

```python
existing_result = supabase.table('Stock').select('QOH').eq('Stock_ID', stock_id_to_link).single().execute()
current_qoh = existing_result.data.get('QOH', 0)
supabase.table('Stock').update({'QOH': current_qoh + qty_recv}).eq('Stock_ID', stock_id_to_link).execute()
```

**Path B — no matching stock variant exists:** a brand-new `Stock` row is created with `QOH` set directly to the received quantity:

```python
new_stock_result = supabase.table('Stock').insert({
    'Spare_Parts_SP_id': sp_id, 'Brand_Brand_ID': new_brand_id,
    'Size': new_size, 'QOH': qty_recv,
    'S_Price': new_price, 'Warranty': new_warranty,
}).execute()
stock_id_to_link = new_stock_result.data[0]['Stock_ID']
```

In both paths, the `PurchaseOrderItem` row is then updated with `Quantity_Received`, `DateReceived`, the resolved `Stock_Stock_ID`, and `Status = 'Received'`.

**PO Status auto-update:** after any item is received, the parent `PurchaseOrder`'s own `Status` is recalculated across *all* its line items — `'Received'` if every item has been received, `'Partially Received'` if some but not all have, and left unchanged (`'Pending'`) if none have yet:

```python
received = sum(1 for i in items if i.get('Status') == 'Received')
if received == total:
    new_status = 'Received'
elif received > 0:
    new_status = 'Partially Received'
else:
    return   # leave PO status as Pending
```

Items can only be added to a PO whose status is not already `'Received'` or `'Cancelled'`, and a received item can never be deleted or edited (doing so would silently desynchronise `Stock.QOH` from what was actually recorded as received).

### 10.6 Stock ↔ Model Compatibility

As designed in Section 6.3, a `Compatibility` row links one `Stock` variant to one `Model`, with an optional `Year_From`/`Year_To` range. The Admin Panel's Create form supports selecting **multiple Models in one submission** against a single Stock item and year range — implemented as a multi-select `<select multiple>` control, producing one `Compatibility` insert per selected Model:

```python
for model_no_str in selected_model_nos:
    model_no = int(model_no_str)
    supabase.table('Compatibility').insert({
        'Stock_Stock_ID': stock_id, 'Model_Model_No': model_no,
        'Year_From': year_from, 'Year_To': year_to,
    }).execute()
```

Duplicate rows (same Stock, Model, and year range) are individually caught per-insert and silently skipped with a running count reported back to the user ("3 compatibility records added, 1 duplicate skipped"), rather than aborting the whole batch on the first conflict. The Edit form, by contrast, remains single-select — editing one specific existing record.

`[INSERT IMAGE HERE — Business Logic Flow: Sale to Stock/Motorbike Status]`
*A flow diagram: Create Sale → Insert Sale row → Update New_MotorBike.Status = 'Sold' → Bike removed from future Sale dropdowns.*

`[INSERT IMAGE HERE — Business Logic Flow: Appointment Completion → Stock Deduction]`
*A flow diagram: Edit Appointment (Status → Completed) → previous_status check → _deduct_stock_for_appointment() → Stock.QOH reduced per line item.*

`[INSERT IMAGE HERE — Business Logic Flow: Payment Balance Calculation]`
*A flow diagram showing Total, SUM(existing payments), Remaining = Total − Paid, and the two outcomes: still selectable (Remaining > 0) vs removed from dropdown (Remaining = 0).*

---
## 11. Development History (Chronological)

This section presents the project's actual build order, task by task, as it happened.

**Stage 0 — Prior to this report's scope.** Initial Study completed; Python + Flask chosen as the backend language/framework specifically for beginner accessibility; original ERD modelled in Oracle SQL Developer Data Modeler.

**Stage 1 — Technology pivot (start of documented work).** The developer proposed switching the database layer from a planned local MySQL/phpMyAdmin setup to Supabase, and separately considered switching the frontend entirely to React/Next.js. After weighing the options — beginner-friendliness, timeline risk ahead of the project's status-checkpoint prototype demo, and the fact that a full React/Next.js rewrite would introduce an entirely new language and paradigm on top of an already-submitted Initial Study — the decision made was **Option B**: keep Flask (Python) as the backend/frontend-rendering layer, and adopt only Supabase as the database and (later) authentication provider. This avoided introducing a second programming language while still gaining Supabase's hosted Postgres, Table Editor GUI, and built-in Auth/RLS.

**Stage 2 — Phase 1 database setup (Task 1 of the SQL work).** The Oracle DDL was reviewed line by line and converted to PostgreSQL-correct SQL for the 10 Phase 1 tables, with every correction explained before being applied (see Section 6.2) rather than being silently changed. The shared `set_audit_fields()` trigger function and per-table triggers were created in the same script. Verification queries (confirming tables, PKs, FKs, and that audit fields auto-populate on insert/update) were run and confirmed working before proceeding.

**Stage 3 — Admin Panel foundation (Tasks 01–06).** A structured, incremental plan was set: rather than generating the whole application at once, each task covered one focused unit of work, always ending with the developer testing it before the next task was generated. In order: Flask project setup and Supabase connection (Task 01); documentation files (Task 02); full folder/Blueprint scaffolding with placeholder routes (Task 03); the Admin layout — sidebar, header, CSS design system (Task 04); the Dashboard with live count cards (Task 05); and the five shared Jinja macro components — table, form fields, delete modal, alerts, pagination (Task 06) — built once and reused by every module from that point on.

**Stage 4 — Phase 1 CRUD modules (Tasks 07–16).** Each of the 10 Phase 1 tables received its own full CRUD module, built in dependency order (simplest, no-FK tables first): Color (07), Category (08), Role (09), Supplier (10), Brand (11), Service (12), Employee (13), Model (14), Spare Parts (15), Stock (16). Each task's prompt explicitly named what pattern from the *previous* module was being reused (e.g. Role introduced the first numeric field; Supplier introduced email validation and a textarea; Employee introduced the first two-FK-dropdown form with a self-reference), so complexity was introduced one concept at a time rather than all at once.

**Stage 5 — Authentication (Task 17).** Deferred deliberately until every CRUD module above was working, then implemented as one focused unit: UNIQUE constraints added to relevant master-data tables, `anon` grants replaced with `authenticated` grants + RLS policies across all 10 Phase 1 tables, a Supabase Auth user created, and the previously pass-through `login_required` decorator given its real session-checking implementation — all without needing to touch any of the 10 already-written CRUD modules' route files.

**Stage 6 — Supervisor ERD review and Compatibility/Purchase Order redesign (Tasks 18–20).** The supervisor's feedback on the ERD (Section 6.3, 6.4) required: dropping `Spare_Parts.Model_Model_No`, making `Stock.Size` nullable, adding the new `Compatibility` table, and redesigning Purchase Order around `PurchaseOrderItem` (referencing Spare_Parts, not Stock, at order time). This required a corresponding Admin Panel fix to the already-built Spare Parts module (removing its now-invalid Model dropdown) before the new Compatibility module (Task 18) and Purchase Order + receiving-workflow modules (Tasks 19–20) were built.

**Stage 7 — Phase 3 transactional tables (Tasks 21–26).** The remaining schema (Customer, Customer_bike, New_MotorBike, Appointment + bridge tables, Sale, Payment) was created in one SQL script, followed by one Admin Panel task per table: Customer (21), Customer Bike (22), New Motorbike (23), Appointment with Services/Stock management (24), Sale with automatic motorbike status linkage (25), Payment (26).

**Stage 8 — Post-implementation hardening and bug-fixing (multiple rounds, undated relative to task numbers).** After the core Task 26 build, several rounds of targeted fixes were made in response to issues found during hands-on testing, documented in full in Section 12: sidebar scrolling, Sale price auto-fill, Customer/Customer_bike duplicate-data protection, the Payment balance panel and overpayment logic (built, then substantially reworked once the Sale-vs-Appointment inconsistency was found), the Appointment View Jinja `TemplateSyntaxError`, a Flask duplicate-route-registration crash, the Appointment stock-deduction gap, and a duplicate Payment Type display issue.

**Stage 9 — Documentation (this report).** Produced at the point where all modules, authentication, RLS, and business logic fixes above were confirmed working, covering the project from its Stage 1 pivot through to the present state.

**Stage 10 — Post-report supervisor review addition: PO_NewMotorBike (motorcycle purchase ordering).** A further supervisor review, conducted after the documentation above was produced, identified that the Purchase Order module could record procurement of spare parts (`PurchaseOrderItem`) but had no equivalent for motorcycle units. The `PO_NewMotorBike` bridge table (Section 6.10) and its Admin Panel integration into the existing Purchase Order module — a two-mode Add Motorcycle form, edit/delete routes, and a new "Motorcycles Ordered" section on the PO detail page (Section 8.19) — were added in response. Two open items were identified during this addition's review and are documented, unresolved, in Section 6.10, Section 8.19, and Section 12, rather than presented as already fixed.

`[INSERT IMAGE HERE — Development Timeline / Gantt-Style Chart]`
*A horizontal timeline chart showing Stages 1 through 10 above, with the task numbers (01–26) marked along it.*

---
## 12. Errors, Problems, and Solutions

This section documents every significant error or defect encountered during development, in the order they occurred, including problems that were later fixed and are recorded here for completeness rather than omitted.

---

### 12.1 Jinja2 `TemplateSyntaxError: Encountered unknown tag 'endblock'`

**What happened:** After successfully creating an Appointment, clicking **View** produced a Jinja2 crash instead of the appointment detail page.

**Error:**
```
jinja2.exceptions.TemplateSyntaxError: Encountered unknown tag 'endblock'.
File: app/templates/modules/appointment/view.html, line 326
```

**File/function involved:** `app/templates/modules/appointment/view.html`, rendered from `app/modules/appointment/routes.py`'s `view()` function.

**Cause:** When the Payment section was added to the Appointment view template in a later task, it was appended **after** an existing `{% endblock %}` that had already closed `{% block content %}`. The new Payment `<div>` markup was therefore left dangling outside any Jinja block, and a second, now-orphaned `{% endblock %}` at the very end of the file (the one intended to close `content`) had nothing left to close, producing the "unknown tag" error.

**Investigation:** the full block structure of the file was reviewed from `{% extends %}` down to the final `{% endblock %}`, checking each `{% block %}` / `{% if %}` / `{% for %}` against its matching closer, rather than deleting the reported line blindly (which would have removed the wrong block boundary and broken the page a different way).

**Fix:** the premature `{% endblock %}` — the one sitting directly after `{{ delete_modal() }}` and before the Payment section's markup — was removed, so the Payment section became part of `{% block content %}` as intended, leaving exactly one `{% endblock %}` at the true end of the file.

```html
<!-- BEFORE (incorrect) -->
{{ delete_modal() }}

{% endblock %}          <!-- closes content too early -->

<!-- Payment -->
<div class="admin-card"> ... </div>


<!-- AFTER (fixed) -->
{{ delete_modal() }}

<!-- Payment -->
<div class="admin-card"> ... </div>

{% endblock %}          <!-- now the single, correctly placed closer -->
```

**Result:** Create → View → Edit for Appointments all confirmed working afterward, including the Payment section rendering correctly within the same page.

---

### 12.2 Flask `AssertionError: View function mapping is overwriting an existing endpoint function: payment.sale_info`

**What happened:** After a round of edits to the Payment module (adding the `sale_info` JSON endpoint and Payment form-token protection), the Flask app failed to start at all.

**Error:**
```
File "app/__init__.py", line 81, in create_app
    app.register_blueprint(payment_bp, url_prefix='/payments')
...
AssertionError: View function mapping is overwriting an existing endpoint function: payment.sale_info
```

**File/function involved:** `app/modules/payment/routes.py` and/or `app/modules/payment/__init__.py`.

**Cause:** the `sale_info` route (`@bp.route('/sale-info/<int:sale_id>')`) had ended up defined **twice** on the same Blueprint — most likely because a previous manual edit had pasted route code directly into `__init__.py` in addition to the existing `from app.modules.payment import routes` import, causing the same function to be registered on the Blueprint twice during app startup.

**Investigation:** rather than trying to diff the exact duplicate location from a partial file excerpt, the safer and more reliable fix was to overwrite both files completely with known-clean, single-definition content, and then explicitly verify (via a project-wide search for `def sale_info` and for `Blueprint('payment'`) that each pattern occurred **exactly once** across the whole codebase before restarting the server.

**Fix:**
- `app/modules/payment/__init__.py` was reduced to exactly the four standard Blueprint-registration lines (Blueprint creation + one import of `routes`) — nothing else.
- `app/modules/payment/routes.py` was replaced in full with a version containing each route (`sale_info`, `index`, `create`, `edit`, `delete`) defined exactly once.

**Result:** confirmed via `Ctrl+Shift+F` search across the project returning exactly one match for `def sale_info` (in `routes.py`) and exactly one match for `Blueprint('payment'` (in `__init__.py`); the server then started cleanly and the `/payments/sale-info/<id>` endpoint responded correctly.

---

### 12.3 Sidebar not scrollable — content unreachable without browser zoom

**What happened:** as more sidebar sections were added (Management → Purchasing → Customers → Inventory → Appointments → Transactions), the sidebar became taller than the browser viewport, and lower items (e.g. Payments) could only be reached by pressing `Ctrl -` to zoom the whole page out.

**File involved:** `app/static/css/admin.css`, the `.sidebar` rule.

**Cause:** `.sidebar` was declared with `min-height: 100vh`. `min-height` allows an element to **grow taller** than that value if its content requires it — it does not clip content to the viewport — so `overflow-y: auto` (which was already present) never actually had anything to scroll *within*, because the box itself just kept expanding downward past the visible screen.

**Fix:** changed `min-height: 100vh` to a fixed `height: 100vh`, which caps the sidebar's box at exactly the viewport height and lets the pre-existing `overflow-y: auto` finally take effect:

```css
/* BEFORE */
.sidebar { width: var(--sidebar-width); min-height: 100vh; ... }

/* AFTER */
.sidebar { width: var(--sidebar-width); height: 100vh; ... }
```

**Result:** confirmed the sidebar scrolls smoothly at normal 100% browser zoom, with all modules (including the newest, Payments) reachable without any zoom adjustment.

---

### 12.4 Payment amount fields (Sale Total / Already Paid / Remaining Balance) not updating dynamically

**What happened:** the balance-information panel shown below the Sale dropdown on the Payment form displayed static, non-updating values regardless of which Sale was selected, whether a deposit had already been made, or whether the amount field was edited.

**File involved:** `app/templates/modules/payment/form.html` (client-side JavaScript) together with the supporting `sale_info` JSON endpoint in `app/modules/payment/routes.py`.

**Cause:** across several rounds of edits to `form.html`, the JavaScript responsible for calling the balance-info endpoint and writing its response into the DOM had drifted out of sync with the actual element IDs and event bindings on the page (compounded by the duplicate-route crash in 12.2 happening around the same time), so the `fetch()` call was either never firing on the correct event or its result was never being written into the visible panel.

**Fix:** the form's JavaScript block was rewritten as a single, self-contained IIFE with one clearly defined `loadSaleInfo(saleId)` / `loadBalanceInfo(kind, refId)` function responsible for the fetch-and-populate cycle, triggered consistently from three places: the reference-type radio toggle, the Sale/Appointment `<select>`'s `change` event, and once on initial page load if a value was already selected (covering both the Edit-form case and a re-rendered Create form after a failed validation attempt). The endpoint itself (`/payments/sale-info/<id>`, and later its Appointment equivalent `/payments/appointment-info/<id>`) returns a small JSON payload:

```python
@bp.route('/sale-info/<int:sale_id>')
@login_required
def sale_info(sale_id):
    exclude_payment_id = request.args.get('exclude_payment_id', type=int)
    total      = float(sale_r.data.get('TotalAmount') or 0)
    total_paid = _get_sale_total_paid(sale_id, exclude_payment_id=exclude_payment_id)
    remaining  = max(0.0, total - total_paid)
    return jsonify({'sale_date': ..., 'total_amount': total, 'total_paid': total_paid, 'remaining': remaining})
```

**Result:** confirmed the panel updates correctly on Sale selection, after a partial payment (re-fetching shows the updated Already-Paid/Remaining figures), and correctly excludes the payment currently being edited from the "already paid" sum on the Edit form.

---

### 12.5 Sale could be paid repeatedly / Appointment disappeared after first partial payment (inconsistent behaviour)

**What happened:** two related but opposite-facing problems were reported together. First, a Sale could apparently be selected and paid for indefinitely, even after being fully paid. Second, and inconsistently, an Appointment disappeared from the payment-selection dropdown after its **first** payment — even if that payment was only a partial deposit, incorrectly preventing the remaining balance from ever being paid.

**Files involved:** `app/modules/payment/routes.py` (`_get_sale_options`, `_get_appointment_options`, `_validate_form`) and the database (`Payment` table constraints).

**Cause (Sale side):** the Sale dropdown-filtering logic had not yet been written to check remaining balance at all in an early version — it listed every Sale unconditionally, so a fully-paid Sale never actually left the list. **Cause (Appointment side):** a UNIQUE database constraint, `unique_appointment_payment`, had been placed on `Payment.Appointment_AppointmentID` when the Payment table was first created, under the (at that time reasonable-seeming) assumption that an appointment would only ever need exactly one payment. Once partial/deposit payments were required for consistency with the Sale side, this constraint became directly incompatible with the desired behaviour: the *database itself* would reject a second Payment row for the same appointment, regardless of what the application code did.

**Investigation:** the Sale-side logic (`_get_sale_options`, which computes `remaining = total − paid` per sale and only lists sales where `remaining > 0`) was already correct by this point and was used as the reference implementation. Comparing it against `_get_appointment_options` (which, before the fix, filtered purely on "does this appointment have **any** payment row at all," with no balance calculation whatsoever) revealed the exact source of the inconsistency, and comparing both against the schema surfaced the UNIQUE constraint as the deeper, structural blocker.

**Fix:** the database constraint was dropped —

```sql
ALTER TABLE public."Payment" DROP CONSTRAINT IF EXISTS "unique_appointment_payment";
```

— and `_get_appointment_options()` was rewritten to mirror `_get_sale_options()` exactly: computing a live Appointment total (via a new `_get_appointment_total()` helper replicating the same services+stock cost calculation used in the Appointment view page), summing existing payments, and filtering/labelling by remaining balance in the identical way:

```python
def _get_appointment_options(exclude_appt_id=None):
    for a in appts_data:
        total     = _get_appointment_total(aid)
        paid      = _get_appointment_total_paid(aid)
        remaining = max(0.0, total - paid)
        if remaining <= 0.001 and aid != exclude_appt_id:
            continue
        ...
```

`_validate_form()` was correspondingly extended with an Appointment-side overpayment/fully-paid check that had previously only existed for Sales.

**Result:** confirmed Sales and Appointments now behave identically — both support unlimited-count partial payments as long as `remaining > 0`, both block overpayment past the remaining balance, and both disappear from the selection dropdown only once fully paid.

---

### 12.6 Editing a Payment allowed switching Sale ↔ Appointment, risking duplicate associations

**What happened:** the Payment Edit form originally re-rendered the same radio-button reference-type toggle used on the Create form, meaning an admin could open an existing Sale payment for editing and switch it to reference an Appointment instead (or vice versa) — a change that made no business sense and could result in an Appointment accidentally acquiring a second payment record through an edit rather than a create.

**File involved:** `app/templates/modules/payment/form.html`, `app/modules/payment/routes.py` (`edit()`, `_validate_form()`).

**Cause:** the Edit route was reusing the exact same form template and field set as Create without restricting which reference type could be submitted.

**Fix:** the reference type is now determined once, from the existing Payment row itself, at the very start of `edit()`, and is never re-derived from submitted form data:

```python
locked_ref_type = 'appointment' if current_appt_id else 'sale'
```

The template renders this as a read-only indicator plus a hidden input carrying the locked value, rather than the radio buttons shown on Create:

```html
<input type="hidden" name="reference_type" value="{{ locked_ref_type }}">
<div class="readonly-value">
    {% if locked_ref_type == 'sale' %}Sale Payment{% else %}Appointment Payment{% endif %}
    <span class="text-muted">— Reference type cannot be changed when editing.</span>
</div>
```

`_validate_form()` was also updated to always accept an explicit `locked_ref_type` parameter on the Edit path, so the server-side validation itself is incapable of processing a reference-type switch even if a request were crafted manually outside the UI.

**Result:** confirmed that editing a Sale payment only ever shows/accepts the Sale field, editing an Appointment payment only ever shows/accepts the Appointment field, and the existing association can no longer be altered through an edit.

---

### 12.7 Multiple Payment records created from repeated Confirm Payment clicks

**What happened:** clicking the "Confirm Payment" submit button several times in quick succession, while the first request was still processing, created multiple distinct `Payment` rows with different `PaymentID`s from what the user intended as a single payment.

**Files involved:** `app/templates/modules/payment/form.html` (client-side) and `app/modules/payment/routes.py`'s `create()` route (server-side).

**Cause:** the form had no protection against rapid duplicate submission at either layer — the submit button remained clickable throughout the request/response cycle, and the server had no way to distinguish a genuine second payment attempt from an accidental double-click of the same intended payment.

**Fix — two layers, deliberately:**

Client-side, the submit button is disabled and visually switched to a "Processing..." state on the very first `submit` event, before the browser even sends the request:

```javascript
payForm.addEventListener('submit', function () {
    if (submitBtn.disabled) return;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i>Processing...';
});
```

Server-side (the layer that actually matters, since the client-side disable can be bypassed or can fail to fire), a one-time token is generated and stored in the Flask session on every `GET` request to the Create form, embedded as a hidden field, and **consumed** (removed from the session) the moment a `POST` carrying it is accepted:

```python
if request.method == 'GET':
    form_token = str(uuid.uuid4())
    session['payment_form_token'] = form_token

if request.method == 'POST':
    submitted_token = request.form.get('form_token', '')
    session_token   = session.get('payment_form_token')
    if session_token is not None and (not submitted_token or submitted_token != session_token):
        flash_error('This payment appears to have already been submitted. ...')
        return redirect(url_for('payment.index'))
    if session_token is not None:
        session.pop('payment_form_token', None)
```

**A regression introduced, then corrected, within this same fix:** an early version of the fixed `form.html` was deployed without the actual `<input type="hidden" name="form_token" ...>` field present in the markup — meaning every submission sent an *empty* token, which the (at-the-time stricter) server check treated as an automatic duplicate, incorrectly blocking **every** first-time payment with the "already submitted" message. This was diagnosed by tracing the check's logic against the actual submitted form data, and fixed in two parts: restoring the missing hidden field in the template, and relaxing the server check so it only blocks when the session genuinely holds a *different* token than the one submitted (rather than treating "no token submitted" as automatically suspicious) — since a missing session token (e.g. an expired session) should not silently and permanently block legitimate payments either.

**Result:** confirmed via repeated rapid clicking of Confirm Payment that only one `PAY-` record is created per genuine submission, while legitimate first-time submissions are no longer falsely blocked.

---

### 12.8 Sale/Appointment payment cards not refreshing after a payment was deleted

**What happened:** after deleting a Payment record linked to a Sale or Appointment, the corresponding view page's payment/status information did not reliably reflect the deletion — the balance figures could appear stale.

**Cause:** balance and payment-list data were being computed correctly at the point of the fix in Section 12.5/12.7, but the underlying requirement — never caching or storing computed balance figures, and always recalculating from the live `Payment` table on every page load — needed to be applied consistently across the Sale view, Appointment view, and Payment form pages, not just the Payment module itself.

**Fix:** the Appointment view route's payment section was rewritten to fetch **all** payments linked to the appointment fresh on every request (not just check for existence of one), and to recompute `appt_total_paid` and `appt_remaining` from that live list on every render:

```python
appt_payments = supabase.table('Payment').select('*').eq(
    'Appointment_AppointmentID', appt_id
).order('PaymentID').execute().data or []
appt_total_paid = sum(float(p.get('AmountPaid') or 0) for p in appt_payments)
appt_remaining  = max(0.0, appt_total - appt_total_paid)
```

Because this recomputation happens on every page load from the database directly (with no intermediate cache), deleting a Payment and then reloading the Sale or Appointment view page immediately reflects the correct, updated balance.

**Result:** confirmed that creating, editing, and deleting payments each correctly and immediately update the balance figures shown on the related Sale/Appointment view page.

---

### 12.9 Appointment stock quantity not decreasing after completion

**What happened:** using a spare part during an appointment (e.g. 10 units of Piston Rings against a Stock row with QOH 135), completing the appointment, and marking its Payment as settled did **not** reduce the Stock record's QOH — it remained at 135 instead of the expected 125.

**Files involved:** `app/modules/appointment/routes.py` (the `edit()` route and the `Appointment_Stock` add/edit/delete routes).

**Cause:** at no point in the codebase did any route ever write to `Stock.QOH` in connection with an appointment. `Appointment_Stock` rows purely *recorded* that a given stock item and quantity were used during a given appointment — they were never consumed against the actual inventory count. This was a genuine missing feature rather than a bug in existing logic — the deduction step had simply never been implemented.

**Investigation:** the full appointment lifecycle (create → add services/stock → edit status → view) was traced through `routes.py` to confirm no `Stock` table write existed anywhere in the module, and the Stock module's own CRUD was checked to confirm QOH is otherwise only ever changed by a direct admin edit to a Stock record or by the Purchase Order receiving workflow (Section 10.5) — never by an Appointment.

**Fix:** documented fully with code in Section 10.3. In summary, a new `_deduct_stock_for_appointment(appt_id)` helper iterates every `Appointment_Stock` row for the appointment and decrements the linked `Stock.QOH` by the recorded `Quantity`, floored at zero. This is called from the Appointment `edit()` route, guarded so it fires **exactly once**, only on the specific transition of `Status` from something other than `'Completed'` into `'Completed'`:

```python
if status_value == 'Completed' and previous_status != 'Completed':
    _deduct_stock_for_appointment(appt_id)
```

**Result:** confirmed with the exact reported scenario — a Stock item at QOH 135, 10 units used on an appointment, appointment marked Completed — QOH correctly became 125. Re-saving the same already-Completed appointment afterward (without changing Status again) was confirmed **not** to deduct a second time.

---

### 12.10 Payment Type displayed twice on the same row

**What happened:** the Payments list table showed the same value twice per row — a "Type" column and a separate "Payment Type" column both rendering `PaymentType`, producing visible repetition such as `Full Payment ----- Full Payment`.

**File involved:** `app/templates/modules/payment/list.html`.

**Cause:** the table's column-header list (`['Pay ID', 'Reference', 'Type', 'Date', 'Amount Paid', 'Method', 'Payment Type', 'Date Created']`) and its corresponding row-cell markup both independently rendered `row.PaymentType` — once as a styled badge under "Type," and again as plain text under a redundant "Payment Type" column that had not been removed when the badge version was introduced.

**Fix — a display-only change, no route or database logic touched:**

```html
<!-- header list: 'Payment Type' entry removed -->
['Pay ID', 'Reference', 'Type', 'Date', 'Amount Paid', 'Method', 'Date Created']

<!-- row cells: the duplicate plain-text <td> removed -->
<td>{{ row.PaymentMethod }}</td>
<!-- <td>{{ row.PaymentType }}</td>  <-- removed -->
<td> ... Date Created cell ... </td>
```

**Result:** confirmed each payment's type now appears exactly once per row, as the color-coded badge under "Type."

---

### 12.11 Cross-cutting: Admin Panel code breaking after a database schema change (Spare Parts / Model)

**What happened:** as documented in Section 6.3, once `Spare_Parts.Model_Model_No` was dropped from the database (per the supervisor's Compatibility redesign), the already-built Spare Parts module — which had a working Model dropdown from before the schema change — began erroring on page load, because its route code still queried and referenced a column that no longer existed.

**Files involved:** `app/modules/spare_parts/routes.py`, `app/templates/modules/spare_parts/list.html`, `app/templates/modules/spare_parts/form.html`, and similarly `app/modules/stock/routes.py` / `app/templates/modules/stock/form.html` for the related `Stock.Size` now-optional change.

**Cause:** a database migration was applied without the corresponding application-layer code being updated at the same time.

**Fix:** systematically removed every reference to the dropped column from the Spare Parts module — the Model fetch inside `_get_form_options()`, the `_model_desc` enrichment and its use in search filtering inside `index()`, the `model_no_raw` parsing and validation inside `create()`/`edit()`, its presence in the insert/update payload, and the corresponding "Model" column/cell in `list.html` and the entire "Model Compatibility" field block in `form.html`. Separately, the Stock module's `Size` field validation was relaxed from required to optional, matching the new `Stock.Size` nullable column, with its help text updated to say "Optional."

**Result:** confirmed both Spare Parts and Stock modules' list, create, and edit pages worked correctly again after the changes, with Model compatibility now exclusively managed through the dedicated Compatibility module instead.

`[INSERT IMAGE HERE — Before/After Screenshot: Sidebar Scrolling Fix]`

`[INSERT IMAGE HERE — Before/After Screenshot: Payment Balance Panel]`

---

### 12.12 PO_NewMotorBike — two items identified during review, not yet fixed

Unlike the entries above, the following two items were identified while reviewing the newly added `PO_NewMotorBike` feature (Section 6.10, Section 8.19) and are recorded here as **known, unresolved issues** rather than completed fixes, so they are not lost between review cycles.

**Item 1 — duplicate-error misattribution in the "New Motorcycle Record" path.** In `add_motorbike()`, the `New_MotorBike` insert and the subsequent `PO_NewMotorBike` insert are currently wrapped in a single `try/except`. If the `New_MotorBike` insert fails because the entered VIN already exists elsewhere (a `New_MotorBike_VIN_unique` violation), the shared exception handler still reports it as `"This motorcycle is already linked to another purchase order"` — the wrong field (`New_MotorBike_NB_ID` instead of `VIN`) and the wrong explanation. The proposed fix is to split the two inserts into separate `try/except` blocks, each mapping its own exception to the correct form field, but this has not yet been applied.

**Item 2 — PO Status not recalculated for motorcycle procurement.** `PurchaseOrderItem` receiving triggers `_auto_update_po_status()` (Section 10.5) so a PO's own `Status` field reflects whether all, some, or none of its items have been received. Linking, editing, or deleting a `PO_NewMotorBike` row does not call anything equivalent, so a Purchase Order can show `Status = 'Pending'` even after every motorcycle on it has arrived. Whether — and how — motorcycle rows should feed into the same status calculation is an open design question, since motorbikes (unlike spare-part items) have no `Ordered`/`Received` state of their own to check.

---
## 13. Important Code Explained

This section collects the pieces of code that recur across the project or that embody a specific technical decision, with an explanation of what each does and why it exists in that form.

### 13.1 The Application Factory and Blueprint Registration

Already shown in Section 5.3 — the single most structurally important piece of code in the project, because it is what made adding 17 independent modules over the course of development possible without any module's code ever needing to be touched by a later module's addition.

### 13.2 The Shared Audit Trigger Function

Shown in full in Section 6.6 — one PL/pgSQL function (`set_audit_fields()`) attached to every substantive table via a per-table `BEFORE INSERT OR UPDATE` trigger, meaning **no Flask route anywhere in the codebase ever manually sets `Date_Created`, `Created_By`, `Date_Updated`, or `Updated_By`** — this was an explicit rule enforced in every single task specification throughout the project, and its correctness was specifically re-verified after Supabase Auth was introduced (Section 6.6) to confirm `auth.uid()` would resolve to the real logged-in user rather than remaining stuck on `'system'`.

### 13.3 The FK-Violation-to-Plain-Language-Message Pattern

Used in every module that has at least one FK dependent (Category, Role, Brand, Model, Spare Parts, Employee, Supplier, Customer, Customer_bike, New_MotorBike, Sale, Appointment):

```python
try:
    supabase.table('Category').delete().eq('CAT_ID', cat_id).execute()
    flash_success(f'Category "{desc_value}" was deleted successfully.')
except Exception as e:
    error_msg = str(e)
    if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
        flash_error(
            f'Cannot delete "{desc_value}" because it is used by one or more spare parts.'
        )
    else:
        flash_error(f'Could not delete category: {error_msg}')
```

This pattern deliberately inspects the *text* of the raised exception for the substrings `'foreign key'` or `'violates'` (which PostgreSQL's own error messages reliably contain) rather than parsing a specific error code, and converts that into a message naming the **specific dependent table** in plain English. This was applied consistently everywhere a delete could fail due to referential integrity, rather than ever surfacing a raw database exception string to the end user.

### 13.4 The Lookup-Dictionary Enrichment Pattern

Introduced first in the Model module (Section 8.8) and reused in every list view that needs to show a human-readable label instead of a raw foreign key:

```python
brand_lookup = {r['Brand_ID']: r['Brand_Name'] for r in brand_result.data or []}
for model in all_records:
    model['_model_label'] = brand_lookup.get(model.get('Brand_Brand_ID'), '—')
```

The underscore-prefixed key (`_model_label`, `_customer_name`, `_stock_label`, `_reference_label`, etc.) is a project-wide naming convention signalling "this field was computed in Python for display, it does not exist in the database row." This was chosen over a Supabase join query (PostgREST does support embedded resource joins) specifically for clarity and debuggability at the developer's current skill level — separate, simple `select()` queries plus a Python dictionary lookup were judged easier to reason about and modify than nested join syntax.

### 13.5 Optional Foreign Key Handling (Empty String → `None`)

A recurring, deliberately-applied rule: whenever an HTML `<select>` for an *optional* foreign key is submitted empty, the value must be converted to Python `None` before being sent to Supabase — never left as an empty string, which Postgres would reject or misinterpret for an integer FK column:

```python
supervisor_id = None
if supervisor_id_raw:
    try:
        supervisor_id = int(supervisor_id_raw)
    except ValueError:
        errors['SupervisorID'] = 'Invalid supervisor selection.'
```

This exact pattern appears for `Employee.SupervisorID`, `Spare_Parts.Model_Model_No` (before it was removed), `Compatibility.Year_From`/`Year_To`, `Sale.Employee_EmployeeID`, and `Payment.Sale_SaleID`/`Appointment_AppointmentID` (whichever side is not the active reference type).

### 13.6 Server-Side Validation Structure

Every Create/Edit route in the project follows the same validation shape: collect all field-level errors into a single dictionary **before** deciding whether to proceed, so the user sees every problem with their submission at once rather than being told about one error, fixing it, and then being told about the next:

```python
errors = {}
if 'FirstName' in missing:
    errors['FirstName'] = 'First name is required.'
if 'Email' in missing:
    errors['Email'] = 'Email address is required.'
elif not is_valid_email(email):
    errors['Email'] = 'Please enter a valid email address.'
# ... every other field checked similarly ...

if not errors:
    # only now attempt the database write
```

On the template side, the `novalidate` attribute is placed on every `<form>` tag specifically so the browser's own native validation popups never interfere with this server-driven, all-errors-at-once display — every validation message the user sees comes from the Flask route, not the browser.

### 13.7 The `_validate_year` / `_validate_date` / `_validate_time` Helpers

Small, single-purpose validators reused across modules that accept dates, times, or bounded year values:

```python
def _validate_date(raw_value, field_label):
    value = (raw_value or '').strip()
    if not value:
        return None, f'{field_label} is required.'
    try:
        date_type.fromisoformat(value)
        return value, None
    except ValueError:
        return None, f'{field_label} must be a valid date.'
```

Each returns a `(value_or_None, error_or_None)` tuple, letting the calling route write `date_val, err = _validate_date(...)` and immediately know whether to add `err` to the `errors` dict or use `date_val` in the insert payload. This tuple-return convention is used consistently for every specialised validator introduced from the Purchase Order module onward.

### 13.8 The Delete Confirmation Modal (Shared Across All Modules)

```html
<!-- components/modal_confirm.html -->
{% macro delete_modal() %}
<div class="modal fade" id="deleteModal" tabindex="-1">
  ...
  <form id="deleteModalForm" method="POST" action="">
    <button type="submit" class="btn btn-danger">Delete</button>
  </form>
</div>
{% endmacro %}
```

```javascript
// admin.js
const deleteModal = document.getElementById('deleteModal');
deleteModal.addEventListener('show.bs.modal', function (event) {
    const triggerButton = event.relatedTarget;
    const deleteUrl  = triggerButton.getAttribute('data-delete-url');
    const recordName = triggerButton.getAttribute('data-record-name');
    document.getElementById('deleteModalForm').action = deleteUrl || '';
    document.getElementById('deleteModalRecordName').textContent = recordName || '';
});
```

One single modal element exists per page, and every row's individual Delete button carries its own target URL and record name as `data-*` attributes; Bootstrap's `show.bs.modal` event fires with the triggering button available as `event.relatedTarget`, which is what lets one shared modal correctly populate itself differently for whichever row's Delete button was actually clicked, without needing a separate modal per row.

### 13.9 Payment Balance Calculation and Overpayment Guard

Shown in full in Section 10.2 and Section 12.4/12.5. The key idiom worth calling out here is the **always-recompute-never-cache** principle applied to both the Sale and Appointment sides: `_get_sale_total_paid()` / `_get_appointment_total_paid()` are called fresh, from the live `Payment` table, every single time a balance is needed — on the dropdown-population pass, on the balance-info JSON endpoint, and inside `_validate_form()`'s overpayment check — rather than storing a running "amount paid" total anywhere. This was a deliberate correctness decision: a stored/cached total can drift out of sync with reality (exactly the bug in Section 12.8); a value recomputed from source on every read cannot.

### 13.10 Appointment Cost Calculation and Stock Deduction

Shown in full in Section 10.3. Notable here is the differing default-quantity behaviour between services (`Quantity or 1`) and stock (`Quantity or 0`), and the `previous_status != 'Completed'` guard that makes the stock-deduction side effect idempotent — safe to have the surrounding `edit()` route call unconditionally on every save, because the guard itself decides whether the deduction should actually happen.

### 13.11 Multi-Row Insert with Per-Row Duplicate Tolerance (Compatibility)

```python
success_count, duplicate_count, fail_count = 0, 0, 0
for model_no_str in selected_model_nos:
    try:
        model_no = int(model_no_str)
        supabase.table('Compatibility').insert({...}).execute()
        success_count += 1
    except Exception as e:
        if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
            duplicate_count += 1
        else:
            fail_count += 1
```

This is the one place in the project where a single form submission intentionally issues **multiple** independent insert calls in a loop, each with its own try/except, so that one duplicate among several selected models does not abort the whole batch — the user instead receives a single summarising flash message reporting how many succeeded, how many were skipped as duplicates, and how many genuinely failed.

### 13.12 The Purchase Order Receiving Dual-Path Logic

Shown in full in Section 10.5. Architecturally significant because it is the one place in the codebase where a single admin action (clicking "Receive") deliberately branches into two structurally different database write sequences (an `UPDATE` to an existing `Stock` row, or an `INSERT` of a brand-new one) based on a runtime choice made via the two-card radio selector described in Section 9.6, with both paths converging back onto the same `PurchaseOrderItem` update at the end.

### 13.13 Duplicate-Submission Protection (Session Token)

Shown in full in Section 12.7 — a hand-rolled, minimal alternative to a CSRF-token library, chosen because the project deliberately avoided adding Flask-WTF or any other forms/validation extension (Section 4.1). The token is generated on `GET`, stored server-side in the Flask session (never trusted from the client alone), embedded as a hidden form field, and explicitly popped from the session the moment a matching `POST` is accepted — meaning a second, accidental submission of the exact same rendered form (whether from a double-click or a browser back-button resubmission) is caught because the session no longer holds a matching token to compare against.

---
## 14. Testing

Testing throughout this project was **manual and structured**, not automated — no unit or integration test suite (e.g. `pytest`) was written. Every task in the development history (Section 11) ended with an explicit, itemised manual test pass before the next task began, and every bug-fix round in Section 12 ended with a specific re-test of the reported scenario. The table below distinguishes what was **confirmed working through this process** from anything not independently confirmed.

### 14.1 CRUD Testing — Confirmed Working

For all 18 modules (Color through Payment), the following was manually verified per module: list page renders with correct search/pagination; Create inserts a new row with audit fields auto-populated by the trigger (showing the real authenticated user's email post-Task-17, not `'system'`); Edit pre-populates every field correctly, including all FK dropdowns pre-selecting their existing value; Delete removes the row only after explicit modal confirmation, and Cancel in the modal performs no deletion; attempting to delete a row with existing FK dependents produces the specific, named plain-language error described in Section 13.3 rather than a raw exception.

### 14.2 Validation Testing — Confirmed Working

Required-field validation, string length limits, numeric range validation (`is_positive_number`, `is_positive_integer`), email format validation, date/time format validation, and predefined-option validation (Status/PaymentMethod/PaymentType/FuelType/Transmission/AppointmentType all rejecting values outside their fixed lists) were each tested with both a valid and an invalid input per field, per module, confirming that submitting multiple invalid fields at once surfaces **all** of their errors simultaneously (Section 13.6) rather than stopping at the first.

### 14.3 Duplicate-Data Testing — Confirmed Working

- Brand, Category, Role, Service, Supplier, and Model: confirmed a duplicate name/description is rejected with a specific "already exists" message.
- Customer: confirmed a duplicate NIC and a duplicate PhoneNumber are each independently rejected; confirmed two customers with the same First/Last name **are** allowed (by design).
- Customer_bike: confirmed a duplicate VIN and a duplicate RegistrationNumber are each rejected; confirmed the ownership-transfer workflow (editing the existing bike's linked Customer) works correctly without needing or allowing a duplicate vehicle row.
- New_MotorBike: confirmed a duplicate VIN is rejected via its UNIQUE constraint.
- Compatibility: confirmed the multi-select batch insert correctly skips already-existing (Stock, Model, Year range) combinations while still inserting the genuinely new ones, with an accurate success/duplicate count reported back.

### 14.4 Payment Testing — Confirmed Working

- Full payment against a Sale, immediately removing that Sale from the Create-form dropdown.
- Partial/deposit payment against a Sale, leaving the Sale selectable with a correctly updated "remaining" label; a second payment for exactly the remaining balance correctly fully settles it.
- Overpayment attempt against a Sale (amount greater than remaining balance) correctly blocked with the exact-figures error message.
- The identical full/partial/overpayment/remaining-balance behaviour re-confirmed on the Appointment side, following the fix described in Section 12.5.
- Editing a Payment's amount re-validated against the current remaining balance (excluding that payment's own prior amount from the "already paid" sum).
- Attempting to change a Payment's reference type (Sale ↔ Appointment) during Edit confirmed impossible — the field is locked (Section 12.6).
- Rapid repeated clicking of "Confirm Payment" confirmed to produce exactly one `PAY-` record (Section 12.7), and confirmed that a genuine first-time submission is no longer falsely blocked by the same protection.
- Deleting a Payment confirmed to immediately update the related Sale/Appointment view page's balance figures on next load (Section 12.8).

### 14.5 Appointment Testing — Confirmed Working

Create/Edit/View for Appointments (including the Jinja fix in Section 12.1); adding and removing Services and Stock items on a non-locked appointment; confirmed Services/Stock cannot be modified once Status is Completed or Cancelled; confirmed the Estimated Cost Summary (Services Total + Stock Total = Grand Total) calculates correctly and updates as items are added/removed; confirmed the specific reported stock-deduction scenario from Section 12.9 (135 → 125 after using 10 units and completing the appointment), including confirming no double-deduction occurs on a subsequent save of an already-Completed appointment.

### 14.6 Stock Testing — Confirmed Working

Stock CRUD with the now-optional `Size` field; Stock QOH correctly increased via the Purchase Order "existing stock" receiving path; a new Stock row correctly created via the "new stock" receiving path with QOH set to the received quantity; Stock QOH correctly decreased via Appointment completion (Section 12.9).

### 14.7 Authentication Testing — Confirmed Working

Login with valid/invalid credentials; every protected route redirecting to `/auth/login` when accessed without a session (tested via a private/incognito browser window); the login page itself redirecting *away* to the dashboard if already authenticated; logout correctly clearing the session and redirecting to login; a manually-deleted session cookie correctly triggering a redirect to login on the next protected-page request; `Created_By`/`Updated_By` confirmed to show the real authenticated user's email (not `'system'`) on records created/edited after login.

### 14.8 Navigation / UI Testing — Confirmed Working

All sidebar links across all six sections reachable and correctly highlighting the active module; sidebar scrolling confirmed fixed at normal zoom (Section 12.3); mobile/collapsed sidebar toggle and overlay behaviour confirmed at narrow viewport widths; dashboard count cards confirmed to reflect live database counts and to degrade gracefully (falling back to 0 for that one card) if an individual count query fails, without breaking the rest of the dashboard.

### 14.9 Not Independently Confirmed / Out of Scope for Testing

- No automated regression test suite exists; all confirmations above were manual, human-performed passes at the time each fix was made, not continuously re-verified on every subsequent change.
- Load/performance testing, concurrent-user testing, and browser-compatibility testing beyond the developer's own working environment were not performed and are not claimed here.
- The "customers buying spare parts directly" feature discussed during the Payment/Appointment review round (see the original issue list referenced in Section 12) was evaluated conceptually but **not implemented**, and is therefore not covered by any testing in this report.

`[INSERT IMAGE HERE — Testing Evidence Screenshot: Stock Deduction Before/After]`
*Side-by-side Stock module screenshots showing QOH = 135 before completing the appointment and QOH = 125 after.*

`[INSERT IMAGE HERE — Testing Evidence Screenshot: Overpayment Error]`
*The Payment form showing the specific overpayment error message with exact Rupee figures.*

---

## 15. Final System State

At the time of writing, the Admin Panel provides complete, working CRUD coverage across all 18 documented modules (Section 8), secured end-to-end by Supabase Authentication and PostgreSQL Row Level Security (Section 7), with the following business logic layers fully implemented and tested:

- Automatic New_MotorBike Available/Sold status linkage to Sale create/edit/delete (Section 10.1).
- Consistent full/partial/deposit/remaining-balance payment logic across both Sale and Appointment payments, with overpayment prevention and duplicate-submission protection (Section 10.2, Section 12.5–12.7).
- Automatic estimated cost calculation and stock deduction on Appointment completion (Section 10.3, Section 12.9).
- Duplicate-data protection across Customer, Customer_bike, and all relevant master-data tables, with a working ownership-transfer workflow (Section 10.4).
- A two-path Purchase Order receiving workflow correctly updating or creating Stock records (Section 10.5).
- A Compatibility module correctly implementing the supervisor-requested Stock↔Model many-to-many relationship with optional year ranges (Section 10.6).

All errors and defects identified during development and documented in Sections 12.1–12.11 have been resolved and re-tested against their originally reported scenario.

**Addition pending final review:** the `PO_NewMotorBike` bridge table and its Purchase Order module integration (Section 6.10, Section 8.19) were added after the above was confirmed working, extending purchase ordering to motorcycle units alongside the existing spare-parts workflow. Two items identified during this addition's review — the duplicate-error misattribution and the PO Status not recalculating for motorcycles (Section 12.12) — remain open and are not yet included in the "resolved and re-tested" statement above.

`[INSERT IMAGE HERE — Final Dashboard Screenshot]`
*The completed dashboard showing all module count cards populated with real data, as the final visual state of the system at time of writing.*

---

## 16. Conclusion

The Admin Panel component of the Motorbike Sales and Servicing Management System was built incrementally, module by module, from an initial Oracle-modelled ERD through to a fully authenticated, RLS-secured Flask/Supabase application covering the dealership's master data, purchasing, customer, inventory, appointment, sales, and payment operations. The project's development process was characterised by two recurring, deliberate patterns: building a small set of shared, reusable components (the Jinja macros in Section 9.4, the validation and FK-error-handling idioms in Section 13) early and reusing them without duplication across every subsequent module; and treating supervisor feedback and testing-discovered defects as first-class inputs to the schema and business logic, documented and reasoned through explicitly (Sections 6.9, 10, and 12) rather than patched silently. The result is a system whose database design, authentication model, and core business rules — motorbike sale/availability linkage, payment balance tracking, and appointment-driven stock consumption — are grounded in real dealership workflow requirements gathered and refined throughout the project's supervised development.

---

## 17. Appendices

### Appendix A — Full List of Database Tables

| # | Table | Type |
|---|---|---|
| 1 | Color | Phase 1 master data |
| 2 | Category | Phase 1 master data |
| 3 | Role | Phase 1 master data |
| 4 | Supplier | Phase 1 master data |
| 5 | Brand | Phase 1 master data |
| 6 | Employee | Phase 1 master data |
| 7 | Model | Phase 1 master data |
| 8 | Service | Phase 1 master data |
| 9 | Spare_Parts | Phase 1 master data |
| 10 | Stock | Phase 1 master data |
| 11 | Compatibility | Bridge (Stock ↔ Model) |
| 12 | PurchaseOrder | Purchasing |
| 13 | PurchaseOrderItem | Purchasing |
| 14 | Customer | Phase 3 transactional |
| 15 | Customer_bike | Phase 3 transactional |
| 16 | New_MotorBike | Phase 3 transactional |
| 17 | Appointment | Phase 3 transactional |
| 18 | appointment_service | Bridge (Appointment ↔ Service) |
| 19 | Appointment_Stock | Bridge (Appointment ↔ Stock) |
| 20 | Sale | Phase 3 transactional |
| 21 | Payment | Phase 3 transactional |
| 22 | PO_NewMotorBike | Bridge (PurchaseOrder ↔ New_MotorBike) |

### Appendix B — Full List of Admin Panel Modules and URL Prefixes

| Module | URL Prefix |
|---|---|
| Color | `/colors` |
| Category | `/categories` |
| Brand | `/brands` |
| Model | `/models` |
| Spare Parts | `/spare-parts` |
| Stock | `/stock` |
| Service | `/services` |
| Role | `/roles` |
| Employee | `/employees` |
| Supplier | `/suppliers` |
| Compatibility | `/compatibility` |
| Purchase Order | `/purchase-order` |
| Customer | `/customers` |
| Customer Bike | `/customer-bikes` |
| New Motorbike | `/new-motorbikes` |
| Appointment | `/appointments` |
| Sale | `/sales` |
| Payment | `/payments` |
| Auth | `/auth` |
| Dashboard | `/dashboard` |

### Appendix C — Key Reference: Audit Trigger Function

See Section 6.6 for the full `set_audit_fields()` function and its per-table attachment pattern.

### Appendix D — Key Reference: RLS Policy Pattern

See Section 6.7 for the three-stage RLS rollout (temporary `anon` grants → `authenticated` grants + policies → per-new-table policy at creation time) and the standard `admin_full_access` policy applied identically across every table.

`[INSERT IMAGE HERE — Full ERD, Repeated for Appendix Reference]`
*A second, full-page copy of the complete ERD from Section 6.1, sized for print/appendix reference.*

---

**End of Report**
