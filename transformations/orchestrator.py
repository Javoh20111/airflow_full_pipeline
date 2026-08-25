#---------------------------------------------------------------------------------
# ETL turdaki pipelini dasturlashga harakat qilaman
#---------------------------------------------------------------------------------

import pandas as pd
from transformation import drop_duplicate, price_cleaner, housing_type_cleaner, validate_rooms, classify_listing_type, create_price_per_sqr, clean_district, clean_total_area_m2, clean_floor
import logging
from sqlalchemy import create_engine, text
log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def extract():
    log.info("Extracting data from Bronze")
    engine = create_engine(
    "postgresql+psycopg://postgres:8228@localhost:5432/airflow_apartments_db"
    )
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
    clean_floor
]

def transfrom(df):
    for fn in transformations:
        df = fn(df)
    return df



def load_to_silver(df):
    pass



def main():
    df = extract()
    
    df = transfrom(df)
    load_to_silver(df)
if __name__ == "__main__":
    main()