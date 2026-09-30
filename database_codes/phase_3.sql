-- =============================================================================
-- TASK 21 — PHASE 3 DATABASE TABLES
-- Run this entire script in the Supabase SQL Editor.
-- All Phase 1 tables, PurchaseOrder, and PurchaseOrderItem must already exist.
-- =============================================================================


-- =============================================================================
-- 1. CUSTOMER
-- No FK dependencies on other Phase 3 tables.
-- NIC, HomeNumber, PostCode changed from NUMBER to VARCHAR — see notes above.
-- =============================================================================
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

CREATE OR REPLACE TRIGGER audit_customer
    BEFORE INSERT OR UPDATE ON public."Customer"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

GRANT SELECT, INSERT, UPDATE, DELETE ON public."Customer" TO authenticated;
ALTER TABLE public."Customer" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."Customer"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);


-- =============================================================================
-- 2. CUSTOMER_BIKE
-- Depends on: Customer, Model.
-- Updated_By corrected from NVARCHAR2(1) to VARCHAR(20).
-- =============================================================================
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

    CONSTRAINT "Customer_bike_PK"
        PRIMARY KEY ("BikeID"),

    CONSTRAINT "Customer_bike_Model_FK"
        FOREIGN KEY ("Model_Model_No")
        REFERENCES public."Model" ("Model_No"),

    CONSTRAINT "Customer_bike_Customer_FK"
        FOREIGN KEY ("Customer_CustomerID")
        REFERENCES public."Customer" ("CustomerID")
);

CREATE OR REPLACE TRIGGER audit_customer_bike
    BEFORE INSERT OR UPDATE ON public."Customer_bike"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

GRANT SELECT, INSERT, UPDATE, DELETE ON public."Customer_bike" TO authenticated;
ALTER TABLE public."Customer_bike" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."Customer_bike"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);


-- =============================================================================
-- 3. NEW_MOTORBIKE
-- Depends on: Model, Color.
-- VIN corrected from NVARCHAR2(1) to VARCHAR(50).
-- "Warranty(Months)" renamed to "Warranty_Months" — parentheses in column
--   names cause SQL syntax errors in PostgreSQL.
-- "FuelTankCapacity(Litres)" renamed to "FuelTankCapacity".
-- Price changed from NUMBER to NUMERIC(10,2).
-- FuelTankCapacity changed from NUMBER to NUMERIC(5,2) — litres can be decimal.
-- Status: suggested values are 'Available' and 'Sold'.
-- =============================================================================
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

    CONSTRAINT "New_MotorBike_PK"
        PRIMARY KEY ("NB_ID"),

    CONSTRAINT "New_MotorBike_VIN_unique"
        UNIQUE ("VIN"),

    CONSTRAINT "New_MotorBike_Model_FK"
        FOREIGN KEY ("Model_Model_No")
        REFERENCES public."Model" ("Model_No"),

    CONSTRAINT "New_MotorBike_Color_FK"
        FOREIGN KEY ("Color_Color")
        REFERENCES public."Color" ("Color"),

    CONSTRAINT "New_MotorBike_Status_check"
        CHECK ("Status" IN ('Available', 'Sold'))
);

CREATE OR REPLACE TRIGGER audit_new_motorbike
    BEFORE INSERT OR UPDATE ON public."New_MotorBike"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

GRANT SELECT, INSERT, UPDATE, DELETE ON public."New_MotorBike" TO authenticated;
ALTER TABLE public."New_MotorBike" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."New_MotorBike"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);


-- =============================================================================
-- 4. SALE
-- Depends on: Customer, New_MotorBike, Employee.
-- Employee_EmployeeID included as nullable — pending supervisor confirmation.
-- UNIQUE on New_MotorBike_NB_ID — each bike can only be sold once.
-- =============================================================================
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

    CONSTRAINT "Sale_PK"
        PRIMARY KEY ("SaleID"),

    CONSTRAINT "Sale_unique_bike"
        UNIQUE ("New_MotorBike_NB_ID"),

    CONSTRAINT "Sale_Customer_FK"
        FOREIGN KEY ("Customer_CustomerID")
        REFERENCES public."Customer" ("CustomerID"),

    CONSTRAINT "Sale_New_MotorBike_FK"
        FOREIGN KEY ("New_MotorBike_NB_ID")
        REFERENCES public."New_MotorBike" ("NB_ID"),

    CONSTRAINT "Sale_Employee_FK"
        FOREIGN KEY ("Employee_EmployeeID")
        REFERENCES public."Employee" ("EmployeeID")
);

