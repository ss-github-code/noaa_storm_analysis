import numpy as np
import pandas as pd
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
from dash.dependencies import Input, Output
import dash_alternative_viz as dav
import altair as alt

from app_df import get_counties_json, get_storm_data, get_list_years, CACHE_FIGURE
from notebooks.data_constants import STORM_CATEGORIES
from app import app, cache

alt.data_transformers.disable_max_rows()
alt.renderers.enable('default', embed_options={'actions': False}); # hide the option to export chart as png

option_categories = [{'label': 'All events', 'value': 'all'}]
for k, _ in STORM_CATEGORIES.items():
    option_categories.append({'label': k, 'value': k})

layout = html.Div([
    html.Div([
        html.H2('Economic Damage from Natural Disasters in the USA'),
        html.P(['This dashboard presents the damage caused by storms in the USA as reported in the storm events database ' \
               'released by the National Oceanic and Atmospheric Administration (NOAA). We report the independent variables ' \
               'from the affected county like population and economic activity that could be used to predict the total damage ' \
               'caused by the natural disasters in the USA. The dashboard allows you to explore three main types of storms - ' \
               'tropical storms/cyclones, severe local storms, and wildfires/droughts. ', 
               html.A('Explore wildfires here.', href='/wildfires', target='_blank')]),
        html.Div([
            html.Label('Select year:'),
            dcc.Dropdown(
                clearable=False,
                id='year',
                options=[{'label': i, 'value': i} for i in get_list_years()],
                value='2017'),
            html.Br(),
            html.Label('Select layer:'),
            dcc.Dropdown(
                clearable=False,
                id='layers',
                options=option_categories, 
                value='all'),
        ], className='two columns'),

        html.Div(dcc.Graph(id='graph-us-map', config={'displayModeBar': False}), className='seven columns'),
    ], className='row'),
    html.Br(),
    html.P('Click on an event in the graph below to see the statistics for the affected county:'),
    html.Div([
        html.Td([dav.VegaLite(id="vega")], className='offset-by-one columns'),
    ], className='row'),
    # signal value to trigger callbacks
    dcc.Store(id='signal')
])

@cache.memoize()
def generate_figure(year, layers='all', cache_id=CACHE_FIGURE):
    title_event = 'storms'
    df_map, _, _ = get_storm_data(year)
    map_columns = df_map.columns
    if layers != 'all':
        df_map = df_map[df_map[layers]==True]
        title_event = layers

    if df_map.shape[0] == 0:
        df_map = pd.DataFrame([[0]*len(map_columns)], columns=map_columns.tolist())

    counties = get_counties_json()

    if layers == 'all':
        hover_data_dict = {'FIPS': False, 'ALL_EVENTS' : True, 'TOTAL_DAMAGE': True}
        color_col = 'TOTAL_DAMAGE'
    else:
        for i, k in enumerate(STORM_CATEGORIES.keys()):
            if k == layers:
                df_map = df_map[['FIPS', 'NAME', 'EVENT_TYPE_'+str(i), 'TYPE_'+str(i)+'_DAMAGE']]
                df_map.rename(columns={'EVENT_TYPE_'+str(i) : 'EVENTS', 'TYPE_'+str(i)+'_DAMAGE': 'DAMAGES'}, inplace=True)
                hover_data_dict = {'FIPS': False, 'EVENTS' : True, 'DAMAGES': True}
                color_col = 'DAMAGES'
                break
    
    fig = px.choropleth(df_map, 
                    geojson = counties,    # use the geo info for counties
                    locations='FIPS',      # location is based on FIPS code
                    hover_name = 'NAME',   # this has both the county and state name
                    hover_data = hover_data_dict,
                    color = color_col,          # TOTAL_DAMAGE or DAMAGE
                    # color_continuous_scale='viridis',
                    scope = 'usa') # set the scope to usa to automatically configure the 
                                   # map to display USA-centric data in an appropriate projection.
    fig.update_layout(title_text = f'<b>Total damage in $ from {title_event} in year {year}</b>',
                      title_font_size=13, title_x=0.5, title_xanchor='center') # match font-size and location with Altair
    # fig['layout'] = {'margin': {'l': 20, 'r': 10, 'b': 20, 't': 10}}
    return fig

