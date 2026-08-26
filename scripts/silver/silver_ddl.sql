
/*
===================================================================
Silver Layer: OLX Apartments Listings (Cleaned)
===================================================================
Purpose:
    Stores cleaned apartment listing data scraped from OLX, preserved in
    cleaned form to serve as the single source of truth for
    downstream gold analytics.
===================================================================
*/

CREATE TABLE silver.airflow_apartments_tb(
    listing_id TEXT PRIMARY KEY,
    price_usd NUMERIC(12,2) NOT NULL,
    price_per_sqr NUMERIC(10,2),
    listing_type VARCHAR(4),
    commission BOOLEAN,
    negotiable BOOLEAN,
    published_date DATE,
    date_scraped DATE,
    url TEXT,
    description TEXT,
    housing_type VARCHAR(15), 
    rooms INTEGER, 
    total_area_m2 NUMERIC(10,2), 
    floor INTEGER,
    total_floors INTEGER,
    building_type TEXT, 
    layout TEXT, 
    build_year INTEGER,
    age INTEGER,
    ceiling_height NUMERIC(3,2),
    bathroom TEXT, 
    furnished BOOLEAN, 
    renovation TEXT,
    seller_type TEXT,
    region TEXT,
    district TEXT,

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
    nearby_restaurant BOOLEAN,
    nearby_school BOOLEAN,
    nearby_shops BOOLEAN,
    nearby_supermarket BOOLEAN,
    near_metro_mentioned BOOLEAN,
    -- Metadata: when this row was loaded into the warehouse, not when the listing was published/scraped
    dwh_created_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);