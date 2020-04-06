import copy
import io
import logging
import re
from datetime import datetime

import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import requests
from dash.dependencies import Input, Output
from flask import send_file
from flask_caching import Cache

app = dash.Dash(__name__)
app.index_string = """<!DOCTYPE html>
<html>
    <head>
        <meta name="Description" content="A dashboard tracking COVID-19 cases in Larimer County, Colorado">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script type="application/ld+json">
        {
          "@context": "http://schema.org",
          "@type": "WebApplication",
          "name": "Larimer County COVID-19",
          "url": "https://www.larimer-county-c19.com/",
          "description": "A dashboard tracking COVID-19 cases in Larimer County, Colorado",
          "applicationCategory": "Health, Visualization",
          "keywords": "Larimer County, COVID-19, Coronavirus",
          "browserRequirements": "Requires JavaScript",
          "softwareVersion": "1.0.0",
          "operatingSystem": "All"
        }
        </script>
        <!-- Global site tag (gtag.js) - Google Analytics -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-XR42PS5B9B"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());

          gtag('config', 'G-XR42PS5B9B');
        </script>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""

app.title = 'Larimer County COVID-19'
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
cache.clear()

MARKDOWN = '''
#### 
This site summarizes the Larimer County COVID-19 case data found on the 
[Larimer County Health Department website](https://www.larimer.org/health/communicable-disease/coronavirus-covid-19/larimer-county-positive-covid-19-numbers).

Select a city to see city level data. Select multiple cities to compare between 
cities within Larimer County. Clear the city filter for a summary of all of Larimer County. 

*This site is not affiliated with the Larimer County Health Department.*
'''

app.layout = html.Div(
    style={"marginTop": "5rem"},
    className="container",
    children=
    [
        html.Div(
            className="row app-row",
            children=[
                html.H2("Larimer County COVID-19"),
                dcc.Markdown(MARKDOWN)
            ],
        ),
        html.Div(
            className="row app-row",
            children=[
                html.Div(
                    id="dropdown-container",
                    className="one-half column",
                    children=[
                        html.Label("Select a City", className="select-city-label"),
                        dcc.Dropdown(id='demo-dropdown', multi=True),

                    ],
                )],
        ),
        dcc.Loading(id='loading', children=[
            html.Div(id='graph-container', className="u-max-full-width"),
        ]),
        html.Div(id='ticker-text', className="row ticker-text"),
        dcc.Interval(id='interval', interval=server.config["UPDATE_INTERVAL"], n_intervals=0),
        dcc.Markdown(
            "Matthew Krump | [matthewkrump.com](https://matthewkrump.com/) | Rendered by [Dash](https://plotly.com/dash/)",
            id='footer', className="footer", )

    ],
)


@cache.cached()
def update_metrics():
    # cases
    r = requests.get(
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vQLNokCu-CD-7XMSqhV1-t4H0cYzOcszJIf8KCyr3yP82jZ2TD53iWaFb7r_7dtAELfTt8ndM-dQvgj/pub?output=csv"
    )
    cases_df = create_cases_df(r.content)

    # deaths
    r = requests.get(
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vQLNokCu-CD-7XMSqhV1-t4H0cYzOcszJIf8KCyr3yP82jZ2TD53iWaFb7r_7dtAELfTt8ndM-dQvgj/pub?output=csv&gid=71138259"
    )
    deaths_df = create_deaths_df(r.content)
    now = datetime.now().isoformat()
    logging.info("update_metrics {0}".format(now))
    return deaths_df, cases_df, datetime.now().isoformat()


# date format is bad / missing year sometimes
# try to fix these if possible
def fix_bad_dates(d):
    date_parts = d.split("/")
    if len(date_parts) == 2:
        return f"{date_parts[0]}/{date_parts[1]}/2020"
    return d


def create_deaths_df(deaths):
    bs = io.BytesIO(deaths)
    deaths_df = pd.read_csv(bs, encoding="utf-8")
    columns = [format_column(x) for x in deaths_df.columns]
    deaths_df.columns = columns
    deaths = deaths_df.dropna(axis=0, how='all')
    deaths.city = deaths_df.city.str.title()
    deaths.age = deaths.age.apply(lambda x: str(int(x) - (int(x) % 10)) + "s")
    deaths.sex = deaths.sex.replace({"F": "Female", "M": "Male"})
    return deaths


def format_column(col):
    f_col = re.findall('[A-Z][a-z]*', col)
    f_col = [x.lower() for x in f_col]
    return "_".join(f_col)


def create_cases_df(cases):
    bs = io.BytesIO(cases)
    cases_df = pd.read_csv(bs, encoding="utf-8")
    columns = [format_column(x) for x in cases_df.columns]
    cases_df.columns = columns
    cases_df = cases_df.dropna(axis=0, how='all')
    cases_df.city = cases_df.city.str.title()
    cases_df.sex = cases_df.sex.str.title()
    cases_df.reported_date = cases_df.reported_date.apply(fix_bad_dates)
    cases_df.reported_date = pd.to_datetime(cases_df.reported_date)
    return cases_df


def parse_table(html_table):
    data = []
    rows = html_table.find_all('tr')
    for i, row in enumerate(rows):
        cells = row.find_all('td')
        parsed_row = []
        for j, cell in enumerate(cells):
            # some malformed tags with inline styles
            # exclude these.
            has_style = cell.find('style')
            # TODO maybe change to below to exclude all non-string tags
            # "".join([x.strip() for x in cell if isinstance(x, bs4.element.NavigableString)])
            if has_style:
                cell.style.extract()
            parsed_row.append(cell.get_text(strip=True))
        data.append(parsed_row)
    return data


@app.callback(Output('ticker-text', 'children'),
              [Input('interval', 'n_intervals')])
def update_date(n_intervals):
    # call once and chain other dependent calls of this, so not making
    # api calls on every update
    try:
        _, _, now = update_metrics()
        return [html.P(f"Last update: {now}")]
    except:
        return html.Div(
            className='global-error',
            children=[
                html.I(className="fa fa-times-circle"),
                '  There was an issue retrieving the updated data. Please check back shortly.'
            ]
        )


@app.callback(
    Output('demo-dropdown', "options"),
    [Input('ticker-text', "children")])
def update_dropdown(children):
    _, cases_df, _ = update_metrics()
    # TODO would be nice not do this each time probably can cache too
    df = cases_df.drop_duplicates(subset=['city'])
    values = [{"label": value, "value": value} for label, value in zip(df['city'], df['city']) if label]
    return sorted(values, key=lambda k: k['label'])


@app.callback(
    Output('graph-container', "children"),
    [
        Input('demo-dropdown', "value"),
        Input('ticker-text', "children")
    ]
)
@cache.memoize()
def update_figure(cities, _):
    figures = []
    now = datetime.now().isoformat()
    logging.info("update_figure {0}".format(now))
    deaths_df, cases_df, _ = update_metrics()
    if cities is None or len(cities) == 0:
        fig = cumulative_by_day_scatter(cases_df)
        figures.append(dcc.Graph(id="by_day_cumulative", figure=fig, className="plot"))
        fig = by_day_scatter(cases_df)
        figures.append(dcc.Graph(id="by_day", figure=fig, className="plot"))
        fig = top(cases_df)
        figures.append(dcc.Graph(id="top_n", figure=fig, className="plot"))
        fig = top(deaths_df, layout_overrides={"title": "<b>COVID-19 Deaths by City</b>"})
        figures.append(dcc.Graph(id="deaths", figure=fig, className="plot"))
        # 100s, 20s etc sort by numeric value
        age_labels = sorted(cases_df.age.unique(), key=lambda x: int(x.replace("s", "")))
        fig = histogram(cases_df, "age", layout_overrides={
            "title": "<b>COVID-19 Cases by Age Range</b>",
            "xaxis": {"categoryarray": age_labels, "categoryorder": "array"}})
        figures.append(dcc.Graph(id="age", figure=fig, className="plot"))
        fig = histogram(deaths_df, "age", layout_overrides={
            "title": "<b>COVID-19 Deaths by Age Range</b>",
            "xaxis": {"categoryarray": age_labels, "categoryorder": "array"}})
        figures.append(dcc.Graph(id="deaths_age", figure=fig, className="plot"))
        fig = histogram(cases_df, "sex", layout_overrides={"title": "<b>COVID-19 Cases by Sex</b>"})
        figures.append(dcc.Graph(id="sex", figure=fig, className="plot"))
        fig = histogram(deaths_df, "sex", layout_overrides={
            "title": "<b>COVID-19 Deaths by Sex</b>",
            "xaxis": {"categoryarray": ["Female", "Male"], "categoryorder": "array"},
        })
        figures.append(dcc.Graph(id="deaths_sex", figure=fig, className="plot"))
        return figures

    dff = cases_df[cases_df["city"].isin(cities)]
    fig = cumulative_by_city(dff)
    figures.append(dcc.Graph(id="by_day", figure=fig, className="plot"))
    fig = by_day_by_city_scatter(dff)
    figures.append(dcc.Graph(id="by_day_cumulative", figure=fig, className="plot"))
    age_labels = sorted(cases_df.age.unique(), key=lambda x: int(x.replace("s", "")))
    fig = histogram_by_city(cases_df, "age", cities, layout_overrides={
        "title": "<b>COVID-19 Cases by Age Range</b>",
        "xaxis": {"categoryarray": age_labels, "categoryorder": "array"}})
    figures.append(dcc.Graph(id="deaths_age", figure=fig, className="plot"))
    fig = histogram_by_city(deaths_df, "age", cities, layout_overrides={
        "title": "<b>COVID-19 Deaths by Age Range</b>",
        "xaxis": {"categoryarray": age_labels, "categoryorder": "array"}})
    figures.append(dcc.Graph(id="age", figure=fig, className="plot"))
    fig = histogram_by_city(cases_df, "sex", cities, layout_overrides={"title": "<b>COVID-19 Cases by Sex</b>"})
    figures.append(dcc.Graph(id="deaths_sex", figure=fig, className="plot"))
    fig = histogram_by_city(deaths_df, "sex", cities, layout_overrides={
        "title": "<b>COVID-19 Deaths by Sex</b>",
        "xaxis": {"categoryarray": ["Female", "Male"], "categoryorder": "array"},
    })
    figures.append(dcc.Graph(id="sex", figure=fig, className="plot"))
    return figures


DEFAULT_LAYOUT = {
    "margin": {
        "l": 0,
        "r": 0,
        "pad": 0,
    },
    "xaxis": {
        "automargin": True,
        "title": None,
    },
    "yaxis": {
        "automargin": True,
        "title": None
    },
}


def top(df, layout_overrides=None):
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    fig = go.Figure({
        "data": [
            {
                "x": df["city"],
                "type": "histogram",
            },
        ],
        "layout": layout,
    })
    fig.update_layout(title_text="<b>COVID-19 Cases by City</b>")
    fig.update_xaxes(categoryorder="total descending")
    if layout_overrides:
        layout.update(layout_overrides)
    fig.update_layout(layout)
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
    fig = px.bar(x, x="reported_date", y="counts", color="city", barmode='group')
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    # No trendlines for now
    # fig2 = px.scatter(x, x="reported_date", y="counts", color="city", trendline="lowess")
    # trendlines = fig2.data[1::2]
    # _ = [fig.add_trace(t) for t in trendlines]
    fig.update_layout(title_text="<b>Daily COVID-19 Cases</b>")
    fig.update_layout(showlegend=True, legend_title=None, legend_orientation="h")
    if layout_overrides:
        layout.update(layout_overrides)
    fig.update_layout(layout)
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

    fig = px.scatter(by_city_by_day, x="reported_date", y="cumulative_sum", color="city")
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    fig.update_layout(title_text="<b>Cumulative COVID-19 Cases")
    fig.update_layout(showlegend=True, legend_title=None, legend_orientation="h")
    fig.update_traces(mode='lines+markers')
    if layout_overrides:
        layout.update(layout_overrides)
    fig.update_layout(layout)
    return fig


def by_day_scatter(df, layout_overrides=None):
    by_day = df['reported_date'].dt.date.value_counts()
    by_day.index = pd.to_datetime(by_day.index)
    by_day = by_day.resample("D").sum().fillna(0)
    by_day = by_day.sort_index()
    fig = px.bar(x=by_day.index, y=by_day)
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    # No trendlines for now
    # fig2 = px.scatter(x=by_day.index, y=by_day, trendline="lowess", color_discrete_sequence=["red"])
    # trendline = fig2.data[1]
    # fig.add_trace(trendline)
    fig.update_layout(title_text="<b>Daily COVID-19 Cases</b>")
    if layout_overrides:
        layout.update(layout_overrides)
    fig.update_layout(layout)
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

    fig = go.Figure(data=go.Scatter(x=by_day.reported_date, y=by_day.cumulative_sum, mode='lines+markers'))
    fig.update_layout(title_text="<b>Cumulative COVID-19 Cases</b>")
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    if layout_overrides:
        layout.update(layout_overrides)
    fig.update_layout(layout)
    return fig


def histogram_by_city(df, column, cities, layout_overrides=None):
    x = (df.groupby(["city", column])[column]
         .count()
         .unstack(fill_value=0)
         .stack()
         .sort_index(level=0)
         .reset_index(name="counts")
         )

    bars = []
    categories = None
    try:
        categories = layout_overrides["xaxis"]["categoryarray"]
    except:
        pass
    for city in cities:
        bar = x[x.city == city]
        if categories is not None:
            cats = pd.DataFrame(categories, columns=[column])
            cats["counts"] = 0
            cats["city"] = city
            missing_cats = cats[~cats[column].isin(bar[column])]
            bar = pd.concat([missing_cats, bar])
        bars.append(go.Bar(name=city, x=bar[column], y=bar.counts))

    fig = go.Figure(data=bars)
    fig.update_layout(barmode='group')
    fig.update_layout(showlegend=True, legend_orientation="h")
    fig.update_xaxes(categoryorder="category ascending")
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    if layout_overrides:
        layout.update(layout_overrides)
    fig.update_layout(layout)
    return fig


def histogram(df, column, layout_overrides=None):
    x = (df.groupby([column])[column]
         .count()
         .reset_index(name="counts")
         .sort_index(level=0))
    categories = None
    try:
        categories = layout_overrides["xaxis"]["categoryarray"]
    except:
        pass
    if categories is not None:
        cats = pd.DataFrame(categories, columns=[column])
        cats["counts"] = 0
        missing_cats = cats[~cats[column].isin(x[column])]
        x = pd.concat([missing_cats, x])
    fig = go.Figure(data=go.Bar(x=x[column], y=x.counts))
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    fig.update_xaxes(categoryorder="category ascending")
    if layout_overrides:
        layout.update(layout_overrides)
    fig.update_layout(layout)
    return fig


@app.server.route('/robots.txt')
def robots():
    return send_file('robots.txt', mimetype="text")


if __name__ == '__main__':
    app.run_server(host=server.config["HOST"], debug=server.config["DEBUG"], port=server.config["PORT"])
