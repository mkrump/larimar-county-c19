from datetime import datetime
import re

import plotly.graph_objs as go
import dash
import dash_core_components as dcc
import plotly.express as px
import dash_html_components as html
import requests
from bs4 import BeautifulSoup
from dash.dependencies import Input, Output
from flask_caching import Cache
import pandas as pd
import logging

app = dash.Dash(__name__)
app.title = 'Larimer County Positive COVID-19 Dashboard'
server = app.server
server.config.from_object("settings")
logging.basicConfig(level='INFO')

cache = Cache()
cache.init_app(
    app.server,
    config={
        "CACHE_DIR": server.config["CACHE_DIR"],
        "CACHE_TYPE": server.config["CACHE_TYPE"],
        "CACHE_DEFAULT_TIMEOUT": server.config["CACHE_DEFAULT_TIMEOUT"],
    }
)

MARKDOWN = '''
#### 
This dashboard summarizes the Larimar County COVID-19 case data found on the 
[Larimar County health department website](https://www.larimer.org/health/communicable-disease/coronavirus-covid-19/larimer-county-positive-covid-19-numbers). 


Select a city to see city level statistics or to compare the number of COVID-19 cases between the various cities in Larimar County.
Clear the city filter to see a summary for all of Larimar County. 
'''

app.layout = html.Div(
    style={"marginTop": "5rem"},
    className="container",
    children=
    [
        html.Div(
            className="row app-row",
            children=[
                html.H1("Larimer County Positive COVID-19 Dashboard"),
                dcc.Markdown(MARKDOWN)
            ],
        ),
        # TODO fix size of text on mobile?
        html.Div(
            className="row app-row",
            children=[
                html.Div(
                    className="one-half column",
                    children=[
                        html.Label("Select a City", className="select-city-label"),
                        dcc.Dropdown(id='demo-dropdown', multi=True),

                    ],
                )],
        ),
        html.Div(id='graph-container', className="u-max-full-width"),
        html.Div(id='ticker-text', className="row ticker-text"),
        dcc.Interval(id='interval', interval=server.config["UPDATE_INTERVAL"], n_intervals=0),
    ],
)


@cache.memoize()
def update_metrics():
    r = requests.get(
        "https://www.larimer.org/health/communicable-disease/coronavirus-covid-19/larimer-county-positive-covid-19-numbers"
    )
    data = []
    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find('table')
    text = soup.find(text=re.compile(r'On \d{1,2}/\d{1,2}/\d{4}')).parent.getText()
    dt, t = re.search(r'(\d{1,2}/\d{1,2}/\d{4}) at (\d{1,2}:\d{1,2}\w{2})', text).groups()
    last_update = datetime.strptime("{} {}".format(dt, t), '%m/%d/%Y %H:%M%p')
    rows = table.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        cols = [ele.text.strip() for ele in cols]
        data.append([ele for ele in cols if ele])  # Get rid of empty values
    columns = data[0]
    cols = [c.lower().replace(" ", '_') for c in columns]
    data = pd.DataFrame(data[1:], columns=cols)
    # if True:
    #     data = pd.read_csv("./data.csv")
    #     last_update = pd.to_datetime("2020-03-22T10:00:00")
    data.reported_date = pd.to_datetime(data.reported_date)
    return data, last_update.isoformat()


@app.callback(Output('ticker-text', 'children'),
              [Input('interval', 'n_intervals')])
def update_date(n_intervals):
    # call once and chain other dependent calls of this, so not making
    # api calls on every update
    _, now = update_metrics()
    return [html.P(f"Last update: {now}")]


@app.callback(
    Output('demo-dropdown', "options"),
    [Input('ticker-text', "children")])
def update_dropdown(children):
    orig_df, _ = update_metrics()
    # TODO would be nice not do this each time probably can cache too
    df = orig_df.drop_duplicates(subset=['city'])
    values = [{"label": value, "value": value} for label, value in zip(df['city'], df['city']) if label]
    return sorted(values, key=lambda k: k['label'])


