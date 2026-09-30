-- adding UNIQUE constraints to the 10 tables where uniqueness is required
--COlor already has natural uniqueness as is Primary key
-- Employee, spare_parts and Stock have no appropriate single-column UNIQUE target

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



--====================================================================================
-- =============================================================================
-- DUPLICATE CONSTRAINT ADDITIONS
-- Customer.NIC, Customer.PhoneNumber, Customer_bike.VIN,
-- Customer_bike.RegistrationNumber
--
-- STEP 1: Run each duplicate check SELECT separately.
-- If any query returns rows, resolve those duplicates first.
-- STEP 2: Run the ALTER TABLE statements.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- STEP 1: Duplicate checks
-- Run each of these separately and confirm zero rows are returned.
-- ---------------------------------------------------------------------------

-- Check for duplicate NICs
SELECT "NIC", COUNT(*) AS occurrences
FROM public."Customer"
GROUP BY "NIC"
HAVING COUNT(*) > 1;

-- Check for duplicate PhoneNumbers
SELECT "PhoneNumber", COUNT(*) AS occurrences
FROM public."Customer"
GROUP BY "PhoneNumber"
HAVING COUNT(*) > 1;

-- Check for duplicate VINs
SELECT "VIN", COUNT(*) AS occurrences
FROM public."Customer_bike"
GROUP BY "VIN"
HAVING COUNT(*) > 1;

-- Check for duplicate RegistrationNumbers
SELECT "RegistrationNumber", COUNT(*) AS occurrences
FROM public."Customer_bike"
GROUP BY "RegistrationNumber"
HAVING COUNT(*) > 1;


-- ---------------------------------------------------------------------------
-- STEP 2: Add UNIQUE constraints
-- Only run after confirming all four duplicate checks above return zero rows.
-- ---------------------------------------------------------------------------

ALTER TABLE public."Customer"
    ADD CONSTRAINT "unique_customer_nic"
    UNIQUE ("NIC");

ALTER TABLE public."Customer"
    ADD CONSTRAINT "unique_customer_phone"
    UNIQUE ("PhoneNumber");

ALTER TABLE public."Customer_bike"
    ADD CONSTRAINT "unique_bike_vin"
    UNIQUE ("VIN");

ALTER TABLE public."Customer_bike"
    ADD CONSTRAINT "unique_bike_registration"
    UNIQUE ("RegistrationNumber");
