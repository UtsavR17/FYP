SELECT "SP_id", "SP_name", "Model_Model_No"
FROM "Spare_Parts";


-- =============================================================================
-- SCRIPT 1: Remove direct Spare_Parts → Model relationship
-- Per supervisor: model compatibility is now handled via Compatibility table
-- =============================================================================

-- Drop the FK constraint first, then the column
ALTER TABLE public."Spare_Parts"
    DROP CONSTRAINT IF EXISTS "Spare_Parts_Model_FK";

ALTER TABLE public."Spare_Parts"
    DROP COLUMN IF EXISTS "Model_Model_No";


-- =============================================================================
-- SCRIPT 2: Make Stock.Size nullable
-- Per supervisor: Size should not be mandatory
-- =============================================================================

ALTER TABLE public."Stock"
    ALTER COLUMN "Size" DROP NOT NULL;




-- =============================================================================
-- SCRIPT 3: Create Compatibility table
-- Bridge table between Stock and Model
-- Implements Model M:N Stock with year range support
-- =============================================================================

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
        FOREIGN KEY ("Stock_Stock_ID")
        REFERENCES public."Stock" ("Stock_ID"),

    CONSTRAINT "Compatibility_Model_FK"
        FOREIGN KEY ("Model_Model_No")
        REFERENCES public."Model" ("Model_No"),

    CONSTRAINT "unique_compatibility"
        UNIQUE ("Stock_Stock_ID", "Model_Model_No", "Year_From", "Year_To")
);

-- Attach the shared audit trigger to Compatibility
CREATE OR REPLACE TRIGGER audit_compatibility
    BEFORE INSERT OR UPDATE ON public."Compatibility"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

-- Grant access to authenticated role (matches existing Phase 1 grants)
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Compatibility" TO authenticated;

-- Enable RLS
ALTER TABLE public."Compatibility" ENABLE ROW LEVEL SECURITY;

-- RLS policy — authenticated admin only
CREATE POLICY "admin_full_access" ON public."Compatibility"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);



-- =============================================================================
-- PREREQUISITE FOR SCRIPT 4
-- PurchaseOrder table — Supabase/PostgreSQL
-- Depends on: Supplier (already exists)
-- No Admin Panel module is built for this table at this stage.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public."PurchaseOrder" (
    "PurchaseOrderID"   INTEGER      GENERATED ALWAYS AS IDENTITY,
    "POrderDate"        DATE         NOT NULL,
    "ExpectedDate"      DATE         NOT NULL,
    "Status"            VARCHAR(30)  NOT NULL,
    "Supplier_SupplierID" INTEGER    NOT NULL,
    "Date_Created"      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"        VARCHAR(20)  NOT NULL DEFAULT 'system',
    "Date_Updated"      TIMESTAMPTZ,
    "Updated_By"        VARCHAR(20),

    CONSTRAINT "PurchaseOrder_PK"
        PRIMARY KEY ("PurchaseOrderID"),

    CONSTRAINT "PurchaseOrder_Supplier_FK"
        FOREIGN KEY ("Supplier_SupplierID")
        REFERENCES public."Supplier" ("SupplierID")
);

-- Audit trigger
CREATE OR REPLACE TRIGGER audit_purchase_order
    BEFORE INSERT OR UPDATE ON public."PurchaseOrder"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

-- Grant access to authenticated role
GRANT SELECT, INSERT, UPDATE, DELETE
    ON public."PurchaseOrder" TO authenticated;

-- Enable RLS
ALTER TABLE public."PurchaseOrder" ENABLE ROW LEVEL SECURITY;

-- RLS policy
CREATE POLICY "admin_full_access" ON public."PurchaseOrder"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

-- =============================================================================
-- SCRIPT 4: Create PurchaseOrderItem
-- Replaces the original PO_Stock concept from the Oracle DDL.
-- A PO line item references Spare_Parts at order creation time.
-- The Stock_Stock_ID FK is populated only at receiving time.
-- =============================================================================

-- Note: Run this after PurchaseOrder table exists.
-- PurchaseOrder must be created first (it has no dependency on this table).

CREATE TABLE IF NOT EXISTS public."PurchaseOrderItem" (
    "POItem_ID"           INTEGER        GENERATED ALWAYS AS IDENTITY,
    "PurchaseOrder_ID"    INTEGER        NOT NULL,
    "SP_id"               INTEGER        NOT NULL,
    "Quantity_Ordered"    INTEGER        NOT NULL,
    "BuyingPrice"         NUMERIC(10,2)  NOT NULL,
    "Size_Expected"       VARCHAR(20),
    "Stock_Stock_ID"      INTEGER,
    "Quantity_Received"   INTEGER,
    "DateReceived"        DATE,
    "Status"              VARCHAR(20)    NOT NULL DEFAULT 'Ordered',
    "Date_Created"        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    "Created_By"          VARCHAR(50)    NOT NULL DEFAULT 'system',
    "Date_Updated"        TIMESTAMPTZ,
    "Updated_By"          VARCHAR(50),

    CONSTRAINT "POItem_PK"
        PRIMARY KEY ("POItem_ID"),

    CONSTRAINT "POItem_PO_FK"
        FOREIGN KEY ("PurchaseOrder_ID")
        REFERENCES public."PurchaseOrder" ("PurchaseOrderID"),

    CONSTRAINT "POItem_SP_FK"
        FOREIGN KEY ("SP_id")
        REFERENCES public."Spare_Parts" ("SP_id"),

    CONSTRAINT "POItem_Stock_FK"
        FOREIGN KEY ("Stock_Stock_ID")
        REFERENCES public."Stock" ("Stock_ID")
);

