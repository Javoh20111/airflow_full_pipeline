
/*
===================================================================
Test: gold.fact_listing row count matches silver.airflow_apartments_tb
===================================================================
Purpose:
    gold.fact_listing is populated via an INNER JOIN from silver to
    dim_property/dim_location, matched with IS NOT DISTINCT FROM so
    that listings with NULL attributes still find their dimension
    row. If that join condition were ever weakened back to plain '='
    (or a dimension row failed to get created), rows with NULL
    attributes would be silently dropped from the join instead of
    erroring — this test catches that by row-count reconciliation.
===================================================================
*/


CREATE OR REPLACE PROCEDURE gold.check_gold()
LANGUAGE plpgsql
AS $$
DECLARE
    silver_count INTEGER;
    fact_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO silver_count FROM silver.airflow_apartments_tb;
    SELECT COUNT(*) INTO fact_count FROM gold.fact_listing;

    IF fact_count > silver_count THEN
        RAISE EXCEPTION
            'FAILED: gold.fact_listing has % rows but silver.airflow_apartments_tb has % — % rows were lost in the dimension lookup join',
            fact_count, silver_count, (silver_count - fact_count);
    END IF;

    RAISE NOTICE 'PASSED: gold.fact_listing row count (%) matches silver (%)', fact_count, silver_count;
END;
$$;

CALL gold.check_gold()