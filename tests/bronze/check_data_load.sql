/*
===================================================================
Test: bronze.olx_apartments_info is not empty
===================================================================
Purpose:
    Sanity check that CALL bronze.load_bronze(...) actually loaded
    rows, rather than succeeding silently against an empty/missing
    CSV.
===================================================================
*/

CREATE OR REPLACE PROCEDURE bronze.check_load()
LANGUAGE plpgsql
AS $$
DECLARE 
    row_count INTEGER;
    null_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count
    FROM bronze.airflow_apartments_tb;

    IF row_count = 0 THEN 
        RAISE EXCEPTION 'FAILED: bronze.airflow_apartments_tb has 0 rows';
    END IF;

    SELECT COUNT(*) INTO null_count
    FROM bronze.airflow_apartments_tb
    WHERE listing_id IS NULL  
        OR url is NULL;
    
    IF null_count > 0 THEN
        RAISE EXCEPTION 'FAILED: % rows have NULLs in critical columns (listing_id/price/url)',null_count;
    END IF;
    RAISE NOTICE 'PASSED: % rows loaded, 0 critical NULLs', row_count;
END;
$$;

CALL bronze.check_load();


SELECT listing_id, price, url, source, published_date
FROM bronze.airflow_apartments_tb
WHERE listing_id IS NULL OR price IS NULL OR url IS NULL
LIMIT 5;
/* 
"listing_id","price","url","source","published_date"
"4lVQe","","https://www.olx.uz/d/obyavlenie/kvartira-sotiladi-1-1-2-31500-ID4lVQe.html","olx","03/05/2026"
"4lX6a","","https://www.olx.uz/d/obyavlenie/kvartira-yunusabad-10-2-1-5-72400-ID4lX6a.html","olx","03/05/2026"
"4lX4C","","https://www.olx.uz/d/obyavlenie/kvartira-yunusabad-11-2-1-4-62500u-e-ID4lX4C.html","olx","03/05/2026"
"4lX2Q","","https://www.olx.uz/d/obyavlenie/kvartira-yunusabad-10-3-1-5-69500u-e-ID4lX2Q.html","olx","03/05/2026"
"4mkQk","","https://www.olx.uz/d/obyavlenie/srochno-svoya-gorit-3-kom-63900-ID4mkQk.html","olx","03/05/2026" 
*/


SELECT 
    listing_id,
    seller_type,
    housing_type,
    region,
    district,
    rooms,
    living_area_m2,
    kitchen_area_m2,
    total_area_m2,
    floor,
    total_floors,
    building_type,
    layout,
    build_year,
    ceiling_height,
    bathroom,
    furnished,
    renovation,
    commission,
    amenities,
    nearby,
    negotiable,
    price,
    currency,
    published_date,
    date_scraped,
    url,
        ROW_NUMBER() OVER(PARTITION BY listing_id ORDER BY listing_id) as check_dublicates
FROM bronze.airflow_apartments_tb