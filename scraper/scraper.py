"""
OLX.uz apartment scraper.
 
Pipeline:
  1. Iterate through category pages (?page=1 … ?page=N)
  2. Collect individual listing URLs from each page
  3. Fetch each detail page and parse characteristics
  4. Skip already-seen listing IDs (deduplication)
  5. Append new rows to CSV — never overwrite existing data
 
Run manually (all pages):
    python3 scraper/scraper.py
 
Test run — 1 page only:
    python3 scraper/scraper.py --pages 1

Scheduling:
    Run this script from Airflow or cron. Each invocation performs one scrape
    cycle and exits; the scheduler owns the "run again later" decision.
"""
 
import argparse
import json
import logging
import os
import re
import signal
import sys
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
 
import pandas as pd
import requests
from bs4 import BeautifulSoup
from bs4 import FeatureNotFound
try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover - optional transport
    curl_requests = None
 
# Resolve paths relative to this file so the script works regardless of CWD
_SCRIPT_DIR  = Path(__file__).resolve().parent   # .../scraper/
_PROJECT_DIR = _SCRIPT_DIR.parent                # .../Tashkent apartment analysis/
 
sys.path.insert(0, str(_SCRIPT_DIR))
from config import (
    BASE_URL, BREADCRUMB_SKIP, COLUMNS, DELAY_MAX, DELAY_MIN, FIELD_MAP,
    HEADERS, MAX_PAGES, MAX_RETRIES, BACKOFF_BASE,
    OUTPUT_DIR, LOG_DIR, CSV_FILENAME, UZBEKISTAN_REGIONS, VALUE_TRANSLATIONS,
)
 
# Absolute paths — always land inside the project no matter where you run from
_OUTPUT_DIR = (_PROJECT_DIR / OUTPUT_DIR).resolve()
_LOG_DIR    = (_PROJECT_DIR / LOG_DIR).resolve()
 
shutdown_requested = False


class FetchBlockedError(RuntimeError):
    """Raised when OLX blocks the scraper instead of returning a page."""
 
# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = _LOG_DIR / f"scraper_{datetime.now():%Y%m%d}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)
 
 
def _build_soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        return BeautifulSoup(html, "html.parser")
 
 
# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------
# curl_cffi impersonation profiles to cycle through on repeated 403s
_IMPERSONATION_PROFILES = ["chrome124", "chrome120", "chrome119", "chrome116", "chrome110"]


