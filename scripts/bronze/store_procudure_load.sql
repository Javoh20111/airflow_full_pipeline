/*
===================================================================
Load Bronze Layer: OLX Apartments Listings
===================================================================
Purpose:
    Loads the cleaned dataset CSV into bronze.airflow_apartments_tb.
    Uses psql's client-side \copy so the file is read from wherever
    this script is run, rather than requiring the Postgres server
    process itself to have filesystem access to the file.
 
Usage:
    Run from the repository root using psql:
        psql -U <user> -d apartments_dwh_proj -f load_bronze.sql
 
    The path below is relative to the repository root — adjust the
    working directory (not the path) if running from elsewhere.
===================================================================
*/
 
-- Clear existing rows so this script is safe to re-run
CREATE OR REPLACE PROCEDURE bronze.load_bronze()
LANGUAGE plpgsql
AS $$
DECLARE
    start_time TIMESTAMP WITH TIME ZONE := NOW();
    end_time TIMESTAMP WITH TIME ZONE;
BEGIN
    start_time := NOW();
    RAISE NOTICE'=========================';
    RAISE NOTICE'Loading Bronze Layer';
    RAISE NOTICE'=========================';

    
    TRUNCATE TABLE bronze.airflow_apartments_tb;

    COPY bronze.airflow_apartments_tb
    FROM '/Users/javohireshonov/Desktop/Study/Projects/DataWarehouse/dataset/database.csv'
    WITH (
        FORMAT CSV,
        HEADER
    );
    end_time := NOW();
    RAISE NOTICE 'Load duration: % seconds',
    EXTRACT(EPOCH FROM (end_time - start_time));
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Error loading bronze layer: %', SQLERRM;
END;
$$;

CALL bronze.load_bronze()


SELECT *
FROM bronze.airflow_apartments_tb
LIMIT 10;
