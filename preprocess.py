from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd


DATA_FILE = Path("listings_monthly.csv")
REQUIRED_COLUMNS = {
    "latitude",
    "longitude",
    "neighborhood",
    "room_type",
    "avg_daily_rate",
    "occupancy",
    "revenue",
    "month_date",
}


def load_data(file_path: str | Path = DATA_FILE) -> pd.DataFrame:
    """
    Load the monthly Airbnb dataset and print basic diagnostics for debugging.
    """
    file_path = resolve_input_path(file_path)
    df = pd.read_csv(file_path)

    missing_columns = REQUIRED_COLUMNS.difference(df.columns)
    if missing_columns:
        missing_display = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing_display}")

    print(f"Loaded {file_path.name}")
    print(f"Shape: {df.shape}")

    info_buffer = StringIO()
    df.info(buf=info_buffer)
    print(info_buffer.getvalue())

    return df


def resolve_input_path(file_path: str | Path) -> Path:
    """
    Resolve the requested input path while tolerating common project layouts.
    """
    candidate = Path(file_path)
    fallback_candidates = [
        candidate,
        Path(candidate.name),
        Path(__file__).resolve().parent / candidate,
        Path(__file__).resolve().parent / candidate.name,
    ]

    for path in fallback_candidates:
        if path.exists():
            return path

    return candidate


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove invalid, incomplete, and duplicate rows so the dataset is stable
    for dashboard interactions and chart rendering.
    """
    clean_df = df.copy()

    numeric_columns = ["latitude", "longitude", "avg_daily_rate", "occupancy", "revenue"]
    for column in numeric_columns:
        clean_df[column] = pd.to_numeric(clean_df[column], errors="coerce")

    required_non_null = ["avg_daily_rate", "occupancy", "revenue", "latitude", "longitude"]
    clean_df = clean_df.dropna(subset=required_non_null)

    clean_df = clean_df[
        (clean_df["avg_daily_rate"] <= 1000)
        & (clean_df["occupancy"] <= 1)
        & (clean_df["revenue"] > 0)
    ].copy()

    if "listing_id" in clean_df.columns:
        clean_df["listing_id"] = clean_df["listing_id"].astype("string").str.strip()
    else:
        clean_df["listing_id"] = pd.Series(dtype="string")

    if "neighborhood" in clean_df.columns:
        clean_df["neighborhood"] = (
            clean_df["neighborhood"].astype("string").fillna("").str.strip().replace("", "Unknown")
        )

    if "room_type" in clean_df.columns:
        clean_df["room_type"] = (
            clean_df["room_type"]
            .astype("string")
            .fillna("Unknown")
            .str.replace("_", " ", regex=False)
            .str.title()
            .str.strip()
        )

    if "property_type" in clean_df.columns:
        clean_df["property_type"] = clean_df["property_type"].astype("string").fillna("Unknown").str.strip()
    else:
        clean_df["property_type"] = "Unknown"

    clean_df = clean_df.drop_duplicates().reset_index(drop=True)
    return clean_df


def transform_data(
    df: pd.DataFrame,
    recent_months: int | None = None,
) -> pd.DataFrame:
    """
    Convert date fields, sort chronologically, and optionally keep only the
    most recent valid months for a lighter-weight dashboard dataset.
    """
    transformed_df = df.copy()
    transformed_df["month_date"] = pd.to_datetime(transformed_df["month_date"], errors="coerce")
    transformed_df = transformed_df.dropna(subset=["month_date"]).sort_values("month_date")

    transformed_df = transformed_df[
        transformed_df["latitude"].between(40.45, 40.95)
        & transformed_df["longitude"].between(-74.30, -73.65)
    ].copy()

    if recent_months is not None:
        unique_months = (
            transformed_df["month_date"]
            .drop_duplicates()
            .sort_values()
            .tail(recent_months)
        )
        transformed_df = transformed_df[transformed_df["month_date"].isin(unique_months)]

    transformed_df["month_key"] = transformed_df["month_date"].dt.strftime("%Y-%m-%d")
    transformed_df["month_label"] = transformed_df["month_date"].dt.strftime("%b %Y")
    transformed_df["occupancy_pct"] = (transformed_df["occupancy"] * 100).clip(lower=0, upper=100)
    transformed_df = transformed_df.reset_index(drop=True)
    return transformed_df


def prepare_visualization_data(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build separate datasets optimized for the dashboard's visual components.
    """
    df_map = df.loc[
        :,
        [
            "listing_id",
            "latitude",
            "longitude",
            "neighborhood",
            "room_type",
            "property_type",
            "avg_daily_rate",
            "revenue",
            "occupancy",
            "occupancy_pct",
            "month_date",
            "month_key",
            "month_label",
        ],
    ].copy()

    df_scatter = df.loc[
        :,
        [
            "listing_id",
            "avg_daily_rate",
            "occupancy",
            "occupancy_pct",
            "room_type",
            "neighborhood",
            "property_type",
            "revenue",
            "month_date",
            "month_key",
            "month_label",
        ],
    ].copy()

    df_bar = (
        df.groupby(["month_date", "month_key", "month_label", "neighborhood", "room_type"], as_index=False)
        .agg(
            avg_daily_rate=("avg_daily_rate", "mean"),
            avg_revenue=("revenue", "mean"),
            avg_occupancy=("occupancy", "mean"),
            avg_occupancy_pct=("occupancy_pct", "mean"),
            listing_count=("listing_id", "nunique"),
        )
        .sort_values(["month_date", "avg_daily_rate"], ascending=[True, False])
        .reset_index(drop=True)
    )

    df_time = (
        df.groupby(["month_date", "month_key", "month_label", "neighborhood", "room_type"], as_index=False)
        .agg(
            avg_daily_rate=("avg_daily_rate", "mean"),
            avg_occupancy=("occupancy", "mean"),
            avg_revenue=("revenue", "mean"),
            avg_occupancy_pct=("occupancy_pct", "mean"),
            listing_count=("listing_id", "nunique"),
        )
        .sort_values("month_date")
        .reset_index(drop=True)
    )

    return df_map, df_scatter, df_bar, df_time


