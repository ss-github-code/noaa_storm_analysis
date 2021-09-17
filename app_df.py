import re
import pandas as pd
import numpy as np
import json
from urllib.request import urlopen
import psycopg2

from app import cache, cache_found
from notebooks.amazon_cred import ENDPOINT, PORT, USER, PASSWORD, DATABASE
from notebooks.data_constants import NOAA_CSVFILES_URL, GEOJSON_COUNTIES_URL, BLS_CPI_CSV
from notebooks.data_constants import STORM_CATEGORIES

# Redis Constants
CACHE_DATAFRAME = 0
CACHE_FIGURE = 1

# A decorator takes in a function and returns a new function from it.
# So, if you want a conditional decorator, all you need is to return
# the initial function when you do not want the decorator to be applied.
def cache_memoize_conditional(fn):
    if cache_found:
        return cache.memoize()(fn)
    else:
        return fn

@cache_memoize_conditional
def download_counties_json(url):
    with urlopen(url) as response:
        counties_json = json.load(response)
    return counties_json

def get_counties_json():
    return download_counties_json(GEOJSON_COUNTIES_URL)

@cache_memoize_conditional
def get_list_csvfiles(url):
    html = pd.read_html(url)
    df = html[0]
    df.drop(columns=['Description'], inplace=True)
    df.dropna(inplace=True)
    df = df[df['Name'].str.contains('StormEvents_details.*d20', regex=True)]

    files_dict = {}
    for fname in df['Name']:
        result = re.findall('_d(?P<year>\d{4})', fname)
        if len(result) > 0:
            files_dict[result[0]] = fname
    return files_dict

def get_list_years():
    files_dict = get_list_csvfiles(NOAA_CSVFILES_URL)
    return files_dict.keys()

@cache_memoize_conditional
def get_bls_cpi():
    return pd.read_csv(BLS_CPI_CSV)

# the dataframes for every year are cached in a globally available
# Redis memory store which is available across processes
# and for all time.
@cache_memoize_conditional
def get_storm_data(year, inflation, cache_id=CACHE_DATAFRAME):
    conn = psycopg2.connect(
        host=ENDPOINT,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database = DATABASE
    )
    with conn:
        select = f'SELECT * from counties WHERE "Year" = {year}'
        df_counties = pd.read_sql(select, con=conn)
    conn.close()

    df_bls_cpi = get_bls_cpi() # get the inflation cpi for the years 2000-2021
    df_cpi_2020 = df_bls_cpi[df_bls_cpi['year']==2020] # adjust damage to 2020 dollars
    df_cpi_2020.reset_index(drop=True, inplace=True) # inflation for month 12 is at iloc 0;
    df_cpi_year = df_bls_cpi[df_bls_cpi['year']==int(year)]
    df_cpi_year.reset_index(drop=True, inplace=True)

    df_counties['DATA_COL'] = df_counties['DATA_COL'].apply(lambda x : x.split('|'))
    lst_features = ['Population', 
                    'County Business Patterns', '# establishments','Annual payroll($1000)','# employees',
                    'Nonemployer Statistics', '# establishments','Revenue($1,000)',
                    'Economic Data', 
                    'Rank #1 Industry', 'Value of business($1000)', '# establishments', '# employees',
                    'Rank #2 Industry', 'Value of business($1000)', '# establishments', '# employees',
                    'Rank #3 Industry', 'Value of business($1000)', '# establishments', '# employees']

    df_county_details = df_counties[['FIPS', 'NAME', 'DATA_COL']].copy()
    df_county_details = df_county_details.drop_duplicates(subset = ["FIPS"]) # drop duplicates
    df_county_details['Features'] = [lst_features for _ in range(len(df_county_details))]
    df_county_details = df_county_details.explode(['Features','DATA_COL'], ignore_index=True)

    df_counties.drop(columns=['DATA_COL'], inplace=True)    

    county_dict = {} # key is FIPS, value is a list [name, dict {EVENT_TYPE: BEGIN_YEARMONTH%100/BEGIN_DAY}, total damage]
    def build_map_dict(row):
        categories = STORM_CATEGORIES.keys()
        for k, v in STORM_CATEGORIES.items():
            searchStr = '|'.join(v)
            row[k] = re.search(searchStr, row['EVENT_TYPE']) != None

        county_id = row['FIPS']
        if county_id not in county_dict:
            county_dict[county_id] = [row['NAME'], {}, 0, {}, 0, {}, 0, {}, 0]
            county_dict[county_id].extend([False]*len(categories))
        
        eventDateStr = str(row['EVENT_DATE'].month)+'/'+str(row['EVENT_DATE'].day)
        if row['EVENT_TYPE'] not in county_dict[county_id][1]:
            county_dict[county_id][1][row['EVENT_TYPE']] = set()
            county_dict[county_id][1][row['EVENT_TYPE']].add(eventDateStr)
        else:
            county_dict[county_id][1][row['EVENT_TYPE']].add(eventDateStr)

        damage = row['TOTAL_DAMAGE']
        mth = row['EVENT_DATE'].month
        if inflation: # adjust for inflation
            damage = damage * (df_cpi_2020.iloc[12 - mth]['value']/df_cpi_year.iloc[12 - mth]['value'])

        county_dict[county_id][2] = county_dict[county_id][2] + damage
        for i, c in enumerate(categories):
            if row[c]:
                county_dict[county_id][i+9] = row[c]
                if row['EVENT_TYPE'] not in county_dict[county_id][2*i+3]:
                    county_dict[county_id][2*i+3][row['EVENT_TYPE']] = set()
                    county_dict[county_id][2*i+3][row['EVENT_TYPE']].add(eventDateStr)
                else:
                    county_dict[county_id][2*i+3][row['EVENT_TYPE']].add(eventDateStr)
                county_dict[county_id][2*i+4] += damage
        return row

    df_counties.apply(build_map_dict, axis=1)

    # prepare df_map for Plotly maps
    lst_columns = ['NAME', 'ALL_EVENTS', 'TOTAL_DAMAGE', 
                           'EVENT_TYPE_0', 'TYPE_0_DAMAGE',
                           'EVENT_TYPE_1', 'TYPE_1_DAMAGE',
                           'EVENT_TYPE_2', 'TYPE_2_DAMAGE']
    lst_columns.extend(STORM_CATEGORIES.keys())
    
    df_map = pd.DataFrame.from_dict(county_dict, orient='index', columns=lst_columns)
    df_map.reset_index(inplace=True)
    df_map.rename(columns={'index': 'FIPS'}, inplace=True)

    def build_event_type(row):
        event_desc = ''
        for k, v in row.items():
            if len(event_desc) != 0:
                event_desc += '; '
            event_desc += k + ': ' + ', '.join(v) # v is a set
        return event_desc
    df_map['ALL_EVENTS'] = df_map['ALL_EVENTS'].apply(build_event_type)
    df_map['EVENT_TYPE_0'] = df_map['EVENT_TYPE_0'].apply(build_event_type)
    df_map['EVENT_TYPE_1'] = df_map['EVENT_TYPE_1'].apply(build_event_type)
    df_map['EVENT_TYPE_2'] = df_map['EVENT_TYPE_2'].apply(build_event_type)

    return df_map, df_counties, df_county_details
