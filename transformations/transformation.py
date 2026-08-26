import logging
import pandas as pd
import numpy as np
from datetime import datetime
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
    start_time = datetime.now()
    before = len(df_cleaned)

    df_cleaned = df_cleaned.drop_duplicates(subset=['listing_id'])

    after = len(df_cleaned)
    log.info(f"""
        Dataset size: {before}
        Duplicates: {before - after}
    """)
    end_time = datetime.now()
    log.info(f"Time spent: {before - after}")
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
    df_cleaned = df_cleaned[df_cleaned['price_usd'] > 0].copy()

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
#                   Clean total_area_m2 column
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
    log.info("Cleaning floor&total_floor column")
    before = len(df_cleaned)

    df_cleaned = df_cleaned[df_cleaned['total_floors'] < 100]

    log.info(f"floor&total_floor validation: {before} -> {len(df_cleaned)} ")
    return df_cleaned


# =====================================================================================
#                   Clean building_type column
# =====================================================================================

def clean_building_type(df_cleaned):
    log.info("Cleaning building_type column")
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

    df_cleaned["building_type"] = df_cleaned["building_type"].apply(clean_building)

    return df_cleaned


# =====================================================================================
#                   Clean clean_layout column
# =====================================================================================
def clean_layout(df_cleaned):
    log.info("Cleaning clean_layout column")
    def clean_layout(value):
        if pd.isna(value):
            return np.nan

        value = str(value).lower().strip()

        if value in ["-", ""]:
            return np.nan

        if "css" in value:
            return np.nan

        if "studio" in value or "студ" in value:
            return "studio"

        if "free layout" in value or "свобод" in value:
            return "free_layout"

        if "пентхаус" in value or "penthouse" in value:
            return "penthouse"

        if "многоуров" in value:
            return "multi_level"

        if "малосем" in value:
            return "small_family"

        if (
            "смежно" in value
            or "см-раз" in value
            or "см раз" in value
            or "сможно" in value
        ):
            return "adjacent_separate"

        if "смеж" in value:
            return "adjacent"

        if (
            "раздел" in value
            or "раздель" in value
            or "алоҳида" in value
            or "alohida" in value
            or value == "separate"
        ):
            return "separate"

        if "adjacent" in value:
            return "adjacent"

        return np.nan

    df_cleaned["layout"] = df_cleaned["layout"].apply(clean_layout)
    return df_cleaned

# =====================================================================================
#                   Clean built_year and create age column
# =====================================================================================

def clean_built_year(df_cleaned):
    log.info("Cleaning built_year column")
    current_year = datetime.now().year

    df_cleaned["build_year"] = pd.to_numeric(df_cleaned["build_year"], errors="coerce")

    df_cleaned["age"] = current_year - df_cleaned['build_year']

    df_cleaned.loc[
        (df_cleaned["build_year"] < 1900) |
        (df_cleaned["build_year"] > current_year),
        "age"
    ] = np.nan

    return df_cleaned


# =====================================================================================
#                   Clean bathroom column
# =====================================================================================

def clean_bathroom_column(df_cleaned):
    log.info("Cleaning bathroom_column column")
    def clean_bathroom(value):
        if pd.isna(value):
            return np.nan

        value = str(value).lower().strip().replace(".", "")

        if value in ["", "-", "css"]:
            return np.nan

        if "css" in value:
            return np.nan

        if (
            value in ["2", "3", "4", "2 та"]
            or "2+" in value
            or "2 сан" in value
            or "2 та" in value
            or "3 сан" in value
            or "4 сан" in value
        ):
            return "2+ bathrooms"

        if (
            "separate" in value
            or "раздель" in value
            or "раздел" in value
            or "алоҳида" in value
            or "alohida" in value
        ):
            return "separate"

        if (
            "combined" in value
            or "совмещ" in value
            or "совмеш" in value
            or "совмещение" in value
        ):
            return "combined"

        return np.nan


    df_cleaned["bathroom"] = df_cleaned["bathroom"].apply(clean_bathroom)
    return df_cleaned



# =====================================================================================
#                   Clean renovation column
# =====================================================================================
def clean_renovation_column(df_cleaned):
    log.info("Cleaning renovation column")
    def clean_renovation(value):
        if pd.isna(value):
            return np.nan

        value = str(value).lower().strip()

        if value in ["", "-"]:
            return np.nan

        if "css" in value:
            return np.nan
        
        if value in ["йок", "йўқ", "yo'q", "yoq", "yuq", "yo‘q", "нет", "none", "no"]:
            return "needs_renovation"

        # No / needs renovation
        if (
            "без ремонта" in value
            or "требуется ремонт" in value
            or "needs renovation" in value
            or "ремонт керак" in value
        ):
            return "needs_renovation"

        # Shell/core / unfinished
        if (
            "shell" in value
            or "core" in value
            or "коробка" in value
            or "чернов" in value
        ):
            return "shell_and_core"

        # Pre-finished / white box
        if (
            "pre-finished" in value
            or "white box" in value
            or "предчист" in value
        ):
            return "pre_finished"

        # Designer / author renovation
        if (
            "designer" in value
            or "дизайнер" in value
            or "авторск" in value
            or "haytec" in value
        ):
            return "designer_renovation"

        # Euro / luxury / modern renovation
        if (
            "euro" in value
            or "евро" in value
            or "люкс" in value
            or "lux" in value
            or "современ" in value
            or "комфорт" in value
        ):
            return "euro_renovation"

        # Average / good condition
        if (
            "average" in value
            or "сред" in value
            or "хорош" in value
            or "яхши" in value
            or "чистый" in value
            or "космет" in value
            or "как на фото" in value
            or "с ремонтом" in value
            or value == "есть"
        ):
            return "average_condition"

        return np.nan
    df_cleaned["renovation"] = df_cleaned["renovation"].apply(clean_renovation)
    log.info(f"Sample renovation: {df_cleaned.groupby('renovation')['listing_id'].count()}")
    return df_cleaned


