# Admin Panel — Functionalities

**Project:** Motorbike Sales and Servicing Management System
**Module:** Admin Panel
**Phase:** Phase 2
**Last Updated:** [12 August 2026]
**Status:** In Progress

---

## Change Log

| Version | Date | Change | Approved By |
|---|---|---|---|
| 1.0 | [12 Aug 2026] | Initial document created | Utsav Ramjattan |

---

## 1. Authentication

| ID | Functionality | Status |
|---|---|---|
| AUTH-01 | Admin login with email and password using Supabase Auth | Planned |
| AUTH-02 | Admin logout | Planned |
| AUTH-03 | Session persistence across page loads | Planned |
| AUTH-04 | Protected routes — unauthenticated users are redirected to the login page | Planned |
| AUTH-05 | Unauthorized access page for users who reach a protected route without a session | Planned |
| AUTH-06 | Session expiry handling — expired sessions redirect to login | Planned |

> Authentication is implemented in Task 17, after all CRUD modules are built and tested.

---

## 2. Dashboard

| ID | Functionality | Status |
|---|---|---|
| DASH-01 | Summary count card for each Phase 1 table showing total number of records | Planned |
| DASH-02 | Quick-link navigation from each card to the corresponding management module | Planned |
| DASH-03 | Dashboard is the default landing page after login | Planned |

---

## 3. Color Management

| ID | Functionality | Status |
|---|---|---|
| CLR-01 | List all colors in a searchable table | Planned |
| CLR-02 | Add a new color | Planned |
| CLR-03 | Edit an existing color | Planned |
| CLR-04 | Delete a color with confirmation dialog | Planned |
| CLR-05 | Display audit fields (Date_Created, Created_By, Date_Updated, Updated_By) as read-only | Planned |

---

## 4. Category Management

| ID | Functionality | Status |
|---|---|---|
| CAT-01 | List all categories in a searchable table | Planned |
| CAT-02 | Add a new category | Planned |
| CAT-03 | Edit an existing category | Planned |
| CAT-04 | Delete a category with confirmation dialog | Planned |
| CAT-05 | Display audit fields as read-only | Planned |

---

## 5. Brand Management

| ID | Functionality | Status |
|---|---|---|
| BRD-01 | List all brands in a searchable table | Planned |
| BRD-02 | Add a new brand | Planned |
| BRD-03 | Edit an existing brand | Planned |
| BRD-04 | Delete a brand with confirmation dialog | Planned |
| BRD-05 | Display audit fields as read-only | Planned |

---

## 6. Model Management

| ID | Functionality | Status |
|---|---|---|
| MDL-01 | List all models in a searchable table showing Brand name (not Brand ID) | Planned |
| MDL-02 | Add a new model — Brand selected from a dropdown populated from the Brand table | Planned |
| MDL-03 | Edit an existing model | Planned |
| MDL-04 | Delete a model with confirmation dialog | Planned |
| MDL-05 | Display audit fields as read-only | Planned |

> FK dependency: Model → Brand

---

## 7. Spare Parts Management

| ID | Functionality | Status |
|---|---|---|
| SP-01 | List all spare parts in a searchable table showing Category name and Model description (not raw IDs) | Planned |
| SP-02 | Add a new spare part — Category selected from a dropdown, Model selected from a dropdown (optional — universal parts may have no model) | Planned |
| SP-03 | Edit an existing spare part | Planned |
| SP-04 | Delete a spare part with confirmation dialog | Planned |
| SP-05 | Display audit fields as read-only | Planned |
| SP-06 | Model dropdown includes a "Universal / Not model-specific" option for parts that apply to all models | Planned |

> FK dependencies: Spare_Parts → Category, Spare_Parts → Model (nullable)

---

## 8. Stock Management

| ID | Functionality | Status |
|---|---|---|
| STK-01 | List all stock entries in a searchable table showing Spare Part name and Brand name (not raw IDs) | Planned |
| STK-02 | Add a new stock entry — Spare Part and Brand selected from dropdowns | Planned |
| STK-03 | Edit an existing stock entry | Planned |
| STK-04 | Delete a stock entry with confirmation dialog | Planned |
| STK-05 | Display audit fields as read-only | Planned |

> FK dependencies: Stock → Spare_Parts, Stock → Brand

---

## 9. Service Management

| ID | Functionality | Status |
|---|---|---|
| SVC-01 | List all services in a searchable table | Planned |
| SVC-02 | Add a new service | Planned |
| SVC-03 | Edit an existing service | Planned |
| SVC-04 | Delete a service with confirmation dialog | Planned |
| SVC-05 | Display audit fields as read-only | Planned |

---

## 10. Role Management

| ID | Functionality | Status |
|---|---|---|
| ROL-01 | List all roles in a searchable table | Planned |
| ROL-02 | Add a new role | Planned |
| ROL-03 | Edit an existing role | Planned |
| ROL-04 | Delete a role with confirmation dialog | Planned |
| ROL-05 | Display audit fields as read-only | Planned |

---

## 11. Employee Management

| ID | Functionality | Status |
|---|---|---|
| EMP-01 | List all employees in a searchable table showing Role name and Supervisor name (not raw IDs) | Planned |
| EMP-02 | Add a new employee — Role selected from a dropdown, Supervisor selected from a dropdown of existing employees (optional) | Planned |
| EMP-03 | Edit an existing employee | Planned |
| EMP-04 | Delete an employee with confirmation dialog | Planned |
| EMP-05 | Display audit fields as read-only | Planned |
| EMP-06 | Supervisor dropdown is optional — a senior employee with no supervisor must be creatable | Planned |

> FK dependencies: Employee → Role, Employee → Employee (self-referencing supervisor)

---

## 12. Supplier Management

| ID | Functionality | Status |
|---|---|---|
| SUP-01 | List all suppliers in a searchable table | Planned |
| SUP-02 | Add a new supplier | Planned |
| SUP-03 | Edit an existing supplier | Planned |
| SUP-04 | Delete a supplier with confirmation dialog | Planned |
| SUP-05 | Display audit fields as read-only | Planned |

---

## 13. Shared and Cross-Cutting Features

| ID | Functionality | Applies To | Status |
|---|---|---|---|
| SHR-01 | Search bar on every list page — filters visible rows by keyword | All modules | Planned |
| SHR-02 | Pagination on every list page | All modules | Planned |
| SHR-03 | Success flash notification after Create, Update, and Delete | All modules | Planned |
| SHR-04 | Error flash notification when a database operation fails | All modules | Planned |
| SHR-05 | Delete confirmation modal — user must confirm before a record is deleted | All modules | Planned |
| SHR-06 | FK constraint error handling — if a record cannot be deleted due to a FK dependency, a clear user-facing message is shown instead of a raw database error | All modules with FK dependents | Planned |
| SHR-07 | Required field validation on all Create and Edit forms | All modules | Planned |
| SHR-08 | Audit fields displayed as read-only in Edit view | All modules | Planned |
| SHR-09 | FK dropdown fields populated from related tables — users never type raw database IDs | Model, Spare Parts, Stock, Employee | Planned |
| SHR-10 | Consistent sidebar navigation across all pages | All pages | Planned |
| SHR-11 | Active sidebar item highlighted for the current page | All pages | Planned |
| SHR-12 | Responsive layout for desktop and tablet screens | All pages | Planned |