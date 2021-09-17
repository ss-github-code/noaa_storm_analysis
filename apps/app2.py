import numpy as np
import pandas as pd
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px

from dash.dependencies import Input, Output
from urllib.error import HTTPError

import dash_alternative_viz as dav
import altair as alt

from app_df import get_counties_json, get_list_years, get_storm_data, CACHE_FIGURE
from app import app, cache

alt.data_transformers.disable_max_rows()
alt.renderers.enable('default', embed_options={'actions': False}); # hide the option to export chart as png

# Constants
WILDFIRE_DATA_URL = 'https://raw.githubusercontent.com/ss-github-code/noaa_storm_analysis/main/data/wildfires/'
df_zone_county = pd.read_csv('data/zone_county_corr.csv')

severity_categories = [{'label': 'Abnormally dry', 'value': 'D0'}, 
                       {'label': 'Moderate', 'value': 'D1'},
                       {'label': 'Severe', 'value': 'D2'},
                       {'label': 'Extreme', 'value': 'D3'},
                       {'label': 'Exceptional', 'value': 'D4'}]

layout = html.Div([
    html.Div([
        html.H2('Exploring weather conditions unique to wildfires'),
        html.P('This dashboard presents the drought conditions and weather statistics unique to wildfires.'),
        html.Div([
            html.Div([
                html.Label('Select year:'),
                dcc.Dropdown(
                    clearable=False,
                    id='year',
                    options=[{'label': i, 'value': i} for i in get_list_years()],
                    value='2017'),
                html.Br(),
                html.Label('Select drought severity:'),
                dcc.Dropdown(
                    clearable=False,
                    id='severity',
                    options=severity_categories, 
                    value='D0'),
            ], className='two columns'),
            html.Div([
                html.Label('Select event:'),
                dcc.Dropdown(
                    clearable=False,
                    id='event'),
            ], className='sevend columns')
        ]),

        html.Div(dcc.Graph(id='graph-usdm-map', config={'displayModeBar': False}), className='seven columns'),
    ], className='row'),
    html.Div([
        html.Td([dav.VegaLite(id="vega2")], className='offset-by-one columns'),
    ], className='row'),
    # signal value to trigger callbacks
    dcc.Store(id='signal2')    
])

@app.callback(Output('event', 'options'),
              Output('event', 'value'),
              Output('signal2', 'data'),              
              Input('year', 'value'))
def update_events(year):
    _, df_counties, _ = get_storm_data(year)
    df_counties = df_counties[df_counties['EVENT_TYPE'] == 'Wildfire']
    df_counties.sort_values('TOTAL_DAMAGE', ascending=False, inplace=True)

    lst_options = []
    toret = None
    for i, row in df_counties.iterrows():
        optionStr = str(row['EVENT_DATE'].month)+'/'+str(row['EVENT_DATE'].day)
        optionStr += '; ' + row['NAME']
        optionStr += '; Damage: ' + f"{int(row['TOTAL_DAMAGE']):,}"
        optionStr += '; fips: ' + row['FIPS']
        lst_options.append({'label': optionStr, 'value': i})
        if toret is None:
            toret = i
    return lst_options, toret, year

@cache.memoize()
def generate_figure2(year, severity, index, df_counties, cache_id=CACHE_FIGURE):
    
    dirname = WILDFIRE_DATA_URL + str(year) + '/'
        
    # Get USDM csv file based on the EVENT_DATE
    # USDM csv files are named with a "date".csv where date is always a Tuesday
    today = df_counties.iloc[index]['EVENT_DATE']
    dirname += today.strftime('%m_%d') + '_' + df_counties.iloc[index]['FIPS']
        
    df_usdm = pd.read_csv(dirname+'/usdm.csv')
       
    df_usdm_merged = df_usdm.merge(df_zone_county, on=['FIPS'])
    df_usdm_merged['NAME'] = df_usdm_merged['County'] + ', ' + df_usdm_merged['State']

    wildfire_county_df = df_usdm_merged[df_usdm_merged['FIPS'] == int(df_counties.iloc[index]['FIPS'])]
    # print(wildfire_county_df.shape, df_counties.iloc[wildfiresDrop.index]['FIPS'])
    df_usdm_merged['FIPS'] = df_usdm_merged['FIPS'].astype(str) # cast it as string in order to zfill
    df_usdm_merged['FIPS'] = df_usdm_merged['FIPS'].apply(lambda x: x.zfill(5)) # no need to zfill

        
    county_idx = wildfire_county_df.iloc[0].name

    #data = df_usdm_merged[['LAT', 'LON']].values.tolist()
    counties = get_counties_json()
        
    fig = px.scatter_geo(geojson = counties, 
                            locations=[df_usdm_merged.iloc[county_idx]['FIPS']],
                            hover_name=[df_counties.iloc[index]['NAME']],
                            color_discrete_sequence=['green'],
                            size=[50],
                            basemap_visible = False,
                            scope = 'usa')

    fig_drought = px.choropleth(df_usdm_merged, 
                    geojson = counties,    # use the geo info for counties
                    locations='FIPS',      # location is based on FIPS code
                    hover_name = 'NAME',   # this has both the county and state name
                    hover_data = {'FIPS': False},
                    color = severity,      # Drought level
                    color_continuous_scale='ylorrd',
                    scope = 'usa') # set the scope to usa to automatically configure the 
                                    # map to display USA-centric data in an appropriate projection.
    fig_drought.add_trace(fig.data[0])
    titleStr = f'Map of {severity} drought conditions<br>'
    titleStr += f"near {df_counties.iloc[index]['NAME']}<br>"
    titleStr += f"on {df_counties.iloc[index]['EVENT_DATE'].strftime('%m-%d')}"
    fig_drought.update_layout(title_text = titleStr)
    return fig_drought

