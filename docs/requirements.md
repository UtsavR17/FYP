# Admin Panel — Requirements

**Project:** Motorbike Sales and Servicing Management System
**Module:** Admin Panel
**Phase:** Phase 2
**Last Updated:** [12 August 2026]
**Status:** In Progress

---

## Change Log

| Version | Date | Change | Approved By |
|---|---|---|---|
| 1.0 | [12 August 2026] | Initial document created | Utsav Ramjattan |

---

## 1. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Admins must be authenticated before accessing any page | High |
| FR-02 | All CRUD operations must read from and write to the live Supabase database | High |
| FR-03 | All list views must support keyword search | High |
| FR-04 | All list views must support pagination | Medium |
| FR-05 | Create and Edit forms must validate required fields before submission | High |
| FR-06 | Delete actions must require a confirmation step before the record is removed from the database | High |
| FR-07 | FK fields must use dropdown components populated from the related table — users must never manually enter database IDs | High |
| FR-08 | Audit fields (Date_Created, Created_By, Date_Updated, Updated_By) must be displayed as read-only in Edit views | Medium |
| FR-09 | The Dashboard must display live record counts from all 10 Phase 1 tables | Medium |
| FR-10 | FK constraint violations on Delete must produce a clear, user-readable error message — not a raw database exception | High |
| FR-11 | The Spare Parts module must support a "Universal / Not model-specific" option for parts with no model dependency | High |
| FR-12 | The Employee module must support creating an employee with no supervisor (nullable SupervisorID) | High |

---

## 2. Non-Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| NFR-01 | Pages must load within 3 seconds on a local development connection | Medium |
| NFR-02 | The UI must be usable on screens 768px wide and above | High |
| NFR-03 | The codebase must follow consistent naming conventions throughout | Medium |
| NFR-04 | Components and templates must be reusable across modules — code must not be duplicated between CRUD modules | High |
| NFR-05 | The project structure must be scalable — adding a new module in Phase 3 must not require restructuring the existing application | High |
| NFR-06 | The application must be maintainable by a single developer | Medium |

---

## 3. Security Requirements

| ID | Requirement | Priority |
|---|---|---|
| SR-01 | The Supabase service_role key must never appear anywhere in the application code or configuration files | Critical |
| SR-02 | All admin routes must verify an active session before rendering a response | Critical |
| SR-03 | The .env file must be listed in .gitignore and must never be committed to version control | Critical |
| SR-04 | All user-supplied form inputs must be validated before being passed to the database | High |
| SR-05 | Row Level Security (RLS) must be enabled on all Phase 1 tables | Critical |
| SR-06 | RLS policies must allow only authenticated admin users to perform read, insert, update, and delete operations | Critical |
| SR-07 | Authentication and RLS must be implemented together as one combined task to ensure the same security model is tested throughout | High |
| SR-08 | RLS policies must not interfere with the existing audit triggers for Date_Created, Created_By, Date_Updated, and Updated_By | Critical |

---

## 4. Database Requirements

| ID | Requirement | Priority |
|---|---|---|
| DR-01 | The Admin Panel must use the existing Phase 1 Supabase tables without modifying their structure | Critical |
| DR-02 | Audit fields must be populated automatically by the existing database triggers — application code must not manually set Date_Created, Created_By, Date_Updated, or Updated_By | Critical |
| DR-03 | The Supabase anon key must be used for all database operations from the application | Critical |
| DR-04 | All FK relationships established in Phase 1 must be respected and must remain intact | Critical |
| DR-05 | The database must not be modified until the combined Authentication and RLS task (Task 17) | High |

---

## 5. UI and UX Requirements

| ID | Requirement | Priority |
|---|---|---|
| UX-01 | The Admin Panel must use Flask with Bootstrap 5 as specified in the project framework | Critical |
| UX-02 | The design must be simple, professional, and modern — appropriate for a university project and a real business system | High |
| UX-03 | Consistent sidebar navigation must appear on all Admin Panel pages | High |
| UX-04 | The active sidebar item must be visually highlighted for the current page | Medium |
| UX-05 | Success and error messages must be clearly visible after every form submission | High |
| UX-06 | Forms must display inline field-level validation error messages | Medium |
| UX-07 | Table columns must be clearly labelled and appropriately sized | Medium |
| UX-08 | The design must avoid excessive animations, heavy gradients, and unnecessary decorative elements | Medium |
| UX-09 | The application must have a consistent visual identity — it must not look like a generic Bootstrap template with no customisation | Medium |

---

## 6. Authentication Requirements

| ID | Requirement | Priority |
|---|---|---|
| AU-01 | Supabase Auth is the only authentication provider — no Clerk, no other third-party provider | Critical |
| AU-02 | Authentication uses email and password login | High |
| AU-03 | Sessions must expire and redirect the user to the login page when expired | High |
| AU-04 | No hardcoded credentials anywhere in the codebase | Critical |
| AU-05 | Authentication is implemented in Task 17, after all CRUD modules are built and tested | High |
| AU-06 | The Admin Panel must be tested using the same security model (Supabase Auth + RLS) that will be used in the final system | Critical |

---

## 7. Validation Requirements

| ID | Requirement | Priority |
|---|---|---|
| VLD-01 | All required fields must be validated server-side before any database operation | Critical |
| VLD-02 | Validation errors must be returned to the form with the previously entered values preserved — the form must not reset to blank on validation failure | High |
| VLD-03 | Numeric fields (HourlyRate, Cost, S_Price, QOH, Warranty) must accept only valid numeric values | High |
| VLD-04 | Text fields must enforce the length limits defined in the database schema | Medium |
| VLD-05 | FK dropdown fields must validate that a selected value exists in the related table before inserting or updating | High |

---

## 8. Testing Requirements

| ID | Requirement | Priority |
|---|---|---|
| TR-01 | Each CRUD module must be manually tested with valid inputs | Critical |
| TR-02 | Each CRUD module must be manually tested with invalid or missing inputs to confirm validation works | Critical |
| TR-03 | FK dropdown fields must be tested to confirm they are populated from the correct related table | High |
| TR-04 | Delete confirmation must be tested — clicking Cancel must not delete the record | High |
| TR-05 | Audit fields must be verified as auto-populated after each Create and Update operation | High |
| TR-06 | FK constraint violations on Delete must be tested to confirm a user-readable error appears | High |
| TR-07 | RLS policies must be tested after Task 17 to confirm unauthenticated requests are rejected | Critical |

---

## 9. Phase Scope Boundary

The following items are explicitly out of scope for Phase 2. They belong to a future phase and must not be implemented now:

- Customer management
- Customer Bike management
- Appointment management
- Purchase Order management
- New MotorBike management
- Sale management
- Payment management
- Reporting or analytics beyond the Dashboard count cards
- Export to Excel or PDF
- Email notifications
- Multi-user role management beyond what exists in the Role table