CREATE OR REPLACE TRIGGER audit_sale
    BEFORE INSERT OR UPDATE ON public."Sale"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

GRANT SELECT, INSERT, UPDATE, DELETE ON public."Sale" TO authenticated;
ALTER TABLE public."Sale" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."Sale"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);


-- =============================================================================
-- 5. APPOINTMENT
-- Depends on: Customer_bike, Employee.
-- Payment_PaymentID NOT included — circular FK removed (see context notes).
-- Appointment_time stored as TIME, not DATE — time-of-day value only.
-- AppointmentType and Status widened to VARCHAR(20) from VARCHAR(10).
-- Suggested AppointmentType values: Service, Repair, Inspection, Other.
-- Suggested Status values: Pending, Confirmed, In Progress, Completed,
--   Cancelled, No Show.
-- =============================================================================
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

    CONSTRAINT "Appointment_PK"
        PRIMARY KEY ("AppointmentID"),

    CONSTRAINT "Appointment_CustomerBike_FK"
        FOREIGN KEY ("Customer_bike_BikeID")
        REFERENCES public."Customer_bike" ("BikeID"),

    CONSTRAINT "Appointment_Employee_FK"
        FOREIGN KEY ("Employee_EmployeeID")
        REFERENCES public."Employee" ("EmployeeID")
);

CREATE OR REPLACE TRIGGER audit_appointment
    BEFORE INSERT OR UPDATE ON public."Appointment"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

GRANT SELECT, INSERT, UPDATE, DELETE ON public."Appointment" TO authenticated;
ALTER TABLE public."Appointment" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."Appointment"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);


-- =============================================================================
-- 6. APPOINTMENT_SERVICE (bridge table)
-- Depends on: Appointment, Service.
-- No audit fields — bridge tables record associations only.
-- Composite primary key on (AppointmentID, ServiceID).
-- Quantity is nullable — some appointments record services without a count.
-- =============================================================================
CREATE TABLE IF NOT EXISTS public."appointment_service" (
    "Appointment_AppointmentID" INTEGER NOT NULL,
    "Service_ServiceID"         INTEGER NOT NULL,
    "Quantity"                  INTEGER,

    CONSTRAINT "appointment_service_PK"
        PRIMARY KEY ("Appointment_AppointmentID", "Service_ServiceID"),

    CONSTRAINT "appt_service_Appointment_FK"
        FOREIGN KEY ("Appointment_AppointmentID")
        REFERENCES public."Appointment" ("AppointmentID"),

    CONSTRAINT "appt_service_Service_FK"
        FOREIGN KEY ("Service_ServiceID")
        REFERENCES public."Service" ("ServiceID")
);

GRANT SELECT, INSERT, UPDATE, DELETE ON public."appointment_service" TO authenticated;
ALTER TABLE public."appointment_service" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."appointment_service"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);


-- =============================================================================
-- 7. APPOINTMENT_STOCK (bridge table)
-- Depends on: Appointment, Stock.
-- No audit fields — bridge table.
-- Composite primary key on (AppointmentID, Stock_ID).
-- Quantity is NOT NULL — stock used in a service must have a count.
-- =============================================================================
CREATE TABLE IF NOT EXISTS public."Appointment_Stock" (
    "Appointment_AppointmentID" INTEGER NOT NULL,
    "Stock_Stock_ID"            INTEGER NOT NULL,
    "Quantity"                  INTEGER NOT NULL,

    CONSTRAINT "Appointment_Stock_PK"
        PRIMARY KEY ("Appointment_AppointmentID", "Stock_Stock_ID"),

    CONSTRAINT "Appt_Stock_Appointment_FK"
        FOREIGN KEY ("Appointment_AppointmentID")
        REFERENCES public."Appointment" ("AppointmentID"),

    CONSTRAINT "Appt_Stock_Stock_FK"
        FOREIGN KEY ("Stock_Stock_ID")
        REFERENCES public."Stock" ("Stock_ID")
);

GRANT SELECT, INSERT, UPDATE, DELETE ON public."Appointment_Stock" TO authenticated;
ALTER TABLE public."Appointment_Stock" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."Appointment_Stock"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);


