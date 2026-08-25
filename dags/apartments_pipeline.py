# Purpose: Defines an Airflow DAG that schedules a daily web scraping task for apartment listings using the custom OLXScraper module.
import sys
import pandas as pd
import logging
from sqlalchemy import create_engine, text
from pathlib import Path
from airflow import DAG
from airflow.decorators import task
from datetime import datetime

# Dynamically add the project root to sys.path to allow importing local project modules in Airflow
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CSV_PATH = "/Users/javohireshonov/Desktop/Study/Projects/airflow_full_pipeline/data/raw/olx_apartments.csv"

log = logging.getLogger(__name__)

from scraper.scraper import OLXScraper
from scraper.config import MAX_PAGES


## ===============================================================================
##                       Scrape data
## ===============================================================================
@task(task_id="scrape_data")
def run(max_pages=MAX_PAGES, max_listings=2):

    start_time = datetime.now()

    log.info("Started scraping data")
    scraper = OLXScraper()

    new_listings = scraper.run(
        max_pages=max_pages,
        max_listings=max_listings,
    )

    end_time = datetime.now()
    duration = end_time - start_time

    log.info(f"""
    Scraping completed
    ------------------
    Pages: {max_pages}
    Listing limit: {max_listings}
    New listings: {new_listings}
    Duration: {duration}
    """)

    return new_listings


## ===============================================================================
##                       Load Data
## ===============================================================================
engine = create_engine(
    "postgresql+psycopg://postgres:8228@localhost:5432/airflow_apartments_db"
)
@task(task_id="Load_bronze")
def load_bronze():
    start_time = datetime.now()
    log.info("Starting Bronze load")

    with engine.begin() as conn:

        log.info("Truncating Bronze table")
        conn.execute(
            text("TRUNCATE TABLE bronze.airflow_apartments_tb")
        )

        # -------------------------
        # Load into PostgreSQL
        # -------------------------


        log.info("Loading data into Bronze")
        raw_conn = conn.connection
        cursor = raw_conn.cursor()
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            with raw_conn.cursor() as cur:
                with cur.copy("COPY bronze.airflow_apartments_tb FROM STDIN WITH (FORMAT CSV, HEADER)") as copy:
                    copy.write(f.read())


    end_time = datetime.now()
    duration = end_time - start_time

    log.info(f"Bronze load completed in {duration}")


## ===============================================================================
##                       Test bronze layer
## ===============================================================================

@task(task_id = "bronze_quality_check")
def bronze_quality_check():
    log.info("Starting Bronze quality check")

    # Note: Stored procedure already created and stored in "../tests/bronze/check_data_load.sql"
    with engine.begin() as conn:
        conn.execute(text("""CALL bronze.check_load();"""))
    log.info("Bronze quality check passed")


## ===============================================================================
##                       TRANSFORM
## ===============================================================================



with DAG(
    dag_id="Apartment_pipeline",
    start_date=datetime(2026,8,22),
    schedule="@daily",
    catchup=False # Avoid backfilling runs between the start_date and current date
) as dag:

    scrape = run()
    bronze = load_bronze()
    bronze_quality_check = bronza_quality_check()

    scrape >> bronze >> bronze_quality_check

