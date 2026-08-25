import logging
import pandas as pd
import numpy as np
import re


log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# =====================================================================================
#               Dropping duplicate rows
# =====================================================================================
def drop_duplicate(df_cleaned):
    log.info("Removing duplicates")
    before = len(df_cleaned)

    df_cleaned = df_cleaned.drop_duplicates(subset=['listing_id'])

    after = len(df_cleaned)
    log.info(f"""
        Dataset size: {before}
        Duplicates: {before - after}
    """)
    return df_cleaned



# =====================================================================================
#               Cleaning Price column
# =====================================================================================
def price_cleaner(df_cleaned):
    log.info("Cleaning price and converting currency")

    before = len(df_cleaned)
    df_cleaned = df_cleaned.dropna(subset=['price']).copy()
    after = len(df_cleaned)

    exchange_rate = 12700
    df_cleaned['price_usd'] = df_cleaned['price']
    df_cleaned.loc[df_cleaned['currency'] == "UZS", 'price_usd'] = (
        df_cleaned.loc[df_cleaned['currency'] == "UZS", 'price_usd'] / exchange_rate
    ).round(1)

    log.info(f"Dropped {before - after} rows with missing price")
    return df_cleaned

# =====================================================================================
#               New column listing_type
# =====================================================================================

RENT_MAX_PRICE = 2000
SALE_MIN_PRICE = 10000

RENT_WORDS = [
    "сдаётся", "сдается", "сдам", "сдаю", "аренда", "аренду",
    "посуточно", "помесячно",
    "ижарага", "ижара", "ijaraga", "ijara", "ijaraga beriladi",
    "topshiriladi", "арендага",
    "for rent", "to rent", "lease", "tenant"
]

SALE_WORDS = [
    "продаётся", "продается", "продам", "продаю", "продажа",
    "сотилади", "sotiladi", "sotaman", "sotuv", "sotish",
    "ипотека", "рассрочка", "ipoteka",
    "for sale", "sell", "selling", "mortgage"
]

def listing_type_scores(df_cleaned):
    desc = df_cleaned["description"].fillna("").str.lower()
    url = df_cleaned["url"].fillna("").str.lower()

    rent_score = (
        sum(desc.str.contains(re.escape(w), regex=True, na=False).astype(int) for w in RENT_WORDS) * 3
        + sum(url.str.contains(re.escape(w), regex=True, na=False).astype(int) for w in RENT_WORDS)
    )
    sale_score = (
        sum(desc.str.contains(re.escape(w), regex=True, na=False).astype(int) for w in SALE_WORDS) * 3
        + sum(url.str.contains(re.escape(w), regex=True, na=False).astype(int) for w in SALE_WORDS)
    )
    return rent_score, sale_score


def classify_listings(df_cleaned):
    rent_score, sale_score = listing_type_scores(df_cleaned)
    price = df_cleaned["price_usd"]

    conditions = [
        (sale_score > rent_score) & (price >= RENT_MAX_PRICE),
        (rent_score > sale_score) & (price < SALE_MIN_PRICE),
        (sale_score > rent_score) & (price < RENT_MAX_PRICE),
        (rent_score > sale_score) & (price >= SALE_MIN_PRICE),
        price >= SALE_MIN_PRICE,
    ]
    choices = ["Sale", "Rent", "Rent", "Sale", "Sale"]
    return np.select(conditions, choices, default="Rent")


def classify_listing_type(df_cleaned):
    df_cleaned["listing_type"] = classify_listings(df_cleaned)

    rent_score, sale_score = listing_type_scores(df_cleaned)
    no_signal = ((rent_score == 0) & (sale_score == 0)).sum()
    log.info(f"Classified listings. {no_signal} had no rent/sale keyword match (price-only fallback)")

    log.info(df_cleaned['listing_type'].value_counts().to_dict())
    return df_cleaned

# =====================================================================================
#               housing_type Cleaner
# =====================================================================================
def housing_type_cleaner(df_cleaned):
    log.info("Cleaning housing_type column")
    valid_housing_type = {
    'new building': 'new building',
    'resale': 'resale',
    'Новостройка': 'new building',
    'новостройка': 'new building',
    'Новостройка.': 'new building',
    'Вторичка,кирпичный дом.': 'resale'
    }

    def validate_housing_type(text):
        if pd.isna(text):
            return np.nan

        if text in valid_housing_type:
            return valid_housing_type[text]
        else:
            return np.nan


    df_cleaned['housing_type'] = df_cleaned['housing_type'].apply(validate_housing_type)
    return df_cleaned

# =====================================================================================
#                   Validating&Cleaning rooms column
# =====================================================================================
def validate_rooms(df_cleaned):
    before = len(df_cleaned)
    nan_count = df_cleaned['rooms'].isna().sum()
    over_limit_count = (df_cleaned['rooms'] >= 7).sum()

    df_cleaned = df_cleaned[df_cleaned['rooms'] < 7].copy()

    log.info(f"Rooms validation: {before} -> {len(df_cleaned)} "
              f"(dropped {nan_count} NaN, {over_limit_count} with 7+ rooms)")
    return df_cleaned


# =====================================================================================
#                   Create price_per_sqr column
# =====================================================================================

