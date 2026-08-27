# Gold Layer Data Dictionary

The gold layer is the final analytics layer. It uses a simple star schema for apartment listing analysis.

## gold.dim_property

Stores property-related details. One row represents one unique property attribute combination.

| Column | Type | Description |
| --- | --- | --- |
| property_dim_id | SERIAL | Primary key for the property dimension. |
| housing_type | TEXT | Type of housing or apartment category. |
| building_type | TEXT | Type of building. |
| layout | TEXT | Apartment layout. |
| bathroom | TEXT | Bathroom type or condition. |
| furnished | BOOLEAN | Shows if the apartment is furnished. |
| renovation | TEXT | Renovation status or type. |

## gold.dim_location

Stores location details. One row represents one unique region and district combination.

| Column | Type | Description |
| --- | --- | --- |
| location_dim_id | SERIAL | Primary key for the location dimension. |
| region | TEXT | Region where the apartment is located. |
| district | TEXT | District where the apartment is located. |

## gold.fact_listing

Stores the main apartment listing facts. One row represents one apartment listing.

| Column | Type | Description |
| --- | --- | --- |
| listing_id | TEXT | Primary key for the apartment listing. |
| property_dim_id | INTEGER | Foreign key to `gold.dim_property`. |
| location_dim_id | INTEGER | Foreign key to `gold.dim_location`. |
| rooms | INTEGER | Number of rooms. |
| total_area_m2 | NUMERIC(10,2) | Total apartment area in square meters. |
| floor | INTEGER | Floor where the apartment is located. |
| total_floors | INTEGER | Total number of floors in the building. |
| build_year | INTEGER | Year the building was built. |
| age | INTEGER | Age of the building. |
| ceiling_height | NUMERIC(3,2) | Ceiling height in meters. |
| seller_type | TEXT | Type of seller, such as owner or agency. |
| price_usd | NUMERIC(12,2) | Listing price in USD. |
| price_per_sqr | NUMERIC(10,2) | Price per square meter. |
| listing_type | TEXT | Type of listing. |
| negotiable | BOOLEAN | Shows if the price is negotiable. |
| commission | BOOLEAN | Shows if commission is required. |
| date_scraped | DATE | Date when the listing data was collected. |
| description | TEXT | Listing description text. |

## gold.dim_listing_attributes

Stores amenities and nearby places for each listing. One row represents one apartment listing.

| Column | Type | Description |
| --- | --- | --- |
| listing_id | TEXT | Primary key and foreign key to `gold.fact_listing`. |
| amenity_air_conditioning | BOOLEAN | Shows if air conditioning is mentioned. |
| amenity_balcony | BOOLEAN | Shows if a balcony is mentioned. |
| amenity_cable_tv | BOOLEAN | Shows if cable TV is mentioned. |
| amenity_internet | BOOLEAN | Shows if internet is mentioned. |
| amenity_kitchen | BOOLEAN | Shows if a kitchen is mentioned. |
| amenity_refrigerator | BOOLEAN | Shows if a refrigerator is mentioned. |
| amenity_tv | BOOLEAN | Shows if a TV is mentioned. |
| amenity_telephone | BOOLEAN | Shows if a telephone is mentioned. |
| amenity_washing_machine | BOOLEAN | Shows if a washing machine is mentioned. |
| nearby_bus_stop | BOOLEAN | Shows if a bus stop is nearby. |
| nearby_cafe | BOOLEAN | Shows if a cafe is nearby. |
| nearby_clinic | BOOLEAN | Shows if a clinic is nearby. |
| nearby_entertainment | BOOLEAN | Shows if entertainment places are nearby. |
| nearby_green_area | BOOLEAN | Shows if a green area is nearby. |
| nearby_hospital | BOOLEAN | Shows if a hospital is nearby. |
| nearby_kindergarten | BOOLEAN | Shows if a kindergarten is nearby. |
| nearby_park | BOOLEAN | Shows if a park is nearby. |
| nearby_parking | BOOLEAN | Shows if parking is nearby. |
| nearby_playground | BOOLEAN | Shows if a playground is nearby. |
| near_metro_mentioned | BOOLEAN | Shows if metro proximity is mentioned. |
| nearby_restaurant | BOOLEAN | Shows if a restaurant is nearby. |
| nearby_school | BOOLEAN | Shows if a school is nearby. |
| nearby_shops | BOOLEAN | Shows if shops are nearby. |
| nearby_supermarket | BOOLEAN | Shows if a supermarket is nearby. |
