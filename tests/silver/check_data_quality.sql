/*
===================================================================
Test: silver.airflow_apartments_tb value ranges
===================================================================
Purpose:
    Checks value ranges the schema itself can't enforce (data types
    allow these values; they're just not realistic). Extend the list
    below as more range rules are identified.
===================================================================
*/

CREATE OR REPLACE PROCEDURE silver.check_range()
LANGUAGE plpgsql
AS $$
DECLARE
    duplicates INTEGER;
    bad_price INTEGER;
    bad_rooms INTEGER;
    bad_build_year INTEGER;
BEGIN
    -- Detect duplicates-----------------------------------------------------------
    SELECT COUNT(*) INTO duplicates
    FROM(
        SELECT 
            listing_id,
            ROW_NUMBER() OVER(PARTITION BY listing_id) as row_num
        FROM silver.airflow_apartments_tb
    ) d
    WHERE d.row_num > 1;

    IF duplicates > 0 THEN
        RAISE NOTICE 'silver.olx_apartments has % duplicates', duplicates;
    END IF;
    -------------------------------------------------------------------------------

    -- Detect bad prices-----------------------------------------------------------
    SELECT COUNT(*) INTO bad_price
    FROM silver.airflow_apartments_tb
    WHERE price_usd <= 0;
 
    IF bad_price > 0 THEN
        RAISE EXCEPTION 'FAILED: % rows have price_usd <= 0', bad_price;
    END IF;
    -------------------------------------------------------------------------------

    -- Detect wrong rooms----------------------------------------------------------
    SELECT COUNT(*) INTO bad_rooms
    FROM silver.airflow_apartments_tb
    WHERE rooms IS NOT NULL AND rooms < 0;
 
    IF bad_rooms > 0 THEN
        RAISE EXCEPTION 'FAILED: % rows have negative rooms', bad_rooms;
    END IF;
    -------------------------------------------------------------------------------

    -- Detect wrong build_year-----------------------------------------------------
    SELECT COUNT(*) INTO bad_build_year
    FROM silver.airflow_apartments_tb
    WHERE build_year IS NOT NULL
      AND (build_year < 1900 OR build_year > EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER + 1);
 
    IF bad_build_year > 0 THEN
        RAISE EXCEPTION 'FAILED: % rows have an implausible build_year', bad_build_year;
    END IF;
    -------------------------------------------------------------------------------


    RAISE NOTICE 'PASSED: duplicates, price_usd, rooms, and build_year are within expected ranges';
END;
$$;

CALL silver.check_range();

/* 
One Problem found
FAILED: 3 rows have price_usd <= 0
 */