# =====================================================================================
#                   Clean amenities column
# =====================================================================================
def clean_amenities_and_nearby_column(df_cleaned):
    log.info("Cleaning amenities and nearby column")
    VALID_NEARBY = {
        "Hospital", "Clinic", "Playground", "Kindergarten", "Bus Stop",
        "Park", "Green Area", "Entertainment", "Restaurant", "Cafe",
        "Parking", "Supermarket", "Shops", "School", "Metro",
    }

    NEARBY_ALIASES = {
        "метро": "Metro",
        "metro": "Metro",
    }

    def clean_multi_value_items(value, valid_items=None):
        if pd.isna(value):
            return ""

        items = [item.strip() for item in str(value).split(",")]
        items = [NEARBY_ALIASES.get(item.lower(), item) for item in items]

        if valid_items is not None:
            items = [item for item in items if item in valid_items]

        return ", ".join(items)


    def create_boolean_columns(df, column_name, prefix, valid_items=None):
        old_dummy_cols = [col for col in df.columns if col.startswith(f"{prefix}_")]
        df = df.drop(columns=old_dummy_cols, errors="ignore")

        cleaned_values = df[column_name].apply(
            lambda value: clean_multi_value_items(value, valid_items)
        )

        dummies = cleaned_values.str.get_dummies(sep=", ")

        dummies.columns = [
            f"{prefix}_{col.lower().strip().replace(' ', '_')}"
            for col in dummies.columns
        ]

        return pd.concat([df, dummies], axis=1)
    df_cleaned = create_boolean_columns(df_cleaned, "amenities", "amenity")
    df_cleaned = create_boolean_columns(df_cleaned, "nearby", "nearby", VALID_NEARBY)
    log.info(f"Final remaining rows count: {len(df_cleaned)}")
    return df_cleaned


# =====================================================================================
#                   Add near_metro_mentioned column
# =====================================================================================
def add_near_metro_mentioned(df_cleaned):
    log.info("Added new column near_metro_mentioned")
    metro_pattern = r"metro|метро"

    df_cleaned["near_metro_mentioned"] = (
        df_cleaned["description"].fillna("").str.contains(metro_pattern, case = False, regex = True) 
        |
        df_cleaned["url"].fillna("").str.contains(metro_pattern, case = False, regex = True)
    ).astype(int).astype(bool)
    return df_cleaned




# =====================================================================================
#                   Clean amenities column
# =====================================================================================
def remove_unnecesary_columns_and_fix_data_types(df_cleaned):
    log.info("Removing unnecessary columns and fixing data types")
    keep_columns = [
        "listing_id", "price_usd", "price_per_sqr", "listing_type",
        "commission", "negotiable", "published_date", "date_scraped", "url",
        "description", "housing_type", "rooms", "total_area_m2", "floor",
        "total_floors", "building_type", "layout", "build_year", "age",
        "ceiling_height", "bathroom", "furnished", "renovation",
        "seller_type", "region", "district", "amenity_air_conditioning", "amenity_balcony", "amenity_cable_tv","amenity_internet", "amenity_kitchen","amenity_refrigerator","amenity_tv",
        "amenity_telephone", "amenity_washing_machine","nearby_bus_stop", "nearby_cafe", "nearby_clinic","nearby_entertainment", "nearby_green_area", "nearby_hospital", "nearby_kindergarten", "nearby_park", "nearby_parking", "nearby_playground", "nearby_restaurant", "nearby_school", "nearby_shops", "nearby_supermarket", "near_metro_mentioned",
    ]

    df_cleaned = df_cleaned[keep_columns].copy()

    df_cleaned["commission"] = df_cleaned["commission"].fillna(0).astype(int).astype(bool)
    df_cleaned["negotiable"] = df_cleaned["negotiable"].fillna(0).astype(int).astype(bool)
    df_cleaned["furnished"] = df_cleaned["furnished"].fillna(0).astype(int).astype(bool)
    df_cleaned["floor"] = df_cleaned["floor"].astype("Int64")
    df_cleaned["total_floors"] = df_cleaned["total_floors"].astype("Int64")
    df_cleaned["rooms"] = df_cleaned["rooms"].astype("Int64")
    df_cleaned["age"] = df_cleaned["age"].astype("Int64")
    df_cleaned["build_year"] = df_cleaned["build_year"].astype("Int64")
    df_cleaned["published_date"] = pd.to_datetime(
    df_cleaned["published_date"], format="%d/%m/%Y", errors="coerce").dt.date
    return df_cleaned