CREATE OR REPLACE TRIGGER audit_po_item
    BEFORE INSERT OR UPDATE ON public."PurchaseOrderItem"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

GRANT SELECT, INSERT, UPDATE, DELETE ON public."PurchaseOrderItem" TO authenticated;

ALTER TABLE public."PurchaseOrderItem" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "admin_full_access" ON public."PurchaseOrderItem"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);



-- Widen Created_By and Updated_By on PurchaseOrder and PurchaseOrderItem
-- to accommodate email addresses up to 100 characters.

ALTER TABLE public."PurchaseOrder"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."PurchaseOrderItem"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Compatibility"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);


ALTER TABLE public."Supplier"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);



SELECT table_name, column_name, character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name IN ('Created_By', 'Updated_By')
  AND character_maximum_length < 100
ORDER BY table_name;



SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'Appointment'
ORDER BY ordinal_position;


SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'New_MotorBike'
ORDER BY ordinal_position;


SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'Customer', 'Customer_bike', 'New_MotorBike',
    'Sale', 'Appointment', 'appointment_service',
    'Appointment_Stock', 'Payment'
  )
ORDER BY tablename;



INSERT INTO public."Customer" (
    "FirstName", "LastName", "PhoneNumber",
    "Email", "Street", "Town", "NIC"
)
VALUES (
    'Test', 'Customer', '57001234',
    'test@example.com', 'Royal Road', 'Ebene', 'A1234567890123'
);

SELECT "CustomerID", "FirstName", "Date_Created", "Created_By"
FROM public."Customer"
WHERE "LastName" = 'Customer';



------------------------ changes to Appointment payemnt 
-- from this CONSTRAINT "unique_appointment_payment" UNIQUE ("Appointment_AppointmentID")

-- to this to be able to do partial deposit, remaining payments later similar to sales table 

ALTER TABLE public."Payment"
    DROP CONSTRAINT IF EXISTS "unique_appointment_payment";



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


-- Fix Created_By and Updated_By column sizes 
ALTER TABLE public."Supplier_Product"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Supplier_Model"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);


ALTER TABLE public."PurchaseOrderItem"
    DROP CONSTRAINT IF EXISTS "POItem_SupplierProduct_FK";

ALTER TABLE public."PurchaseOrderItem"
    ADD COLUMN IF NOT EXISTS "SupplierProduct_ID" INTEGER;

ALTER TABLE public."PurchaseOrderItem"
    ADD CONSTRAINT "POItem_SupplierProduct_FK"
        FOREIGN KEY ("SupplierProduct_ID")
        REFERENCES public."Supplier_Product" ("SupplierProduct_ID");


SELECT COUNT(*) FROM public."PO_NewMotorBike";

-----------------------
DROP TABLE IF EXISTS public."PO_NewMotorBike";

CREATE TABLE public."PO_NewMotorBike" (
    "POBike_ID"           INTEGER       GENERATED ALWAYS AS IDENTITY,
    "PurchaseOrder_ID"    INTEGER       NOT NULL,
    "Model_Model_No"      INTEGER       NOT NULL,
    "SupplierModel_ID"    INTEGER,
    "Color_Color"         VARCHAR(20)   NOT NULL,
    "BuyingPrice"         NUMERIC(10,2) NOT NULL,
    "New_MotorBike_NB_ID" INTEGER,
    "DateReceived"        DATE,
    "Status"              VARCHAR(20)   NOT NULL DEFAULT 'Ordered',
    "Date_Created"        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"          VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated"        TIMESTAMPTZ,
    "Updated_By"          VARCHAR(20),

    CONSTRAINT "PO_NewMotorBike_PK" PRIMARY KEY ("POBike_ID"),
    CONSTRAINT "POBike_PO_FK" FOREIGN KEY ("PurchaseOrder_ID")
        REFERENCES public."PurchaseOrder" ("PurchaseOrderID"),
    CONSTRAINT "POBike_Model_FK" FOREIGN KEY ("Model_Model_No")
        REFERENCES public."Model" ("Model_No"),
    CONSTRAINT "POBike_SupplierModel_FK" FOREIGN KEY ("SupplierModel_ID")
        REFERENCES public."Supplier_Model" ("SupplierModel_ID") ON DELETE SET NULL,
    CONSTRAINT "POBike_Color_FK" FOREIGN KEY ("Color_Color")
        REFERENCES public."Color" ("Color"),
    CONSTRAINT "POBike_NewMotorBike_FK" FOREIGN KEY ("New_MotorBike_NB_ID")
        REFERENCES public."New_MotorBike" ("NB_ID"),
    CONSTRAINT "POBike_unique_bike" UNIQUE ("New_MotorBike_NB_ID"),
    CONSTRAINT "POBike_Status_check" CHECK ("Status" IN ('Ordered', 'Received'))
);

CREATE OR REPLACE TRIGGER audit_po_newmotorbike
    BEFORE INSERT OR UPDATE ON public."PO_NewMotorBike"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

GRANT SELECT, INSERT, UPDATE, DELETE ON public."PO_NewMotorBike" TO authenticated;
ALTER TABLE public."PO_NewMotorBike" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin_full_access" ON public."PO_NewMotorBike"
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- Fix: without this, a catalogue entry that has ever been ordered can never be
-- deleted from the Supplier page (FK block). SET NULL keeps PO history intact.
ALTER TABLE public."PurchaseOrderItem" DROP CONSTRAINT IF EXISTS "POItem_SupplierProduct_FK";
ALTER TABLE public."PurchaseOrderItem"
    ADD CONSTRAINT "POItem_SupplierProduct_FK"
        FOREIGN KEY ("SupplierProduct_ID")
        REFERENCES public."Supplier_Product" ("SupplierProduct_ID") ON DELETE SET NULL;