@app.callback(Output('signal', 'data'), 
              Input('year', 'value'),
              Input('layers', 'value'))
def compute_value(year, layers):
    # compute value and send a signal when done
    _, _, _ = get_storm_data(year)
    return (year, layers)

@app.callback(Output('graph-us-map', 'figure'),
              Input('signal', 'data'))
def update_graph_us_map(data):
    # get_storm_data has been fetched in the compute_value callback and 
    # the result is stored in the global redis cached
    year, layers = data
    return generate_figure(year, layers=layers)

months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 
             'August', 'September', 'October', 'November', 'December']
@app.callback(Output('vega', 'spec'),
              Input('signal', 'data'))
def update_graph_(data):
    year, layers = data
    # get_storm_data has been fetched in the compute_value callback and 
    # the result is stored in the global redis cached
    _, df_counties, df_county_details = get_storm_data(year)
    titleStr = "All events"
    if layers != 'all':
        df_counties = df_counties[df_counties[layers]==True]
        titleStr = layers

    temp_df = df_counties[['EVENT_TYPE', 'NAME', 'FIPS', 'TOTAL_DAMAGE', 'EVENT_DATE']]
    if temp_df.shape[0]:
        selection = alt.selection_multi(fields=['EVENT_TYPE'], bind='legend')
        brush = alt.selection(type='single', empty='none', fields=['FIPS'])

        chart = alt.Chart(temp_df).mark_circle().encode(
            x = alt.X('EVENT_DATE:T', axis=alt.Axis(grid=False)),
            y = alt.Y('TOTAL_DAMAGE:Q', title = 'Total damage $(log)', scale=alt.Scale(type='log'), axis=alt.Axis(grid=False)),
            size = alt.Size('TOTAL_DAMAGE:Q',scale=alt.Scale(type='log')),
            color = alt.condition(brush, alt.value('black'), 'EVENT_TYPE:N'),
            opacity=alt.condition(selection, alt.value(1), alt.value(0)),
            tooltip = [alt.Tooltip('NAME'), 
                       alt.Tooltip('TOTAL_DAMAGE', format=','), 
                       alt.Tooltip('EVENT_TYPE'),
                       alt.Tooltip('EVENT_DATE')]
            ).add_selection(
                selection
            ).add_selection(
                brush
            ).properties(
                title = alt.TitleParams([f'Total damage caused by {titleStr} (in $) in year {str(year)}',' ']),
                height = 500,
                width = 450
            )

        text = alt.Chart(df_county_details).mark_text(align='left', dy=-5, limit=100).encode(
            x=alt.value(0),
            y=alt.Y('row_number:O', axis=alt.Axis(labels=False, grid=True, title=None, ticks=False, domain=False)),
        ).transform_window(
            row_number='row_number()'
        ).transform_filter(
            brush
        )
        # Data Tables
        desc = text.encode(
                text='Features:N',
                tooltip=[alt.Tooltip('NAME'), alt.Tooltip('Features', title='Feature')]
            ).properties(title=alt.TitleParams('Features', anchor='start'), width=100)
        vals = text.encode(
                text='DATA_COL:N',
                tooltip=[alt.Tooltip('NAME'), alt.Tooltip('Features', title='Feature'), alt.Tooltip('DATA_COL', title='Value')]
            ).properties(title=alt.TitleParams('Values', anchor='start'), width=100)
        chart = alt.hconcat(chart, desc, vals).configure_view(strokeOpacity=0)        
    else:
        chart = alt.Chart(df_counties).mark_point(

        ).properties(
            title = alt.TitleParams(['No events of the type ' + layers + ' found for the year ' + str(year), ' '])
        )

    return chart.to_dict()