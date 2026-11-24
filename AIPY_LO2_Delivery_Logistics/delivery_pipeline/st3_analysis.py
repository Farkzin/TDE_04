"""ST3 exploratory analysis: business indicators and grouped summaries (reused by ST4 and ST5)."""

import pandas as pd


def calculate_indicators(df: pd.DataFrame) -> dict:
    """Core indicators answering the ST3 business questions (volume, value, average, exception)."""
    revenue = float(df["final_delivery_cost_brl"].sum())
    extended = df["service_zone"] == "Extended"
    return {
        "valid_deliveries": int(len(df)),
        "total_revenue_brl": round(revenue, 2),
        "average_delivery_cost_brl": round(float(df["final_delivery_cost_brl"].mean()), 2),
        "largest_delivery_cost_brl": round(float(df["final_delivery_cost_brl"].max()), 2),
        "total_distance_km": round(float(df["distance_km"].sum()), 1),
        "average_minutes_per_km": round(float(df["delivery_minutes"].sum() / df["distance_km"].sum()), 2),
        "extended_share_of_deliveries_pct": round(100 * float(extended.mean()), 1),
        "extended_share_of_revenue_pct": round(
            100 * float(df.loc[extended, "final_delivery_cost_brl"].sum()) / revenue, 1),
    }


def summarize_by_zone(df: pd.DataFrame) -> pd.DataFrame:
    """ST3 grouping reused as the business summary, sorted by revenue (largest first)."""
    total_revenue = df["final_delivery_cost_brl"].sum()
    summary = (
        df.groupby("service_zone")
        .agg(
            deliveries=("delivery_id", "count"),
            total_distance_km=("distance_km", "sum"),
            total_weight_kg=("package_weight_kg", "sum"),
            revenue_brl=("final_delivery_cost_brl", "sum"),
            average_cost_brl=("final_delivery_cost_brl", "mean"),
            zone_fees_brl=("zone_fee_brl", "sum"),
            average_delivery_minutes=("delivery_minutes", "mean"),
        )
        .reset_index()
    )
    summary["revenue_share"] = summary["revenue_brl"] / total_revenue
    summary = summary.sort_values("revenue_brl", ascending=False, ignore_index=True)
    return summary.round({"total_distance_km": 1, "total_weight_kg": 2, "revenue_brl": 2,
                          "average_cost_brl": 2, "zone_fees_brl": 2, "average_delivery_minutes": 1,
                          "revenue_share": 4})


def summarize_by_district(df: pd.DataFrame) -> pd.DataFrame:
    """Secondary view: which districts generate the most revenue."""
    summary = (
        df.groupby("district")
        .agg(
            deliveries=("delivery_id", "count"),
            revenue_brl=("final_delivery_cost_brl", "sum"),
            average_distance_km=("distance_km", "mean"),
            average_cost_brl=("final_delivery_cost_brl", "mean"),
        )
        .reset_index()
        .sort_values(["revenue_brl", "deliveries"], ascending=False, ignore_index=True)
    )
    return summary.round({"revenue_brl": 2, "average_distance_km": 1, "average_cost_brl": 2})
