DROP TABLE IF EXISTS bronze.airflow_apartments_tb;

CREATE TABLE bronze.airflow_apartments_tb (
    listing_id VARCHAR(64),
    source VARCHAR(100),
    seller_type VARCHAR(50),
    housing_type VARCHAR(50),
    region VARCHAR(100),
    district VARCHAR(100),
    rooms NUMERIC,
    -- float64 in source
    living_area_m2 NUMERIC,
    kitchen_area_m2 NUMERIC,
    total_area_m2 NUMERIC,
    floor NUMERIC,
    -- float64 in source
    total_floors NUMERIC,
    -- float64 in source
    building_type VARCHAR(100),
    layout VARCHAR(100),
    build_year NUMERIC,
    -- float64 in source
    ceiling_height NUMERIC,
    bathroom VARCHAR(50),
    furnished NUMERIC,
    -- float64 in source, DO NOT bool-cast in Python
    renovation VARCHAR(100),
    commission NUMERIC,
    amenities TEXT,
    -- comma-separated string, not JSON
    nearby TEXT,
    -- comma-separated string, not JSON
    negotiable NUMERIC,
    -- int64 in source, DO NOT bool-cast in Python
    price NUMERIC,
    currency VARCHAR(10),
    published_date VARCHAR(20),
    -- raw string "DD/MM/YYYY", parse in silver
    description TEXT,
    date_scraped VARCHAR(20),
    url TEXT
);