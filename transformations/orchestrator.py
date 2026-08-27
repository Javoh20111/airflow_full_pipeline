import pandas as pd
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from transformations.transformation import (
    drop_duplicate, price_cleaner, housing_type_cleaner, validate_rooms,
    classify_listing_type, create_price_per_sqr, clean_district,
    clean_total_area_m2, clean_floor, clean_building_type, clean_layout,
    clean_built_year, clean_bathroom_column, clean_renovation_column,
    clean_amenities_and_nearby_column, add_near_metro_mentioned,
    remove_unnecesary_columns_and_fix_data_types
)
import logging
from sqlalchemy import create_engine, text
import io
log = logging.getLogger(__name__)

engine = create_engine(
    "postgresql+psycopg://postgres:8228@localhost:5432/airflow_apartments_db"
)


def extract():
    log.info("Extracting data from Bronze")
    query = """
        SELECT
            listing_id,
            source,
            seller_type,
            housing_type,
            region,
            district,
            rooms,
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
            description,
            date_scraped,
            url
        FROM bronze.airflow_apartments_tb
    """
    df = pd.read_sql(query, engine)
    log.info(f"Extracted {len(df)} rows from Bronze")
    return df 

transformations = [
    drop_duplicate,
    price_cleaner,
    classify_listing_type,
    housing_type_cleaner, 
    validate_rooms,
    create_price_per_sqr,
    clean_district,
    clean_total_area_m2,
    clean_floor,
    clean_building_type,
    clean_layout,
    clean_built_year,
    clean_bathroom_column,
    clean_renovation_column,
    clean_amenities_and_nearby_column,
    add_near_metro_mentioned,
    remove_unnecesary_columns_and_fix_data_types
]

def transfrom(df):
    for fn in transformations:
        df = fn(df)
    return df



def load_to_silver(df):
    log.info(f"Loading {len(df)} rows into Silver")

    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    columns = ", ".join(df.columns)

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE silver.airflow_apartments_tb"))
        raw_conn = conn.connection
        cursor = raw_conn.cursor()

        with cursor.copy(
            f"COPY silver.airflow_apartments_tb ({columns}) FROM STDIN WITH (FORMAT CSV)"
        ) as copy:
            copy.write(buffer.read())
    log.info("Silver load complete")



def main():
    df = extract()
    df = transfrom(df)
    load_to_silver(df)

if __name__ == "__main__":
    main()