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