-- =============================================================================
-- 8. PAYMENT
-- Depends on: Sale (nullable), Appointment (nullable).
-- One payment record covers either a sale OR an appointment — not both
--   at the same time (enforced by check constraint below).
-- UNIQUE on Appointment_AppointmentID — one payment per appointment maximum.
-- PaymentMethod suggested values: Cash, Card, Bank Transfer, Online.
-- PaymentType suggested values: Full Payment, Deposit, Instalment.
-- =============================================================================
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

    CONSTRAINT "Payment_PK"
        PRIMARY KEY ("PaymentID"),

    CONSTRAINT "unique_appointment_payment"
        UNIQUE ("Appointment_AppointmentID"),

    CONSTRAINT "Payment_Sale_FK"
        FOREIGN KEY ("Sale_SaleID")
        REFERENCES public."Sale" ("SaleID"),

    CONSTRAINT "Payment_Appointment_FK"
        FOREIGN KEY ("Appointment_AppointmentID")
        REFERENCES public."Appointment" ("AppointmentID"),

    CONSTRAINT "Payment_requires_reference"
        CHECK (
            "Sale_SaleID" IS NOT NULL
            OR "Appointment_AppointmentID" IS NOT NULL
        )
);

CREATE OR REPLACE TRIGGER audit_payment
    BEFORE INSERT OR UPDATE ON public."Payment"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

GRANT SELECT, INSERT, UPDATE, DELETE ON public."Payment" TO authenticated;
ALTER TABLE public."Payment" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."Payment"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);





ALTER TABLE public."Customer"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Customer_bike"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);


ALTER TABLE public."Appointment"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);
    


ALTER TABLE public."Sale"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);


ALTER TABLE public."Payment"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);



-- PO_NewMotorBike — bridge table linking a PurchaseOrder to a New_MotorBike
-- unit. Unlike PurchaseOrderItem, there is no Quantity/Status: each row
-- represents exactly one motorbike procured through that order.

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
    -- it, the same motorbike could be linked to two different purchase
    -- orders, which shouldn't be possible for a single physical unit.
    CONSTRAINT "PO_NewMotorBike_unique_bike"
        UNIQUE ("New_MotorBike_NB_ID")
);

GRANT SELECT, INSERT, UPDATE, DELETE ON public."PO_NewMotorBike" TO authenticated;
ALTER TABLE public."PO_NewMotorBike" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."PO_NewMotorBike"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);



-- What Spare Parts a Supplier actually sells, and at what price
CREATE TABLE IF NOT EXISTS public."Supplier_Product" (
    "SupplierProduct_ID"  INTEGER       GENERATED ALWAYS AS IDENTITY,
    "Supplier_SupplierID" INTEGER       NOT NULL,
    "SP_id"               INTEGER       NOT NULL,
    "Brand_Brand_ID"      INTEGER       NOT NULL,
    "BuyingPrice"         NUMERIC(10,2) NOT NULL,
    "Date_Created"        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"          VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated"        TIMESTAMPTZ,
    "Updated_By"          VARCHAR(20),

    CONSTRAINT "Supplier_Product_PK" PRIMARY KEY ("SupplierProduct_ID"),
    CONSTRAINT "Supplier_Product_Supplier_FK" FOREIGN KEY ("Supplier_SupplierID")
        REFERENCES public."Supplier" ("SupplierID"),
    CONSTRAINT "Supplier_Product_SP_FK" FOREIGN KEY ("SP_id")
        REFERENCES public."Spare_Parts" ("SP_id"),
    CONSTRAINT "Supplier_Product_Brand_FK" FOREIGN KEY ("Brand_Brand_ID")
        REFERENCES public."Brand" ("Brand_ID"),
    CONSTRAINT "Supplier_Product_unique"
        UNIQUE ("Supplier_SupplierID", "SP_id", "Brand_Brand_ID")
);

-- What Motorbike Models a Supplier actually sells, and at what price
CREATE TABLE IF NOT EXISTS public."Supplier_Model" (
    "SupplierModel_ID"    INTEGER       GENERATED ALWAYS AS IDENTITY,
    "Supplier_SupplierID" INTEGER       NOT NULL,
    "Model_Model_No"      INTEGER       NOT NULL,
    "BuyingPrice"         NUMERIC(10,2) NOT NULL,
    "Date_Created"        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"          VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated"        TIMESTAMPTZ,
    "Updated_By"          VARCHAR(20),

    CONSTRAINT "Supplier_Model_PK" PRIMARY KEY ("SupplierModel_ID"),
    CONSTRAINT "Supplier_Model_Supplier_FK" FOREIGN KEY ("Supplier_SupplierID")
        REFERENCES public."Supplier" ("SupplierID"),
    CONSTRAINT "Supplier_Model_Model_FK" FOREIGN KEY ("Model_Model_No")
        REFERENCES public."Model" ("Model_No"),
    CONSTRAINT "Supplier_Model_unique"
        UNIQUE ("Supplier_SupplierID", "Model_Model_No")
);