@app.callback(
    Output('graph-container', "children"),
    [
        Input('demo-dropdown', "value"),
        Input('ticker-text', "children")
    ]
)
def update_figure(cities, _):
    figures = []
    now = datetime.now().isoformat()
    logging.info("update_figure {0}".format(now))
    orig_df, _ = update_metrics()
    if cities is None or len(cities) == 0:
        fig = top(orig_df)
        figures.append(dcc.Graph(id="top_n", figure=fig, className="plot"))
        fig = cumulative_by_day_scatter(orig_df)
        figures.append(dcc.Graph(id="by_day_cumulative", figure=fig, className="plot"))
        fig = by_day_scatter(orig_df)
        figures.append(dcc.Graph(id="by_day", figure=fig, className="plot"))
        fig = histogram(orig_df, "age_range",
                        layout_overrides={"title": "<b>Total Confirmed COVID-19 Cases by Age Range</b>"})
        figures.append(dcc.Graph(id="age_range", figure=fig, className="plot"))
        fig = histogram(orig_df, "gender",
                        layout_overrides={"title": "<b>Total Confirmed COVID-19 Cases by Gender</b>"})
        figures.append(dcc.Graph(id="gender", figure=fig, className="plot"))
        return figures

    dff = orig_df[orig_df["city"].isin(cities)]
    fig = cumulative_by_city(dff)
    figures.append(dcc.Graph(id="by_day", figure=fig, className="plot"))
    fig = by_day_by_city_scatter(dff)
    figures.append(dcc.Graph(id="by_day_cumulative", figure=fig, className="plot"))
    fig = histogram_by_city(orig_df, "age_range", cities,
                            layout_overrides={"title": "<b>Total Confirmed COVID-19 Cases by Age Range</b>"})
    figures.append(dcc.Graph(id="age_range", figure=fig, className="plot"))
    fig = histogram_by_city(orig_df, "gender", cities,
                            layout_overrides={"title": "<b>Total Confirmed COVID-19 Cases by Gender</b>"})
    figures.append(dcc.Graph(id="gender", figure=fig, className="plot"))
    return figures

def top(df):
    fig = go.Figure({
        "data": [
            {
                "x": df["city"],
                "type": "histogram",
            }
        ],
        "layout": {
            "title": {"text": f"<b>Total Confirmed COVID-19 Cases by City</b>"},
            "xaxis": {"automargin": True, "title": "Date Reported"},
            "yaxis": {
                "automargin": True,
                "title": {"text": "Count"}
            },
        },
    })
    fig.update_xaxes(categoryorder="total descending")
    return fig


def by_day_by_city_scatter(df, layout_overrides=None):
    x = df.groupby(["city", "reported_date"]).size().reset_index(name='counts')
    x.reported_date = pd.to_datetime(x.reported_date)
    x.set_index(
        ['reported_date', 'city']
    ).unstack(
        fill_value=0
    ).asfreq(
        'D', fill_value=0
    ).stack().sort_index(level=1).reset_index()

    x = x.sort_values(['city', 'reported_date'])
    layout = {
        "title": {"text": f"<b>Total Confirmed COVID-19 Cases by Day</b>"},
        "xaxis": {"automargin": True},
        "yaxis": {
            "automargin": True,
            "title": {"text": "Count"}
        },
    }
    if layout_overrides:
        layout.update(layout_overrides)
    fig = px.scatter(x, x="reported_date", y="counts", color="city")
    fig.update_layout(layout)
    fig.update_traces(mode='lines+markers')
    return fig