class OLXScraper:
 
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.browser_session = None
        self._impersonate_index = 0
        if curl_requests is not None:
            self.browser_session = curl_requests.Session(
                impersonate=_IMPERSONATION_PROFILES[0]
            )
            self.browser_session.headers.update(HEADERS)
            self._warmup_browser_session()
        self.csv_path = _OUTPUT_DIR / CSV_FILENAME
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.seen_ids: set[str] = self._load_existing_ids()
        log.info(f"Loaded {len(self.seen_ids)} already-scraped IDs from {self.csv_path}")

    def _warmup_browser_session(self):
        """
        Visit the OLX homepage first so the session accumulates cookies and
        a realistic browsing history before we hit category pages.  This
        significantly reduces the chance of a 403 on the first real request.
        """
        warmup_urls = [
            "https://www.olx.uz/",
            "https://www.olx.uz/nedvizhimost/",
        ]
        for wu_url in warmup_urls:
            try:
                log.info(f"Warming up browser session: {wu_url}")
                r = self.browser_session.get(wu_url, timeout=30)
                log.info(f"  Warmup {wu_url} → HTTP {r.status_code}")
                time.sleep(random.uniform(2.0, 4.5))
            except Exception as exc:
                log.warning(f"  Warmup request failed (non-fatal): {exc}")
 
    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------
    def _load_existing_ids(self) -> set[str]:
        if self.csv_path.exists():
            try:
                df = pd.read_csv(self.csv_path, usecols=["listing_id", "url"], dtype=str)
                ids: set[str] = set()
                # Add numeric IDs stored in listing_id column
                ids.update(df["listing_id"].dropna())
                # ALSO add the URL-slug form so URL-based duplicate check works
                # even when listing_id was overwritten with a numeric ID by __NEXT_DATA__
                for url in df["url"].dropna():
                    slug = self._extract_id(url)
                    ids.add(slug)
                return ids
            except Exception as e:
                log.warning(f"Could not read existing CSV: {e}")
        return set()
 
    # ------------------------------------------------------------------
    # HTTP — rate-limit handling + exponential backoff
    # ------------------------------------------------------------------
    def _get(self, url: str) -> BeautifulSoup | None:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._request(url)
 
                if resp.status_code == 200:
                    return _build_soup(resp.text)
 
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", BACKOFF_BASE ** attempt))
                    log.warning(f"429 rate-limited. Sleeping {wait}s …")
                    time.sleep(wait)
                    continue
 
                if resp.status_code == 403:
                    log.error(
                        "HTTP 403 from OLX. The request was blocked, not empty. "
                        "Install dependencies with `pip install -r scraper/requirements.txt` "
                        "so the browser-like transport is available, then retry."
                    )
                    raise FetchBlockedError(f"OLX returned HTTP 403 for {url}")

                if resp.status_code == 404:
                    log.warning(f"HTTP 404 — skipping {url}")
                    return None
 
                log.warning(f"HTTP {resp.status_code} attempt {attempt}/{MAX_RETRIES}: {url}")
                time.sleep(BACKOFF_BASE ** attempt)
 
            except requests.RequestException as exc:
                log.error(f"Request error attempt {attempt}/{MAX_RETRIES}: {exc}")
                time.sleep(BACKOFF_BASE ** attempt)
 
        log.error(f"Giving up after {MAX_RETRIES} attempts: {url}")
        return None

    def _next_impersonation(self) -> str:
        """Cycle to the next impersonation profile and return it."""
        self._impersonate_index = (
            self._impersonate_index + 1
        ) % len(_IMPERSONATION_PROFILES)
        return _IMPERSONATION_PROFILES[self._impersonate_index]

    def _request(self, url: str):
        """
        Try curl_cffi browser-impersonation session first (most reliable against
        OLX's bot detection).  Fall back to plain requests only if curl_cffi is
        unavailable.  On 403, rotate the impersonation profile and retry up to
        len(_IMPERSONATION_PROFILES) times before giving up.
        """
        if self.browser_session is None:
            # curl_cffi not installed — use plain requests and let _get() handle 403
            return self.session.get(url, timeout=30)

        # Try each impersonation profile in turn
        for attempt in range(len(_IMPERSONATION_PROFILES)):
            try:
                resp = self.browser_session.get(url, timeout=30)
            except Exception as exc:
                log.warning(f"curl_cffi request error (attempt {attempt + 1}): {exc}")
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                continue

            if resp.status_code != 403:
                return resp

            # 403 — rotate profile and retry after a human-like pause
            next_profile = self._next_impersonation()
            log.warning(
                f"HTTP 403 with profile '{_IMPERSONATION_PROFILES[self._impersonate_index - 1 if self._impersonate_index > 0 else len(_IMPERSONATION_PROFILES) - 1]}'; "
                f"rotating to '{next_profile}' and retrying …"
            )
            # Re-create session with new profile so TLS fingerprint fully changes
            self.browser_session = curl_requests.Session(impersonate=next_profile)
            self.browser_session.headers.update(HEADERS)
            delay = random.uniform(4.0, 9.0)
            log.info(f"  Waiting {delay:.1f}s before retry …")
            time.sleep(delay)

        # All profiles exhausted — return last response (403) so _get() can log it
        log.warning("All impersonation profiles exhausted; returning last response.")
        return resp
 
    def _delay(self):
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
 
    # ------------------------------------------------------------------
    # Listing page — collect detail URLs
    # ------------------------------------------------------------------
    def _get_listing_urls(self, page: int) -> list[str]:
        url = f"{BASE_URL}?page={page}"
        log.info(f"Fetching listing page {page}: {url}")
        soup = self._get(url)
        if not soup:
            return []
 
        links: list[str] = []
        seen_on_page: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/d/obyavlenie/" not in href:
                continue
            full = ("https://www.olx.uz" + href) if href.startswith("/") else href
            full = full.split("?")[0]
            if full not in seen_on_page:
                seen_on_page.add(full)
                links.append(full)
 
        log.info(f"  → {len(links)} unique listing URLs on page {page}")
        return links
 
    # ------------------------------------------------------------------
    # Detail page — parse all fields
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_id(url: str) -> str:
        m = re.search(r"-ID([A-Za-z0-9]+)\.html", url)
        return m.group(1) if m else url
 
    def _parse_detail(self, url: str) -> dict | None:
        soup = self._get(url)
        if not soup:
            return None
 
        listing: dict = {col: None for col in COLUMNS}
        listing["url"]          = url
        listing["listing_id"]   = self._extract_id(url)
        listing["source"]       = "olx"
        listing["date_scraped"] = datetime.now().strftime("%Y-%m-%d")
 
        # 1. Try __NEXT_DATA__ JSON (Next.js sites embed data here)
        next_script = soup.find("script", id="__NEXT_DATA__")
        if next_script:
            try:
                data = json.loads(next_script.string or "")
                self._parse_next_data(data, listing)
            except (json.JSONDecodeError, AttributeError):
                pass
 
        # 2. Characteristics from HTML (fills any gap left by __NEXT_DATA__)
        self._extract_characteristics(soup, listing)
 
        # 3. Price
        if listing["price"] is None:
            listing["price"], listing["currency"] = self._extract_price(soup)
 
        # 4. Region + district from breadcrumb
        if listing["region"] is None or listing["district"] is None:
            self._extract_location(soup, listing)
 
        # 5. Description  (treat empty string same as None — __NEXT_DATA__ may
        #    set it to "" when the field is blank, so the HTML fallback must run)
        if not listing["description"]:
            listing["description"] = self._extract_description(soup)
 
        # 6. Seller type — OLX renders this in the seller card, not as a
        #    characteristic label, so FIELD_MAP cannot catch it.
        if listing["seller_type"] is None:
            listing["seller_type"] = self._extract_seller_type(soup)
 
        # 7. Amenities ("В квартире есть: ...")
        if listing["amenities"] is None:
            listing["amenities"] = self._extract_amenities(soup)
 
        # 8. Nearby ("Рядом есть: ...")
        if listing["nearby"] is None:
            listing["nearby"] = self._extract_nearby(soup)
 
        # 9. Negotiable ("Договорная" anywhere near the price block)
        if listing["negotiable"] is None:
            listing["negotiable"] = self._extract_negotiable(soup)
 
        # 10. Published date
        if listing["published_date"] is None:
            listing["published_date"] = self._extract_published_date(soup)
 
        return listing
 
    # ------------------------------------------------------------------
    # Amenities  — "В квартире есть: item1, item2, ..."
    # ------------------------------------------------------------------
    # Russian label → English tag for each possible amenity
    _AMENITY_MAP = {
        "интернет":            "Internet",
        "телефон":            "Telephone",
        "холодильник":        "Refrigerator",
        "телевизор":          "TV",
        "кондиционер":       "Air Conditioning",
        "кабельное":          "Cable TV",
        "стиральная":         "Washing Machine",
        "кухня":             "Kitchen",
        "балкон":             "Balcony",
    }
 
    @classmethod
    def _extract_amenities(cls, soup: BeautifulSoup) -> str | None:
        """
        Finds the text node that starts with "В квартире есть:" and extracts
        the comma-separated amenity list, translated to English.
        """
        pattern = re.compile(r"В квартире есть:\s*(.+)", re.IGNORECASE)
        for el in soup.find_all(["li", "p", "span", "div"]):
            text = el.get_text(strip=True)
            m = pattern.match(text)
            if m:
                raw_items = [x.strip() for x in m.group(1).split(",")]
                translated = []
                for item in raw_items:
                    low = item.lower()
                    matched = next(
                        (eng for ru, eng in cls._AMENITY_MAP.items() if ru in low),
                        item  # keep original if no mapping found
                    )
                    if matched not in translated:
                        translated.append(matched)
                return ", ".join(translated) if translated else None
        return None
 
    # ------------------------------------------------------------------
    # Nearby  — "Рядом есть: item1, item2, ..."
    # ------------------------------------------------------------------
    _NEARBY_MAP = {
        "больница":         "Hospital",
        "поликлиника":       "Clinic",
        "школа":            "School",
        "детская площадка":  "Playground",
        "детский сад":     "Kindergarten",
        "остановка":         "Bus Stop",
        "остановки":         "Bus Stop",
        "парк":              "Park",
        "зелёная зона":     "Green Area",
        "зеленая зона":     "Green Area",
        "развлекательные":  "Entertainment",
        "ресторан":          "Restaurant",
        "кафе":             "Cafe",
        "стоянка":           "Parking",
        "парковка":          "Parking",
        "супермаркет":        "Supermarket",
        "магазин":           "Shops",
    }
 
    @classmethod
    def _extract_nearby(cls, soup: BeautifulSoup) -> str | None:
        """
        Finds the text node that starts with "Рядом есть:" and extracts
        the comma-separated nearby list, translated to English.
        Deduplicates (e.g. both Больница and поликлиника map to Hospital/Clinic).
        """
        pattern = re.compile(r"Рядом есть:\s*(.+)", re.IGNORECASE)
        for el in soup.find_all(["li", "p", "span", "div"]):
            text = el.get_text(strip=True)
            m = pattern.match(text)
            if m:
                raw_items = [x.strip() for x in m.group(1).split(",")]
                translated = []
                for item in raw_items:
                    low = item.lower()
                    matched = next(
                        (eng for ru, eng in cls._NEARBY_MAP.items() if ru in low),
                        item
                    )
                    if matched not in translated:
                        translated.append(matched)
                return ", ".join(translated) if translated else None
        return None
 
    # ------------------------------------------------------------------
    # Negotiable  — "Договорная" near the price block
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_negotiable(soup: BeautifulSoup) -> int:
        """
        Returns 1 if the listing is marked as negotiable (Договорная), else 0.
        Also checks __NEXT_DATA__ price.negotiable flag if available (already
        parsed upstream, so here we only need the HTML fallback).
        """
        pattern = re.compile(r"договорн", re.IGNORECASE)
        for el in soup.find_all(["span", "p", "div", "strong"]):
            text = el.get_text(strip=True)
            if len(text) < 60 and pattern.search(text):
                return 1
        return 0
 
    # ------------------------------------------------------------------
    # Published date  — "Опубликовано 29 апреля 2026 г." / "Опубликованосегодня в 13:26"
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_published_date(soup: BeautifulSoup) -> str | None:
        """
        Extracts the publication date from the listing and formats it as DD/MM/YYYY.
        """
        pattern = re.compile(r'(?:Опубликовано|Published)\s*(.+)', re.IGNORECASE)
        for el in soup.find_all(["span", "div", "p"]):
            text = el.get_text(strip=True)
            text = re.sub(r'(Опубликовано|Published)', r'\1 ', text, flags=re.IGNORECASE)
            m = pattern.search(text)
            if m:
                raw_date = m.group(1).strip()
                now = datetime.now()
                low = raw_date.lower()
                if 'сегодня' in low or 'today' in low:
                    return now.strftime('%d/%m/%Y')
                elif 'вчера' in low or 'yesterday' in low:
                    return (now - timedelta(days=1)).strftime('%d/%m/%Y')
                else:
                    dm_match = re.search(r'(\d{1,2})\s+([а-яa-z]+)\s+(\d{4})', low)
                    if dm_match:
                        day = int(dm_match.group(1))
                        month_str = dm_match.group(2)
                        year = int(dm_match.group(3))
                        months_ru = {
                            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
                            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
                            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
                            'january': 1, 'february': 2, 'march': 3, 'april': 4,
                            'may': 5, 'june': 6, 'july': 7, 'august': 8,
                            'september': 9, 'october': 10, 'november': 11, 'december': 12
                        }
                        month = months_ru.get(month_str, 1)
                        return f'{day:02d}/{month:02d}/{year}'
                return raw_date
        return None
 
    # ------------------------------------------------------------------
    # Seller type — read from the seller card block
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_seller_type(soup: BeautifulSoup) -> str | None:
        """
        OLX.uz shows the account type in the seller sidebar, not in the
        characteristics list.  The block contains one of:
          • "Пользователь"  → private individual
          • "Бизнес"        → business / agency
 
        We scan every short text node and return on the first match.
        """
        _TYPE_MAP = {
            "пользователь": "private",
            "частное лицо": "private",
            "бизнес":       "business",
            "агент":        "business",
            "агентство":    "business",
        }
        for el in soup.find_all(["span", "p", "div", "strong", "h4", "h3"]):
            text = el.get_text(strip=True)
            # Only look at short, standalone labels (not big concatenated blocks)
            if len(text) > 60:
                continue
            low = text.lower()
            for keyword, mapped in _TYPE_MAP.items():
                if keyword in low:
                    return mapped
        return None
 
    # ------------------------------------------------------------------
    # Characteristics — Russian label → column value
    # ------------------------------------------------------------------
    def _extract_characteristics(self, soup: BeautifulSoup, listing: dict):
        """
        OLX.uz renders characteristics as label : value pairs, either in
        the same text node ("Количество комнат: 2") or as adjacent siblings
        (label element followed by value element).
        """
        for ru_label, field in FIELD_MAP.items():
            if listing.get(field) is not None:
                continue
 
            # Match text node that is exactly the label (with optional colon)
            pattern = re.compile(r"^\s*" + re.escape(ru_label) + r":?\s*$")
            node = soup.find(string=pattern)
 
            if not node:
                # Also try "Label: value" in a single node
                combined = soup.find(
                    string=re.compile(r"^\s*" + re.escape(ru_label) + r":\s*.+")
                )
                if combined:
                    value = combined.strip().split(":", 1)[1].strip()
                    listing[field] = self._clean_value(field, value)
                continue
 
            raw_text = node.strip()
            if ":" in raw_text and len(raw_text) > len(ru_label) + 1:
                value = raw_text.split(":", 1)[1].strip()
            else:
                # Value is in a sibling element
                parent  = node.parent
                sibling = parent.find_next_sibling() if parent else None
                if not sibling and parent and parent.parent:
                    sibling = parent.parent.find_next_sibling()
                if not sibling:
                    continue
                value = sibling.get_text(strip=True)
 
            if value:
                listing[field] = self._clean_value(field, value)
 
    # ------------------------------------------------------------------
    # Location — region + district from breadcrumb
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_location_name(value: str | None) -> str | None:
        if not value:
            return None
 
        cleaned = re.sub(r"\s+", " ", value).strip(" ,")
        cleaned = re.sub(
            r"^(?:Продажа|Аренда(?:\s+долгосрочная)?|Посуточно)\s*-\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not cleaned:
            return None
 
        normalized = cleaned.lower().replace("’", "'").replace("`", "'")
        if normalized in BREADCRUMB_SKIP:
            return None
 
        region_aliases = {
            "toshkent": "Tashkent City",
            "tashkent": "Tashkent City",
            "город ташкент": "Tashkent City",
            "ташкент": "Tashkent City",
            "ташкентская область": "Tashkent Region",
            "toshkent viloyati": "Tashkent Region",
            "andijon": "Andijan Region",
            "андижанская область": "Andijan Region",
            "buxoro": "Bukhara Region",
            "бухарская область": "Bukhara Region",
            "farg'ona": "Fergana Region",
            "fergana": "Fergana Region",
            "ферганская область": "Fergana Region",
            "jizzax": "Jizzakh Region",
            "джизакская область": "Jizzakh Region",
            "xorazm": "Khorezm Region",
            "хорезмская область": "Khorezm Region",
            "namangan": "Namangan Region",
            "наманганская область": "Namangan Region",
            "navoiy": "Navoiy Region",
            "навоийская область": "Navoiy Region",
            "навойская область": "Navoiy Region",
            "навойская область": "Navoiy Region",
            "qashqadaryo": "Kashkadarya Region",
            "кашкадарьинская область": "Kashkadarya Region",
            "samarqand": "Samarkand Region",
            "самаркандская область": "Samarkand Region",
            "sirdaryo": "Sirdaryo Region",
            "сырдарьинская область": "Sirdaryo Region",
            "surxondaryo": "Surxondaryo Region",
            "сурхандарьинская область": "Surxondaryo Region",
            "qoraqalpog'iston": "Republic of Karakalpakstan",
            "каракалпакстан": "Republic of Karakalpakstan",
            "мирзо-улугбекский район": "Mirzo-Ulugbek District",
            "мирабадский район": "Mirabad District",
            "яккасарайский район": "Yakkasaray District",
            "юнусабадский район": "Yunusabad District",
            "шайхантахурский район": "Shaykhantakhur District",
            "чиланзарский район": "Chilanzar District",
            "яшнабадский район": "Yashnabad District",
            "сергелийский район": "Sergeli District",
            "учтепинский район": "Uchtepa District",
            "навои": "Navoiy",
            "бухара": "Bukhara",
            "самарканд": "Samarkand",
        }
        return region_aliases.get(normalized, cleaned)
 
    @classmethod
    def _looks_like_region(cls, value: str | None) -> bool:
        normalized = cls._normalize_location_name(value)
        return bool(normalized and normalized.lower() in UZBEKISTAN_REGIONS)
 
    @classmethod
    def _extract_location(cls, soup: BeautifulSoup, listing: dict):
        """
        Breadcrumb structure on OLX.uz:
          Главная > Недвижимость > Квартиры > [Region] > [District]
 
        We skip category-level crumbs and take the last two meaningful ones.
        """
        for nav in soup.find_all(["nav", "ol", "ul"]):
            crumbs = [
                cls._normalize_location_name(a.get_text(strip=True))
                for a in nav.find_all("a")
            ]
            crumbs = [
                crumb for crumb in crumbs
                if crumb
            ]
 
            if not crumbs:
                continue
 
            region_index = next(
                (i for i, crumb in enumerate(crumbs) if cls._looks_like_region(crumb)),
                None,
            )
            if region_index is not None:
                listing["region"] = crumbs[region_index]
                if region_index + 1 < len(crumbs):
                    # Keep the most specific location after the region:
                    # Region -> City -> District should end up with District.
                    listing["district"] = crumbs[-1]
                return
 
            if len(crumbs) >= 2:
                listing["region"] = crumbs[-2]
                listing["district"] = crumbs[-1]
                return
 
        # Fallback — scan for "район" keyword in short text blocks
        for el in soup.find_all(["p", "span", "div"]):
            text = el.get_text(strip=True)
            if "район" in text.lower() and len(text) < 80:
                listing["district"] = text
                return
 
    # ------------------------------------------------------------------
    # Price
    # ------------------------------------------------------------------
    def _extract_price(self, soup: BeautifulSoup) -> tuple[float | None, str]:
        pattern = re.compile(r"(?:[\$€£]\s*[\d\s.,]+|[\d\s.,]+(?:у\.е\.|сум|UZS|USD|EUR|RUB|руб|\$|€|£))", re.IGNORECASE)
        for el in soup.find_all(["strong", "span", "div", "p"]):
            text = el.get_text(strip=True)
            if pattern.search(text) and len(text) < 40:
                return self._parse_price_text(text)
        return None, "USD"
 
    @staticmethod
    def _parse_price_text(text: str) -> tuple[float | None, str]:
        lower = text.lower()
        if "сум" in lower or "uzs" in lower:
            currency = "UZS"
        elif "rub" in lower or "руб" in lower:
            currency = "RUB"
        elif "eur" in lower or "€" in text:
            currency = "EUR"
        elif "gbp" in lower or "£" in text:
            currency = "GBP"
        else:
            currency = "USD"   # у.е. / $ / default
 
        # Keep only the numeric fragment; this avoids dots from abbreviations
        # such as "у.е." turning into invalid numbers like "70000..".
        numeric_match = re.search(r"[\d\s]+(?:[.,]\d+)?", text)
        if not numeric_match:
            return None, currency
 
        num_str = numeric_match.group(0).replace(" ", "").replace(",", ".")
        try:
            return float(num_str), currency
        except ValueError:
            return None, currency
 
    # ------------------------------------------------------------------
    # Description
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        """
        Multi-strategy description extractor for OLX.uz.
 
        OLX uses randomly-hashed CSS class names so we cannot rely on a class
        containing the word "description".  Instead we try, in order:
          1. data-cy="ad_description" attribute (stable OLX attribute)
          2. itemprop="description" attribute (schema.org markup)
          3. id containing "description"
          4. CSS class containing "description" (legacy / fallback)
          5. Largest <p>-rich block that looks like a listing body
        """
        # 1. Stable OLX data-cy attribute
        el = soup.find(attrs={"data-cy": "ad_description"})
        if el:
            text = el.get_text(separator=" ", strip=True)
            if len(text) > 20:
                return text[:2000]
 
        # 2. Schema.org itemprop
        el = soup.find(attrs={"itemprop": "description"})
        if el:
            text = el.get_text(separator=" ", strip=True)
            if len(text) > 20:
                return text[:2000]
 
        # 3. id containing "description"
        for el in soup.find_all(id=re.compile(r"description", re.I)):
            text = el.get_text(separator=" ", strip=True)
            if len(text) > 20:
                return text[:2000]
 
        # 4. class containing "description"
        for el in soup.find_all(["div", "section", "article"]):
            cls = " ".join(el.get("class", []))
            if "description" in cls.lower():
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 20:
                    return text[:2000]
 
        # 5. Heuristic: find the largest block of coherent paragraph text
        #    (>= 60 chars, not a navigation / price / characteristics block)
        best_text = ""
        for el in soup.find_all(["div", "section", "article", "p"]):
            # Skip tiny or obviously non-description containers
            if el.find(["nav", "ul", "ol", "table"]):
                continue
            text = el.get_text(separator=" ", strip=True)
            if 60 < len(text) < 5000 and len(text) > len(best_text):
                # Reject blocks that are clearly price / characteristics tables
                if not re.search(r"(\d{5,}|USD|UZS|у\.е\.)", text[:50]):
                    best_text = text
        if best_text:
            return best_text[:2000]
 
        return None
 
    # ------------------------------------------------------------------
    # Value cleaning / type coercion
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_value(field: str, raw: str) -> int | float | str | None:
        raw = raw.strip()
        if field in ("rooms", "floor", "total_floors"):
            m = re.search(r"\d+", raw)
            return int(m.group()) if m else None
        if field in ("living_area_m2", "total_area_m2", "kitchen_area_m2"):
            m = re.search(r"[\d.,]+", raw)
            if m:
                try:
                    return float(m.group().replace(",", "."))
                except ValueError:
                    return None
            return None
        if field == "ceiling_height":
            m = re.search(r"[\d.,]+", raw)
            if m:
                try:
                    val = float(m.group().replace(",", "."))
                    if val >= 100:
                        val = val / 100.0
                    elif val >= 10:
                        val = val / 10.0
                    if 2.0 <= val <= 6.0:
                        return round(val, 2)
                except ValueError:
                    pass
            return None
        if field == "furnished":
            return 1 if raw.lower() in ("да", "yes", "есть", "мебелирована") else 0
        if field == "commission":
            return 0 if raw.lower() in ("нет", "no", "без комиссии", "0") else 1
        if field == "build_year":
            years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", raw)]
            return max(years) if years else None
        translations = VALUE_TRANSLATIONS.get(field, {})
        return translations.get(raw.lower(), raw)
 
    # ------------------------------------------------------------------
    # __NEXT_DATA__ JSON parser
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_next_data(data: dict, listing: dict):
        try:
            ad = data["props"]["pageProps"]["ad"]
        except (KeyError, TypeError):
            return
 
        listing["listing_id"] = str(ad.get("id", listing["listing_id"]))
 
        price_block = ad.get("price", {})
        if price_block:
            listing["price"]    = price_block.get("value")
            listing["currency"] = price_block.get("currency", "USD")
 
        # Store None explicitly so the HTML fallback in _parse_detail fires
        # when __NEXT_DATA__ has no description text.
        raw_desc = (ad.get("description") or "").strip()
        listing["description"] = raw_desc[:1000] if raw_desc else None
 
        for param in ad.get("params", []):
            key   = param.get("key", "")
            label = (param.get("value") or {}).get("label", "")
            if key in FIELD_MAP:
                field = FIELD_MAP[key]
                listing[field] = OLXScraper._clean_value(field, label)
 
        location      = ad.get("location", {})
        listing["region"] = OLXScraper._normalize_location_name(
            (location.get("region") or {}).get("name")
        )
        listing["district"] = OLXScraper._normalize_location_name(
            (location.get("district") or {}).get("name")
            or (location.get("city") or {}).get("name")
        )
 
    # ------------------------------------------------------------------
    # Persistence — append-only CSV
    # ------------------------------------------------------------------
    def _save(self, rows: list[dict]):
        if not rows:
            return

        for row in rows:
            row.setdefault("source", "olx")
        
        # Atomic append: read existing if present, append new rows, write to temp, then rename
        if self.csv_path.exists():
            try:
                existing_df = pd.read_csv(self.csv_path, dtype=str)
                new_df = pd.DataFrame(rows, columns=COLUMNS)
                df = pd.concat([existing_df, new_df], ignore_index=True)
            except Exception as e:
                log.warning(f"Could not read existing CSV for atomic append, writing new: {e}")
                df = pd.DataFrame(rows, columns=COLUMNS)
        else:
            df = pd.DataFrame(rows, columns=COLUMNS)
 
        tmp_path = self.csv_path.with_suffix(".csv.tmp")
        df.to_csv(tmp_path, index=False, encoding="utf-8-sig")
        os.replace(tmp_path, self.csv_path)
        log.info(f"Saved {len(rows)} new rows atomically → {self.csv_path}")
 
    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self, max_pages: int = MAX_PAGES, max_listings: int | None = None):
        global shutdown_requested
        limit_msg = f", capped at {max_listings} listing(s)" if max_listings else ""
        log.info(f"===== Scrape started — up to {max_pages} page(s){limit_msg} =====")
        total_new = 0
 
        for page in range(1, max_pages + 1):
            if shutdown_requested:
                break
 
            try:
                urls = self._get_listing_urls(page)
            except FetchBlockedError:
                log.error(
                    "Stopping current run because OLX blocked the listing page. "
                    "Existing CSV data was not changed."
                )
                break
            if not urls:
                log.info(f"No listings on page {page} — stopping.")
                break
 
            self._delay()
            batch: list[dict] = []
 
            for url in urls:
                # Stop early if per-run listing cap is reached
                if max_listings is not None and total_new + len(batch) >= max_listings:
                    log.info(f"Reached --listings cap of {max_listings}. Stopping.")
                    self._save(batch)
                    total_new += len(batch)
                    log.info(f"===== Scrape finished — {total_new} new listings =====")
                    return total_new
                
                if shutdown_requested:
                    log.info("Shutdown requested. Finishing current page block...")
                    break
 
                lid = self._extract_id(url)
                if lid in self.seen_ids:
                    log.info(f"  Duplicate — skipping {lid}")
                    continue
 
                detail = self._parse_detail(url)
                if detail:
                    batch.append(detail)
                    self.seen_ids.add(lid)                          # URL slug (e.g. "4mJXy")
                    self.seen_ids.add(str(detail["listing_id"]))    # numeric ID from __NEXT_DATA__
                    log.info(f"  Scraped {lid}")
 
                self._delay()
 
            self._save(batch)
            total_new += len(batch)
            log.info(f"Page {page} done — new: {len(batch)}, total new: {total_new}")
            self._delay()
 
        log.info(f"===== Scrape finished — {total_new} new listings =====")
        return total_new


    def run_scraper(max_pages=MAX_PAGES, max_listings=None):
        scraper = OLXScraper()
        return scraper.run(
            max_pages=max_pages,
            max_listings=max_listings,
        )
 
 
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OLX.uz apartment scraper")
    parser.add_argument(
        "--pages", type=int, default=MAX_PAGES,
        help=f"Number of listing pages to scrape (default: {MAX_PAGES}). Use 1 for a test run.",
    )
    parser.add_argument(
        "--listings", type=int, default=None,
        help="Hard cap on total new listings scraped per run (e.g. --listings 5 for a quick check).",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Deprecated no-op. The scraper always runs one cycle and exits.",
    )
    args = parser.parse_args()

    def handle_shutdown(signum, frame):
        global shutdown_requested
        log.info(f"Received signal {signum}. Initiating graceful shutdown...")
        shutdown_requested = True
 
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    log.info(f"Starting scrape run. (Configured pages: {args.pages})")
    scraper = OLXScraper()
    try:
        new_listings_count = scraper.run(max_pages=args.pages, max_listings=args.listings)
    except Exception as e:
        log.error(f"Run failed with error: {e}", exc_info=True)
        sys.exit(1)

    log.info(f"Run complete. New listings scraped: {new_listings_count}")
    log.info("Scraper exited cleanly.")