def create_price_per_sqr(df_cleaned):
    df_cleaned["price_per_sqr"] = np.nan
    before = len(df_cleaned)

    sale_mask = (
        (df_cleaned["listing_type"] == "Sale") &
        (df_cleaned["total_area_m2"].notna()) &
        (df_cleaned["total_area_m2"] > 0)
    )

    df_cleaned.loc[sale_mask, "price_per_sqr"] = round(
        (df_cleaned.loc[sale_mask, "price_usd"] /
        df_cleaned.loc[sale_mask, "total_area_m2"]
    ), 2)

    MAX_PRICE_PER_SQR = 50000

    df_cleaned = df_cleaned[
        ~(
            (df_cleaned["listing_type"] == "Sale") &
            (df_cleaned["price_per_sqr"] > MAX_PRICE_PER_SQR)
        )
    ].copy()
    outlier_mask = (
        (df_cleaned["listing_type"] == "Sale") &
        (df_cleaned["price_per_sqr"] > MAX_PRICE_PER_SQR)
    )
    outlier_count = outlier_mask.sum()

    df_cleaned = df_cleaned[~outlier_mask].copy()

    log.info(f"price_per_sqr: dropped {outlier_count} Sale listings above ${MAX_PRICE_PER_SQR}/m2 "
             f"({before} -> {len(df_cleaned)})")
    return df_cleaned


# =====================================================================================
#                   Clean district column
# =====================================================================================

def clean_district(df_cleaned):
    log.info("Cleaning district column")
    district_overrides = {
        # Tashkent city districts
        "mirzo-ulugbek district": "Mirzo Ulugbek",
        "yunusabad district": "Yunusabad",
        "yakkasaray district": "Yakkasaray",
        "mirabad district": "Mirabad",
        "yashnabad district": "Yashnabad",
        "chilanzar district": "Chilanzar",
        "shaykhantakhur district": "Shaykhantakhur",
        "sergeli district": "Sergeli",
        "uchtepa district": "Uchtepa",

        "алмазарский район": "Almazar",
        "бектемирский район": "Bektemir",
        "мирабад": "Mirabad",
        "учтепа": "Uchtepa",

        # Existing Latin names
        "samarkand": "Samarkand",
        "bukhara": "Bukhara",
        "navoiy": "Navoiy",
    }

    cyrillic_to_latin = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
        "е": "e", "ё": "yo", "ж": "zh", "з": "z", "и": "i",
        "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
        "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
        "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
        "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",

        # Uzbek Cyrillic
        "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
    }

    def transliterate(text):
        return "".join(cyrillic_to_latin.get(ch, ch) for ch in text)

    def normalize_place_name(value):
        if pd.isna(value):
            return np.nan

        value = str(value).strip()

        if value == "" or "css" in value.lower():
            return np.nan

        key = value.lower().strip()

        if key in district_overrides:
            return district_overrides[key]

        # Remove generic words
        key = key.replace(" district", "")
        key = key.replace(" район", "")
        key = key.replace("ский", "")
        key = key.replace("ская", "")
        key = key.replace("ское", "")

        # Transliterate Cyrillic to Latin
        key = transliterate(key)

        # Clean spacing
        key = re.sub(r"\s+", " ", key).strip()

        # Title case, keeping hyphenated names readable
        return key.title()

    before_nan = df_cleaned["district"].isna().sum()
    df_cleaned["district"] = df_cleaned["district"].apply(normalize_place_name)
    after_nan = df_cleaned["district"].isna().sum()

    log.info(f"district: {after_nan - before_nan} additional values became NaN during cleaning")
    log.info(f"district unique values after cleaning: {sorted(df_cleaned['district'].dropna().unique().tolist())}")

    return df_cleaned


# =====================================================================================
#                   Clean housing_type column
# =====================================================================================

def clean_total_area_m2(df_cleaned):
    log.info("Cleaning total_area_m2 column")
    before = len(df_cleaned)
    df_cleaned=df_cleaned.dropna(subset=['total_area_m2'])

    Q1 = df_cleaned['total_area_m2'].quantile(0.25)
    Q3 = df_cleaned['total_area_m2'].quantile(0.75)

    IQR = Q3 - Q1

    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    lower = max(lower, 10)
    upper = 400

    df_cleaned = df_cleaned[
        df_cleaned['total_area_m2'].between(lower, upper)
    ]
    log.info(f"total_area_m2 validation: {before} -> {len(df_cleaned)} ")
    return df_cleaned

# =====================================================================================
#                   Clean floor&total_floors column
# =====================================================================================

def clean_floor(df_cleaned):
    log.info("Cleaning total_area_m2 column")
    before = len(df_cleaned)

    df_cleaned = df_cleaned[df_cleaned['total_floors'] < 100]

    log.info(f"total_area_m2 validation: {before} -> {len(df_cleaned)} ")
    return df_cleaned


# =====================================================================================
#                   Clean building_type column
# =====================================================================================

def clean_building_type(df_cleaned):
    log.info("Cleaning total_area_m2 column")
    def clean_building(value):
        if pd.isna(value):
            return np.nan

        value = str(value).lower().strip()

        if "css" in value:
            return np.nan

        if "кирп" in value or "brick" in value:
            return "brick"

        if "панел" in value or "panel" in value:
            return "panel"

        if "монолит" in value or "monolith" in value:
            return "monolith"

        if "блок" in value or "block" in value or "газоблок" in value:
            return "block"

        if "дерев" in value:
            return "wood"

        return np.nan

    df_cleaned["building_type"] = df_cleaned["building_type"].apply(clean_building_type)
    return df_cleaned


