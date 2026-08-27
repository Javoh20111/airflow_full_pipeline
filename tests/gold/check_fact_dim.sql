
/*
===================================================================
Test: gold.dim_property stays meaningfully deduplicated
===================================================================
Purpose:
    dim_property is only useful as a dimension if it's substantially
    smaller than fact_listing (per the earlier check: ~2,800 unique
    combinations vs. ~88,000 listings). If the dedup logic in
    load_gold.sql ever broke — e.g. the UNIQUE NULLS NOT DISTINCT
    constraint got dropped, or the INSERT ... SELECT DISTINCT lost
    the DISTINCT — dim_property would balloon toward fact_listing's
    row count instead of staying small. This uses a generous 50%
    threshold as a smoke test, not a precise business rule; tighten
    it once you know your data's actual dedup ratio is stable.
===================================================================
*/
 
CREATE OR REPLACE PROCEDURE gold.check_ratio()
LANGUAGE plpgsql
AS $$
DECLARE
    dim_count INTEGER;
    fact_count INTEGER;
    ratio NUMERIC;
BEGIN
    SELECT COUNT(*) INTO dim_count FROM gold.dim_property;
    SELECT COUNT(*) INTO fact_count FROM gold.fact_listing;
 
    IF fact_count = 0 THEN
        RAISE EXCEPTION 'FAILED: gold.fact_listing is empty, cannot compute dedup ratio';
    END IF;
 
    ratio := dim_count::NUMERIC / fact_count;
 
    IF ratio > 0.5 THEN
        RAISE EXCEPTION
            'FAILED: gold.dim_property has % rows vs. % fact rows (ratio %) — deduplication may be broken',
            dim_count, fact_count, ROUND(ratio, 3);
    END IF;
 
    RAISE NOTICE 'PASSED: gold.dim_property (%) is % of gold.fact_listing (%)', dim_count, ROUND(ratio, 3), fact_count;
END;
$$;

CALL gold.check_ratio();