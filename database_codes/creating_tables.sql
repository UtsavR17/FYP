-- MOTORBIKE SALES AND SERVICING MANAGEMENT SYSTEM
-- Tables: Color, Category, Role, Supplier, Brand, Employee, Model, Service, Spare_Parts, Stock

-- 1. COLOR
-- No foreign key dependencies.
CREATE TABLE IF NOT EXISTS "Color" (
    "Color"       VARCHAR(20)  NOT NULL,
    "Date_Created" TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"  VARCHAR(20)  NOT NULL DEFAULT 'system',
    "Date_Updated" TIMESTAMPTZ,
    "Updated_By"  VARCHAR(20),
    CONSTRAINT "Color_PK" PRIMARY KEY ("Color")
);

-- 2. CATEGORY
-- No foreign key dependencies.
CREATE TABLE IF NOT EXISTS "Category" (
    "CAT_ID"       INTEGER      GENERATED ALWAYS AS IDENTITY,
    "CAT_desc"     VARCHAR(20)  NOT NULL,
    "Date_Created" TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"   VARCHAR(20)  NOT NULL DEFAULT 'system',
    "Date_Updated" TIMESTAMPTZ,
    "Updated_By"   VARCHAR(20),
    CONSTRAINT "Category_PK" PRIMARY KEY ("CAT_ID")
);

-- 3. ROLE
-- No foreign key dependencies.
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

-- 4. SUPPLIER
-- No foreign key dependencies.
CREATE TABLE IF NOT EXISTS "Supplier" (
    "SupplierID"   INTEGER       GENERATED ALWAYS AS IDENTITY,
    "SupplierName" VARCHAR(100)  NOT NULL,
    "Phone"        VARCHAR(20)   NOT NULL,
    "Email"        VARCHAR(100)  NOT NULL,
    "Address"      VARCHAR(255)  NOT NULL,
    "Country"      VARCHAR(100)  NOT NULL,
    "Date_Created" TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"   VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated" TIMESTAMPTZ,
    "Updated_By"   VARCHAR(20),
    CONSTRAINT "Supplier_PK" PRIMARY KEY ("SupplierID")
);

-- 5. BRAND
-- No foreign key dependencies.
CREATE TABLE IF NOT EXISTS "Brand" (
    "Brand_ID"        INTEGER     GENERATED ALWAYS AS IDENTITY,
    "Brand_Name"      VARCHAR(50) NOT NULL,
    "CountryOfOrigin" VARCHAR(40) NOT NULL,
    "Date_Created"    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "Created_By"      VARCHAR(20) NOT NULL DEFAULT 'system',
    "Date_Updated"    TIMESTAMPTZ,
    "Updated_By"      VARCHAR(20),
    CONSTRAINT "Brand_PK" PRIMARY KEY ("Brand_ID")
);

-- 6. EMPLOYEE
-- Depends on: Role
-- SupervisorID is a self-referencing FK (manager has no supervisor).
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


-- 7. MODEL
-- Depends on: Brand
CREATE TABLE IF NOT EXISTS "Model" (
    "Model_No"      INTEGER     GENERATED ALWAYS AS IDENTITY,
    "Brand_Brand_ID" INTEGER    NOT NULL,
    "Description"   VARCHAR(50) NOT NULL,
    "Date_Created"  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    "Created_By"    VARCHAR(20) NOT NULL DEFAULT 'system',
    "Date_Updated"  TIMESTAMPTZ,
    "Updated_By"    VARCHAR(20),
    CONSTRAINT "Model_PK"       PRIMARY KEY ("Model_No"),
    CONSTRAINT "Model_Brand_FK" FOREIGN KEY ("Brand_Brand_ID")
        REFERENCES "Brand" ("Brand_ID")
);

-- 8. SERVICE
-- No foreign key dependencies.
CREATE TABLE IF NOT EXISTS "Service" (
    "ServiceID"    INTEGER       GENERATED ALWAYS AS IDENTITY,
    "Service_Name" VARCHAR(50)   NOT NULL,
    "Description"  VARCHAR(255)  NOT NULL,
    "Cost"         NUMERIC(10,2) NOT NULL,
    "Date_Created" TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"   VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated" TIMESTAMPTZ,
    "Updated_By"   VARCHAR(20),
    CONSTRAINT "Service_PK" PRIMARY KEY ("ServiceID")
);

-- 9. SPARE_PARTS
-- Depends on: Category, Model (Model_No is null for universal parts)
CREATE TABLE IF NOT EXISTS "Spare_Parts" (
    "SP_id"           INTEGER      GENERATED ALWAYS AS IDENTITY,
    "SP_name"         VARCHAR(50)  NOT NULL,
    "SP_desc"         VARCHAR(255) NOT NULL,
    "Category_CAT_ID" INTEGER      NOT NULL,
    "Model_Model_No"  INTEGER,
    "Date_Created"    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    "Created_By"      VARCHAR(20)  NOT NULL DEFAULT 'system',
    "Date_Updated"    TIMESTAMPTZ,
    "Updated_By"      VARCHAR(20),
    CONSTRAINT "Spare_Parts_PK"          PRIMARY KEY ("SP_id"),
    CONSTRAINT "Spare_Parts_Category_FK" FOREIGN KEY ("Category_CAT_ID")
        REFERENCES "Category" ("CAT_ID"),
    CONSTRAINT "Spare_Parts_Model_FK"    FOREIGN KEY ("Model_Model_No")
        REFERENCES "Model" ("Model_No")
);

-- 10. STOCK
-- Depends on: Spare_Parts, Brand
CREATE TABLE IF NOT EXISTS "Stock" (
    "Stock_ID"         INTEGER       GENERATED ALWAYS AS IDENTITY,
    "Size"             VARCHAR(20)   NOT NULL,
    "QOH"              INTEGER       NOT NULL,
    "S_Price"          NUMERIC(10,2) NOT NULL,
    "Warranty"         INTEGER       NOT NULL,
    "Spare_Parts_SP_id" INTEGER      NOT NULL,
    "Brand_Brand_ID"   INTEGER       NOT NULL,
    "Date_Created"     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    "Created_By"       VARCHAR(20)   NOT NULL DEFAULT 'system',
    "Date_Updated"     TIMESTAMPTZ,
    "Updated_By"       VARCHAR(20),
    CONSTRAINT "Stock_PK"            PRIMARY KEY ("Stock_ID"),
    CONSTRAINT "Stock_Spare_Parts_FK" FOREIGN KEY ("Spare_Parts_SP_id")
        REFERENCES "Spare_Parts" ("SP_id"),
    CONSTRAINT "Stock_Brand_FK"      FOREIGN KEY ("Brand_Brand_ID")
        REFERENCES "Brand" ("Brand_ID")
);
























