
MIN_DAMAGE = 1_000_000
BEGIN_YEAR = 2000
END_YEAR = 2022

ZONE_COUNTY_CORR_URL = 'https://www.weather.gov/source/gis/Shapefiles/County/bp10nv20.dbx'
ZONE_COUNTY_CORR_CSV = 'https://raw.githubusercontent.com/ss-github-code/noaa_storm_analysis/main/data/zone_county_corr.csv'
BLS_CPI_CSV = 'https://raw.githubusercontent.com/ss-github-code/noaa_storm_analysis/main/data/bls_cpi.csv'
NOAA_CSVFILES_URL = 'https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
GEOJSON_COUNTIES_URL = 'https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json'

TABLE_COLUMNS_NOAA = ['NAME', 'FIPS', 'STATE', 'EVENT_TYPE', 'EVENT_DATE', 'TOTAL_DAMAGE', 'TORNADO_STRENGTH', 'DURATION']

STORM_CATEGORIES = {
    'Tropical Cyclones/Floods' : ['Hurricane', 'Storm Surge', 'Tropical Storm', 'Flood'],
    'Severe Local Storms': ['Tornado', 'Hail', 'Thunderstorm', 'Wind'],
    'Wildfires/Droughts': ['Wildfire', 'Drought']
}
