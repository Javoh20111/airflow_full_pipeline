# Purpose: Defines an Airflow DAG that schedules a daily web scraping task for apartment listings using the custom OLXScraper module.
import sys
from pathlib import Path
from airflow import DAG
from airflow.decorators import task
from datetime import datetime

# Dynamically add the project root to sys.path to allow importing local project modules in Airflow
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scraper.scraper import OLXScraper
from scraper.config import MAX_PAGES

@task(task_id="scrape_data")
def run(max_pages=MAX_PAGES, max_listings=10):
    scraper = OLXScraper()
    return scraper.run(
        max_pages=max_pages,
        max_listings=max_listings,
    )

with DAG(
    dag_id="Apartment_pipeline",
    start_date=datetime(2026,8,22),
    schedule="@daily",
    catchup=False # Avoid backfilling runs between the start_date and current date
) as dag:

    scrape = run()