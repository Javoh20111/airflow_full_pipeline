/*
===================================================================
Load Gold Layer: Star Schema for OLX Apartments Listings
===================================================================
Purpose:
    Rebuilds gold.dim_property, gold.dim_location, gold.fact_listing,
    and gold.dim_listing_attributes from silver.airflow_apartments_tb.
 
    Load order follows the FK dependencies: dimensions first, then
    fact_listing (looks up each row's surrogate keys via a NULL-safe
    join), then dim_listing_attributes last, since it references
    fact_listing.listing_id.
 
    IS NOT DISTINCT FROM (rather than =) is used in the fact lookup
    join so listings with NULL attributes still match their dimension
    row — NULL = NULL is unknown under plain equality, but
    IS NOT DISTINCT FROM treats them as equal, matching how the
    NULLS NOT DISTINCT uniqueness constraints dedupe the dimensions.
 
Usage:
    CALL gold.load_gold();
===================================================================
*/

CREATE OR REPLACE PROCEDURE gold.load_gold()
LANGUAGE plpgsql
AS $$
DECLARE
    start_time TIMESTAMP WITH TIME ZONE := NOW();
    end_time TIMESTAMP WITH TIME ZONE;
BEGIN
    RAISE NOTICE '=========================';
    RAISE NOTICE 'Loading Gold Layer';
    RAISE NOTICE '=========================';

    -- All four tables are truncated together so Postgres can resolve
    -- the FK dependencies between them in one statement.
    RAISE NOTICE 'Truncating gold tables';
    TRUNCATE TABLE
        gold.dim_listing_attributes,
        gold.fact_listing,
        gold.dim_location,
        gold.dim_property
    RESTART IDENTITY;

    RAISE NOTICE 'Loading dim_property';
    INSERT INTO gold.dim_property (housing_type, building_type, layout, bathroom, furnished, renovation)
    SELECT DISTINCT 
        housing_type, building_type, layout, bathroom, furnished, renovation
    FROM silver.airflow_apartments_tb;

    RAISE NOTICE 'Loading dim_location';
    INSERT INTO gold.dim_location (region, district)
    SELECT DISTINCT
        region, district
    FROM silver.airflow_apartments_tb;
 
    RAISE NOTICE 'Loading fact_listing';
    INSERT INTO gold.fact_listing (
        listing_id, property_dim_id, location_dim_id,
        rooms, total_area_m2, floor, total_floors, build_year, age, ceiling_height,
        seller_type, price_usd, price_per_sqr, listing_type, negotiable, commission,
        date_scraped, description
    )
    SELECT
        s.listing_id,
        dp.property_dim_id,
        dl.location_dim_id,
        s.rooms, s.total_area_m2, s.floor, s.total_floors, s.build_year, s.age, s.ceiling_height,
        s.seller_type, s.price_usd, s.price_per_sqr, s.listing_type, s.negotiable, s.commission,
        s.date_scraped, s.description
    FROM silver.airflow_apartments_tb s
    -- Inner joins are safe (not left joins): both dimension tables were
    -- just built via SELECT DISTINCT from these same silver rows, so a
    -- match is guaranteed to exist for every listing.
    JOIN gold.dim_property dp
        ON s.housing_type   IS NOT DISTINCT FROM dp.housing_type
       AND s.building_type  IS NOT DISTINCT FROM dp.building_type
       AND s.layout         IS NOT DISTINCT FROM dp.layout
       AND s.bathroom       IS NOT DISTINCT FROM dp.bathroom
       AND s.furnished      IS NOT DISTINCT FROM dp.furnished
       AND s.renovation     IS NOT DISTINCT FROM dp.renovation
    JOIN gold.dim_location dl
        ON s.region   IS NOT DISTINCT FROM dl.region
       AND s.district IS NOT DISTINCT FROM dl.district;

    RAISE NOTICE 'Loading dim_listing_attributes';
    INSERT INTO gold.dim_listing_attributes (
        listing_id,
        amenity_air_conditioning, amenity_balcony, amenity_cable_tv,
        amenity_internet, amenity_kitchen, amenity_refrigerator,
        amenity_tv, amenity_telephone, amenity_washing_machine,
        nearby_bus_stop, nearby_cafe, nearby_clinic,
        nearby_entertainment, nearby_green_area, nearby_hospital,
        nearby_kindergarten, nearby_park, nearby_parking,
        nearby_playground, near_metro_mentioned, nearby_restaurant,
        nearby_school, nearby_shops, nearby_supermarket
    )
    SELECT
        listing_id,
        amenity_air_conditioning, amenity_balcony, amenity_cable_tv,
        amenity_internet, amenity_kitchen, amenity_refrigerator,
        amenity_tv, amenity_telephone, amenity_washing_machine,
        nearby_bus_stop, nearby_cafe, nearby_clinic,
        nearby_entertainment, nearby_green_area, nearby_hospital,
        nearby_kindergarten, nearby_park, nearby_parking,
        nearby_playground, near_metro_mentioned, nearby_restaurant,
        nearby_school, nearby_shops, nearby_supermarket
    FROM silver.airflow_apartments_tb;

    end_time := NOW();
    RAISE NOTICE 'Load duration: % seconds',
        EXTRACT(EPOCH FROM (end_time - start_time));
 
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error loading gold layer: %', SQLERRM;
        RAISE;
END;
$$;

call gold.load_gold();