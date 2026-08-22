BASE_URL = "https://www.olx.uz/nedvizhimost/kvartiry/"
MAX_PAGES = 25           # set to 25 when ready for full scrape
DELAY_MIN = 1.5         # seconds — minimum human-like delay
DELAY_MAX = 4.0         # seconds — maximum human-like delay
MAX_RETRIES = 3         # attempts before giving up on a URL
BACKOFF_BASE = 2        # exponential backoff base in seconds

OUTPUT_DIR = "data/raw"
LOG_DIR    = "logs"
CSV_FILENAME = "olx_apartments.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,uz;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Russian page label → CSV column name
# Labels taken directly from real OLX.uz listings
FIELD_MAP = {
    "Тип жилья":              "housing_type",    # Новостройки / Вторичное
    "Тип объявителя":         "seller_type",     # Частное лицо / Бизнес
    "Тип продавца":           "seller_type",     # alternate label
    "Количество комнат":      "rooms",
    "Жилая площадь":          "living_area_m2",
    "Общая площадь":          "total_area_m2",
    "Площадь кухни":          "kitchen_area_m2",
    "Этаж":                   "floor",
    "Этажность дома":         "total_floors",    # confirmed label from OLX.uz
    "Тип строения":           "building_type",   # Панельный / Кирпичный / Монолитный
    "Планировка":             "layout",          # Раздельная / Смежная
    "Год постройки/сдачи":    "build_year",
    "Год постройки":           "build_year",   # alternate label without /сдачи
    "Year built":              "build_year",   # English variant seen on some listings
    "Год сдачи":               "build_year",   # another alternate
    "Высота потолков":        "ceiling_height",
    "Ceiling height":          "ceiling_height",
    "Санузел":                "bathroom",        # Раздельный / Совмещенный
    "Меблирована":            "furnished",       # Да / Нет → 1 / 0
    "Ремонт":                 "renovation",      # Евроремонт / Авторский проект / …
    "Комиссионные":           "commission",      # Да / Нет → 1 / 0
}

# Breadcrumb words to skip when extracting region / district
BREADCRUMB_SKIP = {
    "главная", "недвижимость", "квартиры", "квартира",
    "дома", "продажа", "аренда", "uzbekistan", "olx",
    "o'z", "oz", "o‘z", "o`z", "узбекистан",
}

# Valid first-level regions of Uzbekistan (+ Karakalpakstan + Tashkent city)
UZBEKISTAN_REGIONS = {
    "tashkent region",
    "tashkent city",
    "andijan region",
    "bukhara region",
    "fergana region",
    "jizzakh region",
    "khorezm region",
    "namangan region",
    "navoiy region",
    "kashkadarya region",
    "samarkand region",
    "sirdaryo region",
    "surxondaryo region",
    "republic of karakalpakstan",
}

# Categorical values normalized to English for cleaner downstream analysis
VALUE_TRANSLATIONS = {
    "housing_type": {
        "новостройки": "new building",
        "вторичный рынок": "resale",
        "вторичное": "resale",
    },
    "seller_type": {
        "частное лицо": "private",
        "бизнес": "business",
    },
    "building_type": {
        "кирпичный": "brick",
        "панельный": "panel",
        "монолитный": "monolith",
        "блочный": "block",
    },
    "layout": {
        "раздельная": "separate",
        "смежная": "adjacent",
        "свободная": "free layout",
        "студия": "studio",
    },
    "bathroom": {
        "раздельный": "separate",
        "раздельная": "separate",
        "совмещенный": "combined",
        "совмещённый": "combined",
        "2 санузла и более": "2+ bathrooms",
    },
    "renovation": {
        "евроремонт": "euro renovation",
        "авторский проект": "designer renovation",
        "средний": "average condition",
        "требует ремонта": "needs renovation",
        "черновая отделка": "shell and core",
        "предчистовая отделка": "pre-finished",
    },
}

# Output columns — final schema
COLUMNS = [
    "listing_id",
    "source",
    "seller_type",
    "housing_type",
    "region",           # which of the 13 Uzbekistan regions
    "district",         # sub-region / rayon
    "rooms",
    "living_area_m2",
    "kitchen_area_m2",
    "total_area_m2",
    "floor",
    "total_floors",
    "building_type",
    "layout",
    "build_year",
    "ceiling_height",
    "bathroom",
    "furnished",
    "renovation",
    "commission",
    "amenities",        # comma-separated list: Internet, Balcony, AC, etc.
    "nearby",           # comma-separated list: School, Park, Hospital, etc.
    "negotiable",       # 1 if price is negotiable, 0 otherwise
    "price",
    "currency",
    "published_date",
    "description",
    "date_scraped",
    "url",
]