def cumulative_by_city(df, layout_overrides=None):
    by_city_by_day = df.groupby(["city", "reported_date"]).size().reset_index(name='counts')
    by_city_by_day.reported_date = pd.to_datetime(by_city_by_day.reported_date)
    by_city_by_day.set_index(
        ['reported_date', 'city']
    ).unstack(
        fill_value=0
    ).asfreq(
        'D', fill_value=0
    ).stack().sort_index(level=1).reset_index()
    by_city_by_day = by_city_by_day.sort_values(['city', 'reported_date'])
    by_city_by_day["cumulative_sum"] = by_city_by_day.groupby('city')['counts'].cumsum()
    layout = {
        "title": {"text": f"<b>Total Cumulative Confirmed COVID-19 Cases by Day</b>"},
        "xaxis": {"automargin": True},
        "yaxis": {
            "automargin": True,
            "title": {"text": "Count"}
        },
    }
    if layout_overrides:
        layout.update(layout_overrides)
    fig = px.scatter(by_city_by_day, x="reported_date", y="cumulative_sum", color="city")
    fig.update_layout(layout)
    fig.update_traces(mode='lines+markers')
    return fig


def by_day_scatter(df, layout_overrides=None):
    by_day = df['reported_date'].dt.date.value_counts()
    by_day.index = pd.to_datetime(by_day.index)
    by_day = by_day.resample("D").sum().fillna(0)
    by_day = by_day.sort_index()
    layout = {
        "title": {"text": f"<b>Total Confirmed COVID-19 Cases by Day</b>"},
        "xaxis": {"automargin": True},
        "yaxis": {
            "automargin": True,
            "title": {"text": "Count"}
        },
    }
    if layout_overrides:
        layout.update(layout_overrides)
    fig = go.Figure({
        "data": [
            {
                "type": "scatter",
                "x": by_day.index,
                "y": by_day,
                "mode": "lines+markers"
            }
        ],
        "layout": layout,
    })
    return fig


def cumulative_by_day_scatter(df, layout_overrides=None):
    by_day = df.groupby(["reported_date"]).size().reset_index(name='counts')
    by_day.reported_date = pd.to_datetime(by_day.reported_date)
    by_day.set_index(
        ['reported_date']
    ).asfreq(
        'D', fill_value=0
    ).sort_index(level=1).reset_index()
    by_day["cumulative_sum"] = by_day['counts'].cumsum()
    layout = {
        "title": {"text": f"<b>Total Cumulative Confirmed COVID-19 Cases by Day</b>"},
        "xaxis": {"automargin": True},
        "yaxis": {
            "automargin": True,
            "title": {"text": "Count"}
        },
    }
    if layout_overrides:
        layout.update(layout_overrides)
    fig = go.Figure(
        data=go.Scatter(x=by_day.reported_date, y=by_day.cumulative_sum, mode='lines+markers'),
        layout=layout
    )

    return fig


def histogram_by_city(df, column, cities, layout_overrides=None, sort_by_total=False):
    layout = {
        "xaxis": {"automargin": True},
        "yaxis": {
            "automargin": True,
            "title": {"text": "Count"}
        },
    }
    if layout_overrides:
        layout.update(layout_overrides)
    x = (df.groupby(["city", column])[column]
         .count()
         .unstack(fill_value=0)
         .stack()
         .sort_index(level=0)
         .reset_index(name="counts")
         )
    bars = []
    for city in cities:
        bar = x[x.city == city]
        bars.append(go.Bar(name=city, x=bar[column], y=bar.counts))
    fig = go.Figure(data=bars)
    fig.update_layout(barmode='group')
    fig.update_layout(layout)
    if sort_by_total:
        fig.update_xaxes(categoryorder="total descending")
    fig.update_xaxes(categoryorder="category ascending")
    return fig


def histogram(df, column, layout_overrides=None, sort_by_total=False):
    layout = {
        "xaxis": {"automargin": True},
        "yaxis": {
            "automargin": True,
            "title": {"text": "Count"}
        },
    }
    if layout_overrides:
        layout.update(layout_overrides)
    fig = go.Figure({
        "data": [
            {
                "x": df[column],
                "type": "histogram",
            }
        ],
        "layout": layout,
    })
    if sort_by_total:
        fig.update_xaxes(categoryorder="total descending")
    fig.update_xaxes(categoryorder="category ascending")
    return fig


if __name__ == '__main__':
    app.run_server(host=server.config["HOST"], debug=server.config["DEBUG"], port=server.config["PORT"])
