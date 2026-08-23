/*
===================================================================
Bronze Layer: OLX Apartments Listings (Raw)
===================================================================
Purpose:
    Stores raw apartment listing data scraped from OLX, preserved in
    its original form to serve as the single source of truth for
    downstream silver/gold transformations. No cleaning, deduplication,
    or derived recalculation is performed at this layer.
===================================================================
*/

/* 
listing_id,source,seller_type,housing_type,region,district,rooms,living_area_m2,kitchen_area_m2,total_area_m2,floor,total_floors,building_type,layout,build_year,ceiling_height,bathroom,furnished,renovation,commission,amenities,nearby,negotiable,price,currency,published_date,description,date_scraped,url
 */


CREATE TABLE bronze.airflow_apartments_tb (
    listing_id TEXT PRIMARY KEY,
    source VARCHAR(15),
    seller_type VARCHAR(15),
    housing_type VARCHAR(15),
    region TEXT,
    district  TEXT,
    rooms INTEGER,
    living_area_m2 NUMERIC,
    kitchen_area_m NUMERIC,
    total_area_m2 NUMERIC,
    floor INTEGER,
    total_floors INTEGER,
    building_type TEXT,
    layout TEXT,
    build_year INTEGER,
    ceiling_height NUMERIC,
    bathroom  VARCHAR(20),
    furnished BOOLEAN,
    renovation TEXT,
    commission BOOLEAN,
    amenities TEXT,
    nearby TEXT,
    negotiable BOOLEAN,
    price NUMERIC NOT NULL,
    currency VARCHAR(15),
    published_date DATE,
    description TEXT,
    date_scraped DATE,
    url TEXT
)