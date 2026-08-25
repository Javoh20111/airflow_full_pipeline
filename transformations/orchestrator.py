#---------------------------------------------------------------------------------
# ETL turdaki pipelini dasturlashga harakat qilaman
#---------------------------------------------------------------------------------

import pandas as pd
from transformation import drop_columns, drop_duplicate, price_cleaner, housing_type_cleaner, validate_rooms

def extract():
    df = pd.read_csv('data/Praperad/olx_apartments.csv')
    return df

transformations = [
    drop_columns, 
    drop_duplicate,
    price_cleaner, 
    housing_type_cleaner, 
    validate_rooms
]

def transfrom(df):
    for fn in transformations:
        df = fn(df)
    return df



def main():
    df = extract()
    
    transfrom(df)

if __name__ == "__main__":
    main()