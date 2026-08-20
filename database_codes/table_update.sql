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

-- Role and Employee were VARCHAR(50)  also widened for consistency.
ALTER TABLE public."Role"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);

ALTER TABLE public."Employee"
    ALTER COLUMN "Created_By" TYPE VARCHAR(100),
    ALTER COLUMN "Updated_By" TYPE VARCHAR(100);
