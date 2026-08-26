/*
===================================================================
Gold Layer: Star Schema for OLX Apartments Listings
===================================================================
Purpose:
    dim_property and dim_location are deduplicated dimension tables
    (one row per unique attribute combination), each with a surrogate
    key referenced by fact_listing. dim_listing_attributes is a
    per-listing satellite table (one row per listing, same grain as
    the fact table) rather than a deduplicated dimension, since the
    23 amenity/nearby booleans are unlikely to repeat identically
    often enough to be worth deduplicating and joining on.

    Creation order matters for the FK dependencies below:
    dim_property and dim_location first (fact_listing references
    them), then fact_listing, then dim_listing_attributes (which
    references fact_listing).

    Several dim_property/dim_location attribute columns are nullable,
    so their uniqueness uses NULLS NOT DISTINCT (Postgres 15+) so
    that rows sharing the same NULLs are treated as duplicates rather
    than each getting their own row. See load_gold.sql for how these
    are populated.
===================================================================
*/

-- ---------------------------------------------------------------
-- dim_property (deduplicated)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_property (
    property_dim_id SERIAL PRIMARY KEY,
    housing_type TEXT,
    building_type TEXT,
    layout TEXT,
    bathroom TEXT,
    furnished BOOLEAN,
    renovation TEXT,
    CONSTRAINT ux_dim_property_natural_key
        UNIQUE NULLS NOT DISTINCT (housing_type, building_type, layout, bathroom, furnished, renovation)
);

-- ---------------------------------------------------------------
-- dim_location (deduplicated)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_location (
    location_dim_id SERIAL PRIMARY KEY,
    region TEXT,
    district TEXT,
    CONSTRAINT ux_dim_location_natural_key
        UNIQUE NULLS NOT DISTINCT (region, district)
);

-- ---------------------------------------------------------------
-- fact_listing
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.fact_listing (
    listing_id TEXT PRIMARY KEY,
    property_dim_id INTEGER NOT NULL REFERENCES gold.dim_property (property_dim_id),
    location_dim_id INTEGER NOT NULL REFERENCES gold.dim_location (location_dim_id),

    rooms INTEGER,
    total_area_m2 NUMERIC(10,2),
    floor INTEGER,
    total_floors INTEGER,
    build_year INTEGER,
    age INTEGER,
    ceiling_height NUMERIC(3,2),

    seller_type TEXT,
    price_usd NUMERIC(12,2) NOT NULL,
    price_per_sqr NUMERIC(10,2),
    listing_type TEXT,
    negotiable BOOLEAN,
    commission BOOLEAN,
    date_scraped DATE,
    description TEXT
);

-- ---------------------------------------------------------------
-- dim_listing_attributes (per-listing satellite, not deduplicated)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.dim_listing_attributes (
    listing_id TEXT PRIMARY KEY REFERENCES gold.fact_listing (listing_id),

    amenity_air_conditioning BOOLEAN,
    amenity_balcony BOOLEAN,
    amenity_cable_tv BOOLEAN,
    amenity_internet BOOLEAN,
    amenity_kitchen BOOLEAN,
    amenity_refrigerator BOOLEAN,
    amenity_tv BOOLEAN,
    amenity_telephone BOOLEAN,
    amenity_washing_machine BOOLEAN,

    nearby_bus_stop BOOLEAN,
    nearby_cafe BOOLEAN,
    nearby_clinic BOOLEAN,
    nearby_entertainment BOOLEAN,
    nearby_green_area BOOLEAN,
    nearby_hospital BOOLEAN,
    nearby_kindergarten BOOLEAN,
    nearby_park BOOLEAN,
    nearby_parking BOOLEAN,
    nearby_playground BOOLEAN,
    near_metro_mentioned BOOLEAN,
    nearby_restaurant BOOLEAN,
    nearby_school BOOLEAN,
    nearby_shops BOOLEAN,
    nearby_supermarket BOOLEAN
);