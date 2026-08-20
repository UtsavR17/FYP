SELECT "Brand_Name", COUNT(*) FROM public."Brand"
    GROUP BY "Brand_Name" HAVING COUNT(*) > 1;

SELECT "CAT_desc", COUNT(*) FROM public."Category"
    GROUP BY "CAT_desc" HAVING COUNT(*) > 1;

SELECT "Role_Name", COUNT(*) FROM public."Role"
    GROUP BY "Role_Name" HAVING COUNT(*) > 1;

SELECT "Service_Name", COUNT(*) FROM public."Service"
    GROUP BY "Service_Name" HAVING COUNT(*) > 1;

SELECT "SupplierName", COUNT(*) FROM public."Supplier"
    GROUP BY "SupplierName" HAVING COUNT(*) > 1;

SELECT "Description", COUNT(*) FROM public."Model"
    GROUP BY "Description" HAVING COUNT(*) > 1;
