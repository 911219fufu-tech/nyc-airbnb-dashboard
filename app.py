import os
from functools import lru_cache

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html


DATA_FILE = "listings_monthly.csv"
APP_TITLE = "NYC Airbnb Performance Dashboard"
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


# ---------- Data ----------


@lru_cache(maxsize=1)
def load_data() -> tuple[pd.DataFrame, dict]:
    dtype_map = {
        "listing_id": "string",
        "host_id": "string",
        "listing_type": "string",
        "room_type": "string",
        "country": "string",
        "currency": "string",
        "property_type": "string",
        "neighborhood": "string",
        "superhost": "string",
        "active": "string",
    }
    numeric_columns = [
        "latitude",
        "longitude",
        "guests",
        "bedrooms",
        "beds",
        "baths",
        "num_reviews",
        "star_rating",
        "available_days",
        "unavailable_days",
        "occupancy",
        "avg_daily_rate",
        "native_avg_daily_rate",
        "revenue",
        "native_revenue",
        "booking_lead_time_avg",
        "length_of_stay_avg",
        "booked_rate_avg",
        "revpar",
        "native_revpar",
    ]

    df = pd.read_csv(DATA_FILE, parse_dates=["month_date"], dtype=dtype_map)

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df["listing_id"] = df["listing_id"].fillna("").str.strip()
    df["neighborhood"] = df["neighborhood"].fillna("").str.strip().replace("", "Unknown")
    df["room_type"] = (
        df["room_type"].fillna("Unknown").str.replace("_", " ").str.title().str.strip()
    )
    df["listing_type"] = df["listing_type"].fillna("Unknown").str.strip()
    df["property_type"] = df["property_type"].fillna("Unknown").str.strip()
    df["month_key"] = df["month_date"].dt.strftime("%Y-%m-%d")
    df["month_label"] = df["month_date"].dt.strftime("%b %Y")
    df["occupancy_pct"] = (df["occupancy"].fillna(0) * 100).clip(lower=0, upper=100)
    df["avg_daily_rate"] = df["avg_daily_rate"].fillna(0)
    df["revenue"] = df["revenue"].fillna(0)
    df["revpar"] = df["revpar"].fillna(0)

    # Keep the spatial extent limited to NYC bounds.
    df = df[
        df["latitude"].between(40.45, 40.95)
        & df["longitude"].between(-74.30, -73.65)
    ].copy()

    month_counts = df.groupby("month_key")["listing_id"].nunique().sort_index()
    max_month_count = month_counts.max()
    stable_months = month_counts[month_counts >= max_month_count * 0.9]
    default_month = stable_months.index.max() if not stable_months.empty else month_counts.index.max()

    price_min = int(max(0, (df["avg_daily_rate"].min() // 10) * 10))
    price_max = int(((df["avg_daily_rate"].max() // 50) + 1) * 50)
    price_marks = build_price_marks(price_min, price_max)

    month_lookup = (
        df[["month_key", "month_label"]]
        .drop_duplicates()
        .sort_values("month_key")
        .reset_index(drop=True)
    )

    metadata = {
        "default_month": default_month,
        "default_month_label": month_lookup.loc[
            month_lookup["month_key"] == default_month, "month_label"
        ].iat[0],
        "month_options": [
            {"label": row.month_label, "value": row.month_key}
            for row in month_lookup.itertuples(index=False)
        ],
        "month_coverage": f"{month_lookup.iloc[0]['month_label']} to {month_lookup.iloc[-1]['month_label']}",
        "neighborhood_options": [
            {"label": value, "value": value}
            for value in sorted(df["neighborhood"].dropna().unique(), key=neighborhood_sort_key)
        ],
        "room_type_options": [
            {"label": value, "value": value}
            for value in sorted(df["room_type"].dropna().unique())
        ],
        "price_min": price_min,
        "price_max": price_max,
        "price_marks": price_marks,
        "latest_month": month_lookup.iloc[-1]["month_label"],
    }
    return df, metadata


def build_price_marks(price_min: int, price_max: int) -> dict:
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


def format_price_mark(value: int) -> str:
    if value >= 1000:
        if value % 1000 == 0:
            return f"${value // 1000}k"
        if value % 500 == 0:
            return f"${value / 1000:.1f}k"
        return f"${value:,}"
    return f"${value}"


def neighborhood_sort_key(value: str) -> tuple[int, str]:
    if value == "Unknown":
        return (1, value)
    return (0, value)


def apply_filters(
    df: pd.DataFrame,
    neighborhoods: list[str] | None,
    room_types: list[str] | None,
    price_range: list[int] | None,
) -> pd.DataFrame:
    filtered = df
    if neighborhoods:
        filtered = filtered[filtered["neighborhood"].isin(neighborhoods)]
    if room_types:
        filtered = filtered[filtered["room_type"].isin(room_types)]
    if price_range and len(price_range) == 2:
        filtered = filtered[
            filtered["avg_daily_rate"].between(price_range[0], price_range[1], inclusive="both")
        ]
    return filtered.copy()


def extract_selected_ids(selected_data: dict | None) -> list[str]:
    if not selected_data or not selected_data.get("points"):
        return []

    selected_ids: list[str] = []
    for point in selected_data["points"]:
        custom_data = point.get("customdata") or []
        if custom_data:
            selected_ids.append(str(custom_data[0]))
    return list(dict.fromkeys(selected_ids))


def summarize_snapshot(snapshot_df: pd.DataFrame) -> dict:
    listings = int(snapshot_df["listing_id"].nunique()) if not snapshot_df.empty else 0
    return {
        "listings": listings,
        "price": float(snapshot_df["avg_daily_rate"].mean()) if listings else 0.0,
        "occupancy": float(snapshot_df["occupancy_pct"].mean()) if listings else 0.0,
        "revenue": float(snapshot_df["revenue"].mean()) if listings else 0.0,
    }


# ---------- Layout ----------


def metric_card(label: str, value_id: str) -> html.Div:
    return html.Div(
        className="metric-card",
        children=[
            html.Div(label, className="metric-label"),
            html.Div(id=value_id, className="metric-value"),
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


def build_layout(metadata: dict) -> html.Div:
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
                                    html.Div("Data Coverage", className="header-chip-label"),
                                    html.Div(metadata["month_coverage"], className="header-chip-value"),
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
                                        className="sidebar-chip-row",
                                        children=[
                                            html.Div(
                                                f"Latest complete month: {metadata['default_month_label']}",
                                                className="sidebar-chip",
                                            ),
                                            html.Div(
                                                f"Latest available month: {metadata['latest_month']}",
                                                className="sidebar-chip subdued",
                                            ),
                                        ],
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
                                    html.Div(id="insight-banner", className="insight-banner"),
                                    html.Div(
                                        className="metric-strip",
                                        children=[
                                            metric_card("Listings in View", "metric-listings"),
                                            metric_card("Average Daily Rate", "metric-price"),
                                            metric_card("Average Occupancy", "metric-occupancy"),
                                            metric_card("Average Monthly Revenue", "metric-revenue"),
                                        ],
                                    ),
                                    dcc.Loading(
                                        type="circle",
                                        color=LINE_COLOR,
                                        className="dashboard-loading",
                                        children=html.Div(
                                            className="content-grid",
                                            children=[
                                                chart_card(
                                                    "Price and Revenue Map",
                                                    "Bubble size reflects revenue and color reflects average daily rate for the selected month.",
                                                    "airbnb-map",
                                                    "span-6 map-card",
                                                ),
                                                chart_card(
                                                    "Price vs Occupancy",
                                                    "Use the upper-left and lower-right quadrants to spot underpriced or overpriced listings.",
                                                    "price-occupancy-scatter",
                                                    "span-3 medium-card",
                                                ),
                                                chart_card(
                                                    "Neighborhood Demand Ranking",
                                                    "Compare ZIP codes by occupancy to surface the strongest demand pockets.",
                                                    "neighborhood-bar",
                                                    "span-3 medium-card",
                                                ),
                                                chart_card(
                                                    "Seasonal Revenue Trend",
                                                    "Track how the current filtered market moves over time, with the selected month highlighted.",
                                                    "seasonality-line",
                                                    "span-12 full-card",
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


# ---------- Figures ----------


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


def build_map_figure(snapshot_df: pd.DataFrame, selected_ids: list[str]) -> go.Figure:
    if snapshot_df.empty:
        return empty_figure("No listings match the current filters.", 480)

    figure_df = snapshot_df.copy()
    revenue_max = max(figure_df["revenue"].max(), 1)
    sizeref = (2.0 * revenue_max) / (28**2)
    color_min = float(figure_df["avg_daily_rate"].min())
    color_max = float(figure_df["avg_daily_rate"].quantile(0.98))
    if color_max <= color_min:
        color_max = color_min + 1
    selected_set = set(selected_ids)
    selected_points = [
        idx for idx, listing_id in enumerate(figure_df["listing_id"]) if listing_id in selected_set
    ]

    fig = go.Figure(
        go.Scattermapbox(
            lat=figure_df["latitude"],
            lon=figure_df["longitude"],
            mode="markers",
            customdata=list(
                zip(
                    figure_df["listing_id"],
                    figure_df["neighborhood"],
                    figure_df["room_type"],
                    figure_df["avg_daily_rate"].round(0),
                    figure_df["occupancy_pct"].round(1),
                    figure_df["revenue"].round(0),
                    figure_df["property_type"],
                )
            ),
            marker={
                "size": figure_df["revenue"].clip(lower=1),
                "sizemode": "area",
                "sizeref": sizeref,
                "sizemin": 6,
                "color": figure_df["avg_daily_rate"],
                "colorscale": PRICE_SCALE,
                "cmin": color_min,
                "cmax": color_max,
                "opacity": 0.86,
                "line": {"width": 0},
                "colorbar": {
                    "title": {"text": "Avg Daily Rate", "side": "top"},
                    "tickprefix": "$",
                    "thickness": 12,
                    "len": 0.62,
                    "x": 0.98,
                    "outlinewidth": 0,
                },
            },
            selectedpoints=selected_points or None,
            selected={"marker": {"opacity": 0.98, "line": {"color": "#ffffff", "width": 1.4}}},
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
        **base_layout(480),
        mapbox={
            "style": "carto-positron",
            "zoom": 10.25,
            "center": {
                "lat": float(figure_df["latitude"].mean()),
                "lon": float(figure_df["longitude"].mean()),
            },
        },
        dragmode="select",
        uirevision="nyc-airbnb-map",
        clickmode="event+select",
    )
    return fig


def build_scatter_figure(snapshot_df: pd.DataFrame) -> go.Figure:
    if snapshot_df.empty:
        return empty_figure("No listing points to compare for this month.", 480)

    figure_df = snapshot_df.copy().sort_values("avg_daily_rate")
    fig = go.Figure()

    for room_type, group in figure_df.groupby("room_type", dropna=False):
        fig.add_trace(
            go.Scatter(
                x=group["avg_daily_rate"],
                y=group["occupancy_pct"],
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
                    "Occupancy: %{y:.1f}%<br>"
                    "Revenue: $%{customdata[2]:,.0f}<br>"
                    "Property: %{customdata[3]}<extra></extra>"
                ),
            )
        )

    price_mid = figure_df["avg_daily_rate"].median()
    occupancy_mid = figure_df["occupancy_pct"].median()
    fig.add_vline(x=price_mid, line_dash="dot", line_color="rgba(23,32,51,0.25)")
    fig.add_hline(y=occupancy_mid, line_dash="dot", line_color="rgba(23,32,51,0.25)")
    fig.add_annotation(
        x=price_mid,
        y=101,
        xref="x",
        yref="y",
        text="Median price",
        showarrow=False,
        font={"size": 11, "color": MUTED_COLOR},
    )
    fig.add_annotation(
        x=max(figure_df["avg_daily_rate"].max() * 0.97, price_mid),
        y=max(occupancy_mid * 0.4, 10),
        text="High price,<br>soft demand",
        showarrow=False,
        align="right",
        font={"size": 11, "color": MUTED_COLOR},
    )

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
        ticksuffix="%",
        range=[0, 105],
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
    )
    return fig


def build_bar_figure(snapshot_df: pd.DataFrame) -> go.Figure:
    if snapshot_df.empty:
        return empty_figure("No neighborhood comparison is available for this view.", 480)

    neighborhood_df = (
        snapshot_df.groupby("neighborhood", as_index=False)
        .agg(
            occupancy_pct=("occupancy_pct", "mean"),
            avg_daily_rate=("avg_daily_rate", "mean"),
            revenue=("revenue", "mean"),
            listings=("listing_id", "nunique"),
        )
        .sort_values(["occupancy_pct", "listings"], ascending=[False, False])
        .head(12)
        .sort_values("occupancy_pct", ascending=True)
    )

    fig = go.Figure(
        go.Bar(
            x=neighborhood_df["occupancy_pct"],
            y=neighborhood_df["neighborhood"],
            orientation="h",
            marker={"color": LINE_COLOR, "opacity": 0.9},
            text=[f"{value:.0f}%" for value in neighborhood_df["occupancy_pct"]],
            textposition="outside",
            customdata=list(
                zip(
                    neighborhood_df["avg_daily_rate"].round(0),
                    neighborhood_df["revenue"].round(0),
                    neighborhood_df["listings"],
                )
            ),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Occupancy: %{x:.1f}%<br>"
                "Avg Daily Rate: $%{customdata[0]:,.0f}<br>"
                "Avg Revenue: $%{customdata[1]:,.0f}<br>"
                "Listings: %{customdata[2]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        **base_layout(480),
        showlegend=False,
    )
    fig.update_xaxes(
        title="Average Occupancy",
        ticksuffix="%",
        range=[0, max(100, neighborhood_df["occupancy_pct"].max() * 1.12)],
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
    )
    fig.update_yaxes(title=None, showgrid=False, automargin=True)
    return fig


def build_line_figure(trend_df: pd.DataFrame, selected_month: str) -> go.Figure:
    if trend_df.empty:
        return empty_figure("No seasonal pattern is available after filtering.", 420)

    monthly = (
        trend_df.groupby(["month_date", "month_label"], as_index=False)
        .agg(
            revenue=("revenue", "mean"),
            occupancy_pct=("occupancy_pct", "mean"),
            avg_daily_rate=("avg_daily_rate", "mean"),
            listings=("listing_id", "nunique"),
        )
        .sort_values("month_date")
    )

    fig = go.Figure(
        go.Scatter(
            x=monthly["month_date"],
            y=monthly["revenue"],
            mode="lines+markers",
            line={"color": LINE_COLOR, "width": 3, "shape": "spline", "smoothing": 0.75},
            marker={"size": 7, "color": "#ffffff", "line": {"color": LINE_COLOR, "width": 2}},
            customdata=list(
                zip(
                    monthly["occupancy_pct"].round(1),
                    monthly["avg_daily_rate"].round(0),
                    monthly["listings"],
                    monthly["month_label"],
                )
            ),
            hovertemplate=(
                "<b>%{customdata[3]}</b><br>"
                "Avg Revenue: $%{y:,.0f}<br>"
                "Occupancy: %{customdata[0]:.1f}%<br>"
                "Avg Daily Rate: $%{customdata[1]:,.0f}<br>"
                "Listings: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    selected_month_ts = pd.to_datetime(selected_month)
    selected_row = monthly.loc[monthly["month_date"] == selected_month_ts]
    if not selected_row.empty:
        fig.add_vline(x=selected_month_ts, line_dash="dot", line_color="rgba(31,79,214,0.32)")
        fig.add_trace(
            go.Scatter(
                x=selected_row["month_date"],
                y=selected_row["revenue"],
                mode="markers",
                marker={"size": 13, "color": LINE_COLOR, "line": {"color": "#ffffff", "width": 2}},
                name="Selected month",
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.update_layout(
        **base_layout(420),
        hovermode="x unified",
        showlegend=False,
    )
    fig.update_xaxes(
        title=None,
        showgrid=False,
        tickformat="%b\n%Y",
        dtick="M3",
    )
    fig.update_yaxes(
        title="Average Monthly Revenue",
        tickprefix="$",
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
    )
    return fig


def build_banner(
    selected_month: str,
    snapshot_rows: int,
    selected_ids: list[str],
    neighborhoods: list[str] | None,
    room_types: list[str] | None,
) -> list[html.Div]:
    month_label = pd.to_datetime(selected_month).strftime("%B %Y")
    filters_active = bool(neighborhoods or room_types)
    scope_text = "Focused view" if filters_active else "Market overview"
    selection_text = (
        f"Map selection: {len(selected_ids)} listings"
        if selected_ids
        else "Map selection: none"
    )
    return [
        html.Div(
            className="banner-primary",
            children=[
                html.Div(scope_text, className="banner-label"),
                html.Div(
                    f"{month_label} snapshot with {snapshot_rows:,} listing-month records in view",
                    className="banner-value",
                ),
            ],
        ),
        html.Div(selection_text, className="banner-secondary"),
    ]


# ---------- Callbacks ----------


def register_callbacks(app: Dash, df: pd.DataFrame, metadata: dict) -> None:
    @app.callback(
        Output("neighborhood-filter", "value"),
        Output("room-type-filter", "value"),
        Output("price-filter", "value"),
        Output("month-filter", "value"),
        Output("airbnb-map", "selectedData"),
        Input("reset-filters", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_dashboard(_: int):
        return [], [], [metadata["price_min"], metadata["price_max"]], metadata["default_month"], None

    @app.callback(
        Output("insight-banner", "children"),
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
        Input("month-filter", "value"),
        Input("airbnb-map", "selectedData"),
    )
    def update_dashboard(
        neighborhoods: list[str],
        room_types: list[str],
        price_range: list[int],
        selected_month: str,
        selected_data: dict | None,
    ):
        base_filtered = apply_filters(df, neighborhoods, room_types, price_range)
        snapshot_df = base_filtered[base_filtered["month_key"] == selected_month].copy()

        selected_ids = extract_selected_ids(selected_data)
        if selected_ids:
            selected_snapshot_df = snapshot_df[snapshot_df["listing_id"].isin(selected_ids)].copy()
            if selected_snapshot_df.empty:
                selected_ids = []
                selected_snapshot_df = snapshot_df
        else:
            selected_snapshot_df = snapshot_df

        trend_df = (
            base_filtered[base_filtered["listing_id"].isin(selected_ids)].copy()
            if selected_ids
            else base_filtered.copy()
        )

        summary = summarize_snapshot(selected_snapshot_df)
        banner = build_banner(
            selected_month,
            len(selected_snapshot_df),
            selected_ids,
            neighborhoods,
            room_types,
        )

        return (
            banner,
            f"{summary['listings']:,}",
            f"${summary['price']:,.0f}",
            f"{summary['occupancy']:.1f}%",
            f"${summary['revenue']:,.0f}",
            build_map_figure(snapshot_df, selected_ids),
            build_scatter_figure(selected_snapshot_df),
            build_bar_figure(selected_snapshot_df),
            build_line_figure(trend_df, selected_month),
        )


df, metadata = load_data()
app = Dash(__name__, title=APP_TITLE, update_title="Updating dashboard...")
server = app.server
app.layout = build_layout(metadata)
register_callbacks(app, df, metadata)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8050"))
    app.run(host="0.0.0.0", port=port, debug=False)
