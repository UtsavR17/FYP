-- STEP 1: GRANT to authenticated role
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Color"       TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Category"    TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Brand"       TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Model"       TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Spare_Parts" TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Stock"       TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Service"     TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Role"        TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Employee"    TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Supplier"    TO authenticated;


-- STEP 2: REVOKE broad anon grants (replaced by RLS below)
-------------------------------------------------------------------------------
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Color"       FROM anon;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Category"    FROM anon;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Brand"       FROM anon;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Model"       FROM anon;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Spare_Parts" FROM anon;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Stock"       FROM anon;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Service"     FROM anon;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Role"        FROM anon;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Employee"    FROM anon;
REVOKE SELECT, INSERT, UPDATE, DELETE ON public."Supplier"    FROM anon;


-- STEP 3: ENABLE RLS on all Phase 1 tables
-------------------------------------------------------------------------------
ALTER TABLE public."Color"       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Category"    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Brand"       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Model"       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Spare_Parts" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Stock"       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Service"     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Role"        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Employee"    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Supplier"    ENABLE ROW LEVEL SECURITY;


-- CREATE RLS POLICIES
-- One policy per table.
-- FOR ALL covers SELECT, INSERT, UPDATE, and DELETE.
-- TO authenticated restricts access to logged-in users only.
-- USING (true) allows reading all rows an authenticated user has table access to.
-- WITH CHECK (true) allows writing all rows.
-------------------------------------------------------------------------------
CREATE POLICY "admin_full_access" ON public."Color"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "admin_full_access" ON public."Category"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "admin_full_access" ON public."Brand"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "admin_full_access" ON public."Model"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "admin_full_access" ON public."Spare_Parts"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "admin_full_access" ON public."Stock"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "admin_full_access" ON public."Service"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "admin_full_access" ON public."Role"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "admin_full_access" ON public."Employee"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "admin_full_access" ON public."Supplier"
    FOR ALL TO authenticated
    USING (true)
    WITH CHECK (true);




    -----------------------------------------------------------------
-- =============================================================================
-- HOTFIX Widen Created_By and Updated_By columns on all 10 tables
--
-- Root cause: these columns were VARCHAR(20) from the Oracle DDL, sized for
-- short usernames. Emails longer than 20 characters cause error 22001 (value too long) and roll back the entire operation.
-- Fix: widen to VARCHAR(100) on all Phase 1 tables VARCHAR(100) accommodates for real length email address.
-- Existing rows are not affected.

ALTER TABLE public."Color"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Category"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Brand"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Model"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Spare_Parts"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Stock"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Service"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Supplier"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

-- Role and Employee were VARCHAR(50) — also widened for consistency.
ALTER TABLE public."Role"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Employee"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);