def compute_summary(df: pd.DataFrame) -> dict:
    """
    Compute dashboard KPI values from the cleaned dataset.
    """
    if df.empty:
        return {
            "total_listings": 0,
            "avg_price": 0.0,
            "avg_occupancy": 0.0,
            "avg_revenue": 0.0,
        }

    return {
        "total_listings": int(df["listing_id"].nunique()),
        "avg_price": float(df["avg_daily_rate"].mean()),
        "avg_occupancy": float(df["occupancy"].mean()),
        "avg_revenue": float(df["revenue"].mean()),
    }


def run_pipeline(
    file_path: str | Path = DATA_FILE,
    recent_months: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    End-to-end preprocessing pipeline for the Airbnb visualization dashboard.

    Returns:
        df_clean, df_map, df_scatter, df_bar, df_time
    """
    df_raw = load_data(file_path)
    df_clean = clean_data(df_raw)
    df_clean = transform_data(df_clean, recent_months=recent_months)
    df_map, df_scatter, df_bar, df_time = prepare_visualization_data(df_clean)
    return df_clean, df_map, df_scatter, df_bar, df_time


def print_pipeline_summary(
    df_clean: pd.DataFrame,
    df_map: pd.DataFrame,
    df_scatter: pd.DataFrame,
    df_bar: pd.DataFrame,
    df_time: pd.DataFrame,
) -> None:
    """
    Print concise output shapes so the preprocessing results are easy to verify.
    """
    print("Pipeline complete")
    print(f"df_clean:   {df_clean.shape}")
    print(f"df_map:     {df_map.shape}")
    print(f"df_scatter: {df_scatter.shape}")
    print(f"df_bar:     {df_bar.shape}")
    print(f"df_time:    {df_time.shape}")


if __name__ == "__main__":
    df_clean, df_map, df_scatter, df_bar, df_time = run_pipeline()
    print_pipeline_summary(df_clean, df_map, df_scatter, df_bar, df_time)
