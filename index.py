import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output

from app import app, server
from apps import app1

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

@app.callback(Output('page-content', 'children'),
              Input('url', 'pathname'))
def display_page(pathname):
    print(pathname)
    if pathname == '/':
        return app1.layout
    else:
        return '404'

if __name__ == '__main__':
    app.run_server(debug=False, processes=6, threaded=False, host="0.0.0.0", port=8080)