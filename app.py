import os

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

from preprocess import run_pipeline, compute_summary


APP_TITLE = "NYC Airbnb Performance Dashboard"
DATA_SOURCE = "data/listings_monthly.csv"
RECENT_MONTHS = 12
PRICE_SCALE = [
    [0.0, "#eef4ff"],
    [0.35, "#b7ccff"],
    [0.7, "#5a84ea"],
    [1.0, "#1f4fd6"],
]
ROOM_TYPE_COLORS = {
    "Entire Home": "#1f4fd6",
    "Private Room": "#1f9ca8",
    "Hotel Room": "#d97d54",
    "Shared Room": "#9a78d0",
}
TEXT_COLOR = "#172033"
MUTED_COLOR = "#667085"
GRID_COLOR = "rgba(23, 32, 51, 0.08)"
LINE_COLOR = "#1f4fd6"
GRAPH_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "lasso2d",
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
        "toggleSpikelines",
    ],
    "responsive": True,
}


# ---------- Data Loading ----------


def format_price_mark(value: int) -> str:
    if value >= 1000:
        if value % 1000 == 0:
            return f"${value // 1000}k"
        if value % 500 == 0:
            return f"${value / 1000:.1f}k"
        return f"${value:,}"
    return f"${value}"


def build_price_marks(price_min: int, price_max: int) -> dict[int, str]:
    value_range = max(price_max - price_min, 1)
    rough_step = value_range / 4
    nice_steps = [25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000]
    step = next((candidate for candidate in nice_steps if candidate >= rough_step), nice_steps[-1])

    start = (price_min // step) * step
    if start < price_min:
        start += step

    tick_values = [price_min]
    tick_values.extend(range(start, price_max + 1, step))
    if tick_values[-1] != price_max:
        tick_values.append(price_max)

    tick_values = sorted(set(int(value) for value in tick_values if price_min <= value <= price_max))
    return {value: format_price_mark(value) for value in tick_values}


def neighborhood_sort_key(value: str) -> tuple[int, str]:
    if value == "Unknown":
        return (1, value)
    return (0, value)


def build_metadata(clean_df: pd.DataFrame) -> dict:
    month_lookup = (
        clean_df[["month_key", "month_label", "month_date"]]
        .drop_duplicates()
        .sort_values("month_date")
        .reset_index(drop=True)
    )

    price_min = int(max(0, (clean_df["avg_daily_rate"].min() // 10) * 10))
    price_max = int(min(1000, ((clean_df["avg_daily_rate"].max() // 50) + 1) * 50))

    return {
        "default_month": month_lookup.iloc[-1]["month_key"],
        "default_month_label": month_lookup.iloc[-1]["month_label"],
        "latest_month": month_lookup.iloc[-1]["month_label"],
        "month_coverage": f"{month_lookup.iloc[0]['month_label']} - {month_lookup.iloc[-1]['month_label']}",
        "month_options": [
            {"label": row.month_label, "value": row.month_key}
            for row in month_lookup.itertuples(index=False)
        ],
        "neighborhood_options": [
            {"label": value, "value": value}
            for value in sorted(clean_df["neighborhood"].dropna().unique(), key=neighborhood_sort_key)
        ],
        "room_type_options": [
            {"label": value, "value": value}
            for value in sorted(clean_df["room_type"].dropna().unique())
        ],
        "price_min": price_min,
        "price_max": price_max,
        "price_marks": build_price_marks(price_min, price_max),
    }


df_clean, df_map, df_scatter, df_bar, df_time = run_pipeline(
    "data/listings_monthly.csv",
    recent_months=None,
)

end_date = df_clean["month_date"].max()
start_date = df_clean["month_date"].min()
recent_start_date = end_date - pd.DateOffset(months=RECENT_MONTHS - 1)

df_recent = df_clean[df_clean["month_date"] >= recent_start_date].copy()
df_map_recent = df_map[df_map["month_date"] >= recent_start_date].copy()
df_scatter_recent = df_scatter[df_scatter["month_date"] >= recent_start_date].copy()
df_bar_recent = df_bar[df_bar["month_date"] >= recent_start_date].copy()
df_time_recent = df_time[df_time["month_date"] >= recent_start_date].copy()

summary = compute_summary(df_recent)
metadata = build_metadata(df_clean)
metadata["viewing_label"] = f"Last {RECENT_MONTHS} months"
metadata["time_range_options"] = [
    {"label": f"Last {RECENT_MONTHS} months", "value": "recent"},
    {"label": "Full history", "value": "full"},
]
metadata["recent_months"] = RECENT_MONTHS
metadata["recent_start"] = recent_start_date
metadata["recent_start_label"] = recent_start_date.strftime("%b %Y")
metadata["full_start_label"] = start_date.strftime("%b %Y")
metadata["full_end_label"] = end_date.strftime("%b %Y")


# ---------- Layout ----------


def format_currency(value: float) -> str:
    return f"${value:,.0f}"


def format_percentage(value: float) -> str:
    return f"{value * 100:.1f}%"


def metric_card(label: str, value_id: str, initial_value: str) -> html.Div:
    return html.Div(
        className="metric-card",
        children=[
            html.Div(label, className="metric-label"),
            html.Div(initial_value, id=value_id, className="metric-value"),
        ],
    )


def chart_card(title: str, description: str, graph_id: str, card_class: str) -> html.Section:
    return html.Section(
        className=f"chart-card card {card_class}",
        children=[
            html.Div(
                className="card-header",
                children=[
                    html.Div(
                        children=[
                            html.H3(title, className="card-title"),
                            html.P(description, className="card-description"),
                        ]
                    )
                ],
            ),
            dcc.Graph(id=graph_id, className="chart-graph", config=GRAPH_CONFIG),
        ],
    )


def build_layout(metadata: dict, summary: dict) -> html.Div:
    default_price = [metadata["price_min"], metadata["price_max"]]

    return html.Div(
        className="app-shell",
        children=[
            html.Div(
                className="page-container",
                children=[
                    html.Header(
                        className="page-header",
                        children=[
                            html.Div(
                                children=[
                                    html.Div("AIRBNB MARKET ANALYSIS", className="eyebrow"),
                                    html.H1(APP_TITLE, className="page-title"),
                                    html.P(
                                        (
                                            "Explore pricing power, occupancy, neighborhood demand, "
                                            "and seasonal revenue patterns across New York City listings."
                                        ),
                                        className="page-subtitle",
                                    ),
                                ]
                            ),
                            html.Div(
                                className="header-chip",
                                children=[
                                    html.Div(
                                        className="header-chip-section",
                                        children=[
                                            html.Div("Data Coverage", className="header-chip-label"),
                                            html.Div(metadata["month_coverage"], className="header-chip-value"),
                                        ],
                                    ),
                                    html.Div(
                                        className="header-chip-section",
                                        children=[
                                            html.Div("Viewing", className="header-chip-label"),
                                            html.Div(metadata["viewing_label"], id="viewing-label", className="header-chip-value secondary"),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="dashboard-shell",
                        children=[
                            html.Aside(
                                className="sidebar-card",
                                children=[
                                    html.Div(
                                        children=[
                                            html.H2("Filters", className="sidebar-title"),
                                            html.P("Applies to all views", className="sidebar-note"),
                                        ]
                                    ),
                                    html.Div(
                                        id="sidebar-viewing-chip",
                                        className="sidebar-note",
                                        children="",
                                    ),
                                    html.Div(
                                        className="filter-group",
                                        children=[
                                            html.Label("Neighborhood", className="filter-label"),
                                            dcc.Dropdown(
                                                id="neighborhood-filter",
                                                options=metadata["neighborhood_options"],
                                                value=[],
                                                multi=True,
                                                placeholder="All ZIP codes",
                                                className="dashboard-dropdown",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="filter-group",
                                        children=[
                                            html.Label("Room Type", className="filter-label"),
                                            dcc.Dropdown(
                                                id="room-type-filter",
                                                options=metadata["room_type_options"],
                                                value=[],
                                                multi=True,
                                                placeholder="All room types",
                                                className="dashboard-dropdown",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="filter-group",
                                        children=[
                                            html.Label("Price Range", className="filter-label"),
                                            dcc.RangeSlider(
                                                id="price-filter",
                                                min=metadata["price_min"],
                                                max=metadata["price_max"],
                                                value=default_price,
                                                marks=metadata["price_marks"],
                                                allowCross=False,
                                                updatemode="mouseup",
                                                tooltip={"placement": "bottom", "always_visible": False},
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="filter-group",
                                        children=[
                                            html.Label("Time Range", className="filter-label"),
                                            dcc.Dropdown(
                                                id="time-range-filter",
                                                options=metadata["time_range_options"],
                                                value="recent",
                                                clearable=False,
                                                searchable=False,
                                                className="dashboard-dropdown",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="filter-group",
                                        children=[
                                            html.Label("Snapshot Month", className="filter-label"),
                                            dcc.Dropdown(
                                                id="month-filter",
                                                options=metadata["month_options"],
                                                value=metadata["default_month"],
                                                clearable=False,
                                                searchable=False,
                                                className="dashboard-dropdown",
                                            ),
                                        ],
                                    ),
                                    html.Button(
                                        "Reset filters and map selection",
                                        id="reset-filters",
                                        className="reset-button",
                                        n_clicks=0,
                                    ),
                                    html.P(
                                        (
                                            "Tip: drag on the map to focus a cluster of listings. "
                                            "The scatter, neighborhood ranking, and trend view will update together."
                                        ),
                                        className="sidebar-footnote",
                                    ),
                                ],
                            ),
                            html.Main(
                                className="main-panel",
                                children=[
                                    dcc.Loading(
                                        type="circle",
                                        color=LINE_COLOR,
                                        className="dashboard-loading",
                                        children=html.Div(
                                            className="main-visual-layout",
                                            children=[
                                                html.Div(
                                                    className="editorial-layout",
                                                    children=[
                                                        html.Div(
                                                            className="editorial-left",
                                                            children=[
                                                                html.Div(id="insight-banner", className="insight-banner"),
                                                                html.Div(
                                                                    className="metric-strip editorial-metrics",
                                                                    children=[
                                                                        metric_card(
                                                                            "Total Listings",
                                                                            "metric-listings",
                                                                            f"{summary['total_listings']:,}",
                                                                        ),
                                                                        metric_card(
                                                                            "Average Daily Rate",
                                                                            "metric-price",
                                                                            format_currency(summary["avg_price"]),
                                                                        ),
                                                                        metric_card(
                                                                            "Average Occupancy",
                                                                            "metric-occupancy",
                                                                            format_percentage(summary["avg_occupancy"]),
                                                                        ),
                                                                        metric_card(
                                                                            "Average Revenue",
                                                                            "metric-revenue",
                                                                            format_currency(summary["avg_revenue"]),
                                                                        ),
                                                                    ],
                                                                ),
                                                                chart_card(
                                                                    "Price and Revenue Map",
                                                                    "Bubble size reflects revenue and color reflects average daily rate for the selected month.",
                                                                    "airbnb-map",
                                                                    "map-card editorial-map-card",
                                                                ),
                                                            ],
                                                        ),
                                                        html.Div(
                                                            className="editorial-right",
                                                            children=[
                                                                chart_card(
                                                                    "Price vs Occupancy",
                                                                    "Compare pricing against demand by room type for the selected month.",
                                                                    "price-occupancy-scatter",
                                                                    "editorial-side-card scatter-card",
                                                                ),
                                                                chart_card(
                                                                    "Neighborhood Price Ranking",
                                                                    "Compare neighborhoods by average daily rate using the pre-aggregated bar dataset.",
                                                                    "neighborhood-bar",
                                                                    "editorial-side-card bar-card",
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                chart_card(
                                                    "Monthly Price Trend",
                                                    "Track how average daily rates move through the selected time range.",
                                                    "seasonality-line",
                                                    "line-card trend-full-width-card",
                                                ),
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ],
    )


# ---------- Figure Builders ----------


def base_layout(height: int) -> dict:
    return {
        "height": height,
        "margin": {"l": 16, "r": 16, "t": 8, "b": 8},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Avenir Next, SF Pro Display, Helvetica Neue, sans-serif", "color": TEXT_COLOR},
        "transition": {"duration": 350, "easing": "cubic-in-out"},
    }


def empty_figure(message: str, height: int) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**base_layout(height))
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 15, "color": MUTED_COLOR},
        align="center",
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def build_map_figure(map_df: pd.DataFrame, selected_ids: list[str]) -> go.Figure:
    if map_df.empty:
        return empty_figure("No listings match the current filters.", 700)

    revenue_max = max(float(map_df["revenue"].max()), 1.0)
    sizeref = (2.0 * revenue_max) / (28**2)
    color_min = float(map_df["avg_daily_rate"].min())
    color_max = float(map_df["avg_daily_rate"].quantile(0.98))
    if color_max <= color_min:
        color_max = color_min + 1

    selected_set = set(selected_ids)
    selected_points = [
        idx for idx, listing_id in enumerate(map_df["listing_id"]) if listing_id in selected_set
    ]

    fig = go.Figure(
        go.Scattermapbox(
            lat=map_df["latitude"],
            lon=map_df["longitude"],
            mode="markers",
            customdata=list(
                zip(
                    map_df["listing_id"],
                    map_df["neighborhood"],
                    map_df["room_type"],
                    map_df["avg_daily_rate"].round(0),
                    map_df["occupancy_pct"].round(1),
                    map_df["revenue"].round(0),
                    map_df["property_type"],
                )
            ),
            marker={
                "size": map_df["revenue"].clip(lower=1),
                "sizemode": "area",
                "sizeref": sizeref,
                "sizemin": 6,
                "color": map_df["avg_daily_rate"],
                "colorscale": PRICE_SCALE,
                "cmin": color_min,
                "cmax": color_max,
                "opacity": 0.86,
                "colorbar": {
                    "title": {"text": "Avg Daily Rate", "side": "top"},
                    "tickprefix": "$",
                    "thickness": 12,
                    "len": 0.42,
                    "x": 0.98,
                    "y": 0.95,
                    "yanchor": "top",
                    "outlinewidth": 0,
                },
            },
            selectedpoints=selected_points or None,
            selected={"marker": {"opacity": 0.98}},
            unselected={"marker": {"opacity": 0.28}},
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "Listing ID: %{customdata[0]}<br>"
                "Room Type: %{customdata[2]}<br>"
                "Property: %{customdata[6]}<br>"
                "Avg Daily Rate: $%{customdata[3]:,.0f}<br>"
                "Occupancy: %{customdata[4]:.1f}%<br>"
                "Revenue: $%{customdata[5]:,.0f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        **base_layout(700),
        mapbox={
            "style": "carto-positron",
            "zoom": 10.25,
            "center": {
                "lat": float(map_df["latitude"].mean()),
                "lon": float(map_df["longitude"].mean()),
            },
        },
        dragmode="select",
        uirevision="nyc-airbnb-map",
        clickmode="event+select",
    )
    return fig


def build_scatter_figure(scatter_df: pd.DataFrame) -> go.Figure:
    if scatter_df.empty:
        return empty_figure("No listing points to compare for this month.", 480)

    figure_df = scatter_df.sort_values("avg_daily_rate")
    fig = go.Figure()

    for room_type, group in figure_df.groupby("room_type", dropna=False):
        fig.add_trace(
            go.Scatter(
                x=group["avg_daily_rate"],
                y=group["occupancy"],
                mode="markers",
                name=room_type,
                customdata=list(
                    zip(
                        group["listing_id"],
                        group["neighborhood"],
                        group["revenue"].round(0),
                        group["property_type"],
                    )
                ),
                marker={
                    "size": 11,
                    "color": ROOM_TYPE_COLORS.get(room_type, "#98A2B3"),
                    "opacity": 0.8,
                    "line": {"color": "#ffffff", "width": 0.8},
                },
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "Listing ID: %{customdata[0]}<br>"
                    "Price: $%{x:,.0f}<br>"
                    "Occupancy: %{y:.1%}<br>"
                    "Revenue: $%{customdata[2]:,.0f}<br>"
                    "Property: %{customdata[3]}<extra></extra>"
                ),
            )
        )

    price_mid = figure_df["avg_daily_rate"].median()
    occupancy_mid = figure_df["occupancy"].median()
    fig.add_vline(x=price_mid, line_dash="dot", line_color="rgba(23,32,51,0.25)")
    fig.add_hline(y=occupancy_mid, line_dash="dot", line_color="rgba(23,32,51,0.25)")
    fig.update_layout(
        **base_layout(480),
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "title": None,
        },
        hovermode="closest",
    )
    fig.update_xaxes(
        title="Average Daily Rate",
        tickprefix="$",
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
    )
    fig.update_yaxes(
        title="Occupancy",
        tickformat=".0%",
        range=[0, 1.05],
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
    )
    return fig


def build_bar_figure(bar_df: pd.DataFrame) -> go.Figure:
    if bar_df.empty:
        return empty_figure("No neighborhood comparison is available for this view.", 480)

    figure_df = (
        bar_df.sort_values(["avg_daily_rate", "listing_count"], ascending=[False, False])
        .head(12)
        .sort_values("avg_daily_rate", ascending=True)
    )

    fig = go.Figure(
        go.Bar(
            x=figure_df["avg_daily_rate"],
            y=figure_df["neighborhood"],
            orientation="h",
            marker={"color": LINE_COLOR, "opacity": 0.9},
            text=[f"${value:,.0f}" for value in figure_df["avg_daily_rate"]],
            textposition="outside",
            customdata=list(
                zip(
                    figure_df["avg_revenue"].round(0),
                    figure_df["avg_occupancy_pct"].round(1),
                    figure_df["listing_count"],
                )
            ),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Average Daily Rate: $%{x:,.0f}<br>"
                "Average Revenue: $%{customdata[0]:,.0f}<br>"
                "Average Occupancy: %{customdata[1]:.1f}%<br>"
                "Listings: %{customdata[2]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(**base_layout(480), showlegend=False)
    fig.update_xaxes(
        title="Average Daily Rate",
        tickprefix="$",
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
    )
    fig.update_yaxes(title=None, showgrid=False, automargin=True)
    return fig


def build_line_figure(time_df: pd.DataFrame, selected_month: str) -> go.Figure:
    if time_df.empty:
        return empty_figure("No trend data is available after filtering.", 500)

    fig = go.Figure(
        go.Scatter(
            x=time_df["month_date"],
            y=time_df["avg_daily_rate"],
            mode="lines+markers",
            line={"color": LINE_COLOR, "width": 3, "shape": "spline", "smoothing": 0.75},
            marker={"size": 7, "color": "#ffffff", "line": {"color": LINE_COLOR, "width": 2}},
            customdata=list(
                zip(
                    time_df["month_label"],
                    time_df["avg_occupancy_pct"].round(1),
                    time_df["avg_revenue"].round(0),
                    time_df["listing_count"],
                )
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Average Daily Rate: $%{y:,.0f}<br>"
                "Average Occupancy: %{customdata[1]:.1f}%<br>"
                "Average Revenue: $%{customdata[2]:,.0f}<br>"
                "Listings: %{customdata[3]}<extra></extra>"
            ),
        )
    )

    selected_month_ts = pd.to_datetime(selected_month)
    selected_row = time_df.loc[time_df["month_date"] == selected_month_ts]
    if not selected_row.empty:
        fig.add_vline(x=selected_month_ts, line_dash="dot", line_color="rgba(31,79,214,0.32)")
        fig.add_trace(
            go.Scatter(
                x=selected_row["month_date"],
                y=selected_row["avg_daily_rate"],
                mode="markers",
                marker={"size": 13, "color": LINE_COLOR, "line": {"color": "#ffffff", "width": 2}},
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.update_layout(**base_layout(500), hovermode="x unified", showlegend=False)
    fig.update_xaxes(title=None, showgrid=False, tickformat="%b\n%Y", dtick="M1")
    fig.update_yaxes(
        title="Average Daily Rate",
        tickprefix="$",
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
    )
    return fig


# ---------- Filtering Helpers ----------


def apply_listing_filters(
    df: pd.DataFrame,
    neighborhoods: list[str] | None,
    room_types: list[str] | None,
    price_range: list[int] | None,
    selected_month: str | None = None,
) -> pd.DataFrame:
    filtered = df
    if selected_month:
        filtered = filter_snapshot_month(filtered, selected_month)
    if neighborhoods:
        filtered = filtered[filtered["neighborhood"].isin(neighborhoods)]
    if room_types:
        filtered = filtered[filtered["room_type"].isin(room_types)]
    if price_range and len(price_range) == 2:
        filtered = filtered[
            filtered["avg_daily_rate"].between(price_range[0], price_range[1], inclusive="both")
        ]
    return filtered.copy()


def apply_aggregated_filters(
    df: pd.DataFrame,
    neighborhoods: list[str] | None,
    room_types: list[str] | None,
    price_range: list[int] | None,
    selected_month: str | None = None,
) -> pd.DataFrame:
    filtered = df
    if selected_month:
        filtered = filter_snapshot_month(filtered, selected_month)
    if neighborhoods:
        filtered = filtered[filtered["neighborhood"].isin(neighborhoods)]
    if room_types:
        filtered = filtered[filtered["room_type"].isin(room_types)]
    if price_range and len(price_range) == 2:
        filtered = filtered[
            filtered["avg_daily_rate"].between(price_range[0], price_range[1], inclusive="both")
        ]
    return filtered.copy()


def filter_snapshot_month(df: pd.DataFrame, selected_month: str) -> pd.DataFrame:
    if df.empty or not selected_month or "month_date" not in df.columns:
        return df.copy()

    selected_period = pd.to_datetime(selected_month).to_period("M")
    month_period = pd.to_datetime(df["month_date"], errors="coerce").dt.to_period("M")
    return df[month_period == selected_period].copy()


def ensure_non_empty(filtered_df: pd.DataFrame, original_df: pd.DataFrame) -> pd.DataFrame:
    if filtered_df.empty:
        return original_df.copy()
    return filtered_df.copy()


def extract_selected_ids(selected_data: dict | None) -> list[str]:
    if not selected_data or not selected_data.get("points"):
        return []

    selected_ids: list[str] = []
    for point in selected_data["points"]:
        custom_data = point.get("customdata") or []
        if custom_data:
            selected_ids.append(str(custom_data[0]))
    return list(dict.fromkeys(selected_ids))


def weighted_group_summary(group: pd.DataFrame) -> pd.Series:
    weights = group["listing_count"].clip(lower=1)
    total_weight = float(weights.sum())
    if total_weight <= 0:
        total_weight = 1.0

    return pd.Series(
        {
            "avg_daily_rate": float((group["avg_daily_rate"] * weights).sum() / total_weight),
            "avg_revenue": float((group["avg_revenue"] * weights).sum() / total_weight),
            "avg_occupancy_pct": float((group["avg_occupancy_pct"] * weights).sum() / total_weight),
            "listing_count": int(weights.sum()),
        }
    )


def aggregate_bar_from_precomputed(bar_df: pd.DataFrame) -> pd.DataFrame:
    if bar_df.empty:
        return pd.DataFrame(columns=["neighborhood", "avg_daily_rate", "avg_revenue", "avg_occupancy_pct", "listing_count"])

    return (
        bar_df.groupby("neighborhood", group_keys=False)
        .apply(weighted_group_summary)
        .reset_index()
    )


def aggregate_time_from_precomputed(time_df: pd.DataFrame) -> pd.DataFrame:
    if time_df.empty:
        return pd.DataFrame(
            columns=["month_date", "month_label", "avg_daily_rate", "avg_revenue", "avg_occupancy_pct", "listing_count"]
        )

    aggregated = (
        time_df.groupby(["month_date", "month_label"], group_keys=False)
        .apply(weighted_group_summary)
        .reset_index()
        .sort_values("month_date")
    )
    return aggregated


def aggregate_bar_from_listings(listings_df: pd.DataFrame) -> pd.DataFrame:
    if listings_df.empty:
        return pd.DataFrame(columns=["neighborhood", "avg_daily_rate", "avg_revenue", "avg_occupancy_pct", "listing_count"])

    return (
        listings_df.groupby("neighborhood", as_index=False)
        .agg(
            avg_daily_rate=("avg_daily_rate", "mean"),
            avg_revenue=("revenue", "mean"),
            avg_occupancy_pct=("occupancy_pct", "mean"),
            listing_count=("listing_id", "nunique"),
        )
    )


def aggregate_time_from_listings(listings_df: pd.DataFrame) -> pd.DataFrame:
    if listings_df.empty:
        return pd.DataFrame(
            columns=["month_date", "month_label", "avg_daily_rate", "avg_revenue", "avg_occupancy_pct", "listing_count"]
        )

    return (
        listings_df.groupby(["month_date", "month_label"], as_index=False)
        .agg(
            avg_daily_rate=("avg_daily_rate", "mean"),
            avg_revenue=("revenue", "mean"),
            avg_occupancy_pct=("occupancy_pct", "mean"),
            listing_count=("listing_id", "nunique"),
        )
        .sort_values("month_date")
    )


def build_banner(
    selected_month: str,
    snapshot_count: int,
    selected_ids: list[str],
    neighborhoods: list[str] | None,
    room_types: list[str] | None,
    viewing_label: str,
) -> list[html.Div]:
    month_label = pd.to_datetime(selected_month).strftime("%B %Y")
    filters_active = bool(neighborhoods or room_types)
    scope_text = "Focused view" if filters_active else "Market overview"
    selection_text = f"Map selection: {len(selected_ids)} listings" if selected_ids else "Map selection: none"
    return [
        html.Div(
            className="banner-primary",
            children=[
                html.Div(scope_text, className="banner-label"),
                html.Div(
                    f"{month_label} snapshot",
                    className="banner-value",
                ),
            ],
        ),
    ]


def resolve_time_scope(time_range: str, selected_month: str) -> tuple[str, str]:
    selected_month_ts = pd.to_datetime(selected_month)
    if time_range == "recent" and selected_month_ts < recent_start_date:
        return "full", "Full history (month override)"
    if time_range == "full":
        return "full", "Full history"
    return "recent", f"Last {RECENT_MONTHS} months"


def dataset_bundle_for_scope(scope: str) -> dict[str, pd.DataFrame]:
    if scope == "full":
        return {
            "clean": df_clean,
            "map": df_map,
            "scatter": df_scatter,
            "bar": df_bar,
            "time": df_time,
        }
    return {
        "clean": df_recent,
        "map": df_map_recent,
        "scatter": df_scatter_recent,
        "bar": df_bar_recent,
        "time": df_time_recent,
    }


# ---------- Callbacks ----------


def register_callbacks(app: Dash) -> None:
    @app.callback(
        Output("neighborhood-filter", "value"),
        Output("room-type-filter", "value"),
        Output("price-filter", "value"),
        Output("time-range-filter", "value"),
        Output("month-filter", "value"),
        Output("airbnb-map", "selectedData"),
        Input("reset-filters", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_dashboard(_: int):
        return [], [], [metadata["price_min"], metadata["price_max"]], "recent", metadata["default_month"], None

    @app.callback(
        Output("insight-banner", "children"),
        Output("viewing-label", "children"),
        Output("sidebar-viewing-chip", "children"),
        Output("metric-listings", "children"),
        Output("metric-price", "children"),
        Output("metric-occupancy", "children"),
        Output("metric-revenue", "children"),
        Output("airbnb-map", "figure"),
        Output("price-occupancy-scatter", "figure"),
        Output("neighborhood-bar", "figure"),
        Output("seasonality-line", "figure"),
        Input("neighborhood-filter", "value"),
        Input("room-type-filter", "value"),
        Input("price-filter", "value"),
        Input("time-range-filter", "value"),
        Input("month-filter", "value"),
        Input("airbnb-map", "selectedData"),
    )
    def update_dashboard(
        neighborhoods: list[str],
        room_types: list[str],
        price_range: list[int],
        time_range: str,
        selected_month: str,
        selected_data: dict | None,
    ):
        effective_scope, scope_label = resolve_time_scope(time_range, selected_month)
        datasets = dataset_bundle_for_scope(effective_scope)

        clean_scope_df = datasets["clean"]
        map_scope_df = datasets["map"]
        scatter_scope_df = datasets["scatter"]
        bar_scope_df = datasets["bar"]
        time_scope_df = datasets["time"]

        filtered_clean = apply_listing_filters(
            clean_scope_df, neighborhoods, room_types, price_range
        )
        filtered_map = apply_listing_filters(
            map_scope_df, neighborhoods, room_types, price_range, selected_month
        )
        filtered_scatter = apply_listing_filters(
            scatter_scope_df, neighborhoods, room_types, price_range, selected_month
        )
        filtered_bar = apply_aggregated_filters(
            bar_scope_df, neighborhoods, room_types, price_range, selected_month
        )
        filtered_time = apply_aggregated_filters(
            time_scope_df, neighborhoods, room_types, price_range
        )

        filtered_map = ensure_non_empty(filtered_map, map_scope_df)
        filtered_scatter = ensure_non_empty(filtered_scatter, scatter_scope_df)
        filtered_bar = ensure_non_empty(filtered_bar, bar_scope_df)
        filtered_time = ensure_non_empty(filtered_time, time_scope_df)

        print("map rows:", len(filtered_map))
        print("scatter rows:", len(filtered_scatter))
        print("bar rows:", len(filtered_bar))
        print("time rows:", len(filtered_time))

        selected_ids = extract_selected_ids(selected_data)
        valid_selected_ids = set(filtered_map["listing_id"])
        selected_ids = [listing_id for listing_id in selected_ids if listing_id in valid_selected_ids]

        if selected_ids:
            selected_snapshot_clean = filtered_clean[
                pd.to_datetime(filtered_clean["month_date"], errors="coerce").dt.to_period("M").eq(
                    pd.to_datetime(selected_month).to_period("M")
                )
                & filtered_clean["listing_id"].isin(selected_ids)
            ].copy()
            selected_scatter = filtered_scatter[filtered_scatter["listing_id"].isin(selected_ids)].copy()
            selected_trend_clean = filtered_clean[filtered_clean["listing_id"].isin(selected_ids)].copy()

            if selected_snapshot_clean.empty:
                selected_ids = []
                selected_snapshot_clean = filter_snapshot_month(filtered_clean, selected_month)
                selected_snapshot_clean = ensure_non_empty(selected_snapshot_clean, filtered_clean)
                selected_scatter = filtered_scatter
                selected_trend_clean = filtered_clean
        else:
            selected_snapshot_clean = filter_snapshot_month(filtered_clean, selected_month)
            selected_snapshot_clean = ensure_non_empty(selected_snapshot_clean, filtered_clean)
            selected_scatter = filtered_scatter
            selected_trend_clean = filtered_clean

        current_summary = compute_summary(selected_snapshot_clean)

        if selected_ids:
            bar_source = aggregate_bar_from_listings(selected_snapshot_clean)
            time_source = aggregate_time_from_listings(selected_trend_clean)
        else:
            bar_source = aggregate_bar_from_precomputed(filtered_bar)
            time_source = aggregate_time_from_precomputed(filtered_time)

        banner = build_banner(
            selected_month,
            int(current_summary["total_listings"]),
            selected_ids,
            neighborhoods,
            room_types,
            scope_label,
        )

        return (
            banner,
            scope_label,
            "",
            f"{current_summary['total_listings']:,}",
            format_currency(current_summary["avg_price"]),
            format_percentage(current_summary["avg_occupancy"]),
            format_currency(current_summary["avg_revenue"]),
            build_map_figure(filtered_map, selected_ids),
            build_scatter_figure(selected_scatter),
            build_bar_figure(bar_source),
            build_line_figure(time_source, selected_month),
        )


app = Dash(__name__, title=APP_TITLE, update_title="Updating dashboard...")
server = app.server
app.layout = build_layout(metadata, summary)
register_callbacks(app)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8050"))
    app.run(host="0.0.0.0", port=port, debug=False)