@app.callback(Output('graph-usdm-map', 'figure'), 
              Input('event', 'value'),
              Input('severity', 'value'),
              Input('signal2', 'data'))
def update_graph_usdm_map(event, severity, data):
    # get_storm_data has been fetched in the compute_value callback and 
    # the result is stored in the global redis cached
    year = data
    _, df_counties,_ = get_storm_data(year)
    return generate_figure2(year, severity, event, df_counties)

@app.callback(Output('vega2', 'spec'), 
              Input('event', 'value'),
              Input('signal2', 'data'))
def update_county_info(event, data):
    year = data
    index = event
    dirname = WILDFIRE_DATA_URL + str(year) + '/'

    _, df_counties,_ = get_storm_data(year)

    # Get USDM csv file based on the EVENT_DATE
    # USDM csv files are named with a "date".csv where date is always a Tuesday
    today = df_counties.iloc[index]['EVENT_DATE']
    dirname += today.strftime('%m_%d') + '_' + df_counties.iloc[index]['FIPS']

    # Precipitation data
    try:
        df_weather = pd.read_csv(dirname + '/weather.csv')
    except HTTPError as err:
        toret = alt.Chart(df_counties).mark_text().encode(
        ).properties(
            title=f"No weather data found for {df_counties.iloc[index]['NAME']}"
        ).configure_view(strokeOpacity=0)
        return toret.to_dict()
            
    df_weather.fillna(0, inplace=True)
    df_weather['PRCP'] = df_weather['PRCP'] + df_weather['SNOW']
    df_weather['DATE'] = pd.to_datetime(df_weather['DATE'])
    df_weather_year = df_weather[['DATE','PRCP']].copy()
    df_weather_year['YEAR'] = df_weather['DATE'].apply(lambda r : r.year)
    
    # print(df_weather['TMAX'].max(), df_weather['TMAX'].min())\n",
    q1 = df_weather['TMAX'].quantile(0.25)
    q3 = df_weather['TMAX'].quantile(0.75)
    lower_bound = q1 - 1.5*(q3-q1)
    upper_bound = q3 + 1.5*(q3-q1)
    df_weather['TMAX'].clip(lower_bound, upper_bound, inplace=True)
        
    df_weather_year = df_weather_year.groupby('YEAR', as_index=False).sum()

    line_prcp = alt.Chart(df_weather).mark_line(color='blue', strokeWidth=0.5).transform_window(
        rolling_mean_prcp='mean(PRCP)',
        frame=[-30,0]
    ).encode(
        x = alt.X('DATE:T', axis=alt.Axis(grid=False), title=None),
        y = alt.Y('rolling_mean_prcp:Q', axis=alt.Axis(grid=False), title='PRCP (mm)'),
    ).properties(
        title='30 day rolling average precipitation (mm) for the last 10 years',
        height=150,
        width=800)
    bar_prcp = alt.Chart(df_weather_year).mark_bar(color='blue').encode(
        x = alt.X('YEAR:O', axis=alt.Axis(grid=False), title=None),
        y = alt.Y('PRCP:Q', axis=alt.Axis(grid=False), title='Annual PRCP (mm)'),
    )
    rule = alt.Chart(df_weather_year).mark_rule(color='red').encode(
        y = 'mean(PRCP):Q'
    )
    bar_prcp = (bar_prcp + rule).properties(
        title='Total annuanl PRCP (mm) for the last 10 years with mean',
        height=150,
        width=800
    )
    line_tmin = alt.Chart(df_weather).mark_line(strokeWidth=0.5).transform_window(
        rolling_mean_tmin='mean(TMIN)',
        frame=[-30,0]
    ).encode(
        x = alt.X('DATE:T', axis=alt.Axis(grid=False), title=None),
        y = alt.Y('rolling_mean_tmin:Q', axis=alt.Axis(grid=False), title='TMIN'),
        color=alt.value('blue')
    )
    line_tmax = alt.Chart(df_weather).mark_line(strokeWidth=0.5).transform_window(
        rolling_mean_tmax='mean(TMAX)',
        frame=[-30,0]
    ).encode(
        x = alt.X('DATE:T', axis=alt.Axis(grid=False), title=None),
        y = alt.Y('rolling_mean_tmax:Q', axis=alt.Axis(grid=False), title='TMAX (°C)'),
        color=alt.value('red'), 
    )
    
    #toret = (chart + line).properties(width=800)
    toret = alt.layer(line_tmin, line_tmax).resolve_scale(y='shared').properties(
        title='30 day rolling average min & max temperature (°C) for the last 10 years',
        height=350,
        width=800)
    toret = (line_prcp & bar_prcp & toret).configure_view(strokeOpacity=0)
    #toret = (line_prcp & line_tmin)#.properties(width=800)
    #toret = (line_tmin).properties(width=800)

    return toret.to_dict()