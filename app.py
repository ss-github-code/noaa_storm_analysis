import os
import dash
from flask_caching import Cache

external_stylesheets = [
    # Dash CSS
    'css/styles.css',
    # Loading screen CSS
    'https://codepen.io/chriddyp/pen/brPBPO.css']

app = dash.Dash(__name__,
                external_stylesheets=external_stylesheets)
server = app.server
# print('REDIS_URL', os.environ.get('REDIS_URL'))
CACHE_CONFIG = {
    # try 'filesystem' if you don't want to setup redis
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': os.environ.get('REDIS_URL', 'redis://localhost:6379')
}

cache = Cache()
cache.init_app(app.server, config=CACHE_CONFIG)