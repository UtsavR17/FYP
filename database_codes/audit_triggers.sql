
-- ===============================================================================================================================
-- AUDIT TRIGGERS
-- How they work:
--   A trigger function is created once and is shared by all tables.
--   A trigger is then attached to each table individually.
--
--   INSERT trigger -> sets Date_Created = NOW() and Created_By = current user.
--   UPDATE trigger  --> sets Date_Updated = NOW() and Updated_By = current user.
--
--   auth.uid() is the Supabase authenticated user ID (UUID).
--   COALESCE falls back to 'system' if no authenticated session is active
--   (e.g. when you run seed scripts directly in the SQL Editor).
--
--   NEW refers to the row being inserted or updated inside a trigger.
--   RETURNS TRIGGER is the required return type for all trigger functions.

-- Single shared trigger function used by all 10 tables.
CREATE OR REPLACE FUNCTION set_audit_fields()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        NEW."Date_Created" := NOW();
        NEW."Created_By"  := COALESCE(
            (SELECT email FROM auth.users WHERE id = auth.uid()),
            'system'
        );
        -- On INSERT, ensuring update fields are NULL
        NEW."Date_Updated" := NULL;
        NEW."Updated_By"   := NULL;

    ELSIF (TG_OP = 'UPDATE') THEN
        -- Preserve  original Date_Created and Created_By - pas overwrite them
        NEW."Date_Created" := OLD."Date_Created";
        NEW."Created_By"   := OLD."Created_By";
        -- Set the update audit fields
        NEW."Date_Updated" := NOW();
        NEW."Updated_By"   := COALESCE(
            (SELECT email FROM auth.users WHERE id = auth.uid()),
            'system'
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- Attach the trigger to each 10 table.
-- BEFORE INSERT OR UPDATE ensures the audit fields are set before the row is saved.

CREATE OR REPLACE TRIGGER audit_color
    BEFORE INSERT OR UPDATE ON "Color"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

CREATE OR REPLACE TRIGGER audit_category
    BEFORE INSERT OR UPDATE ON "Category"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

CREATE OR REPLACE TRIGGER audit_role
    BEFORE INSERT OR UPDATE ON "Role"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

CREATE OR REPLACE TRIGGER audit_supplier
    BEFORE INSERT OR UPDATE ON "Supplier"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

CREATE OR REPLACE TRIGGER audit_brand
    BEFORE INSERT OR UPDATE ON "Brand"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

CREATE OR REPLACE TRIGGER audit_employee
    BEFORE INSERT OR UPDATE ON "Employee"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

CREATE OR REPLACE TRIGGER audit_model
    BEFORE INSERT OR UPDATE ON "Model"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

CREATE OR REPLACE TRIGGER audit_service
    BEFORE INSERT OR UPDATE ON "Service"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

CREATE OR REPLACE TRIGGER audit_spare_parts
    BEFORE INSERT OR UPDATE ON "Spare_Parts"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();

CREATE OR REPLACE TRIGGER audit_stock
    BEFORE INSERT OR UPDATE ON "Stock"
    FOR EACH ROW EXECUTE FUNCTION set_audit_fields();