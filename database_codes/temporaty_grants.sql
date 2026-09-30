-- TEMPORARY DEVELOPMENT GRANTS
-- Grants SELECT, INSERT, UPDATE, DELETE on all Phase 1 tables to the anon role.
--
-- PURPOSE: Allow the Flask Admin Panel to perform CRUD operations during development, before Supabase Auth and RLS are implemented 

GRANT SELECT, INSERT, UPDATE, DELETE ON public."Color"       TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Category"    TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Brand"       TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Model"       TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Spare_Parts" TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Stock"       TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Service"     TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Role"        TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Employee"    TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public."Supplier"    TO anon;


-- PHASE 1 — DISABLE RLS FOR DEVELOPMENT
-- These tables were created without RLS but Supabase enabled it automatically.
ALTER TABLE public."Color"       DISABLE ROW LEVEL SECURITY;
ALTER TABLE public."Category"    DISABLE ROW LEVEL SECURITY;
ALTER TABLE public."Brand"       DISABLE ROW LEVEL SECURITY;
ALTER TABLE public."Model"       DISABLE ROW LEVEL SECURITY;
ALTER TABLE public."Spare_Parts" DISABLE ROW LEVEL SECURITY;
ALTER TABLE public."Stock"       DISABLE ROW LEVEL SECURITY;
ALTER TABLE public."Service"     DISABLE ROW LEVEL SECURITY;
ALTER TABLE public."Role"        DISABLE ROW LEVEL SECURITY;
ALTER TABLE public."Employee"    DISABLE ROW LEVEL SECURITY;
ALTER TABLE public."Supplier"    DISABLE ROW LEVEL SECURITY;