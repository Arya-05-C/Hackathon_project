import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ==========================================================
# FILES
# ==========================================================

INVENTORY_FILE = "./outputs/inventory_snapshot.csv"
EDA_FILE = "./outputs/eda_sku_features.csv"
FORECAST_7_FILE = "./outputs/forecast_7_days.csv"
FORECAST_30_FILE = "./outputs/forecast_30_days.csv"

OUTPUT_FILE = "./outputs/inventory_gaps.csv"

# ==========================================================
# LOAD DATA
# ==========================================================

print("Loading data...")

inventory = pd.read_csv(INVENTORY_FILE)
eda = pd.read_csv(EDA_FILE)

forecast7 = pd.read_csv(FORECAST_7_FILE)
forecast30 = pd.read_csv(FORECAST_30_FILE)

# ==========================================================
# AGGREGATE FORECASTS
# ==========================================================

forecast7_agg = (
    forecast7
    .groupby("item_id", as_index=False)["forecast"]
    .sum()
    .rename(columns={"forecast": "forecast_7d"})
)

forecast30_agg = (
    forecast30
    .groupby("item_id", as_index=False)["forecast"]
    .sum()
    .rename(columns={"forecast": "forecast_30d"})
)

# ==========================================================
# MERGE
# ==========================================================

df = (
    inventory
    .merge(
        forecast7_agg,
        on="item_id",
        how="left"
    )
    .merge(
        forecast30_agg,
        on="item_id",
        how="left"
    )
)

risk_cols = [
    "item_id",
    "avg_daily_demand",
    "abc_class",
    "xyz_class",
    "abc_xyz",
    "safety_stock_95",
    "reorder_point_lt_med",
    "stockout_risk_score",
    "procurement_risk_tier"
]

df = df.merge(
    eda[risk_cols],
    on="item_id",
    how="left",
    suffixes=("", "_eda")
)

# ==========================================================
# CLEAN NULLS
# ==========================================================

df["forecast_7d"] = df["forecast_7d"].fillna(0)
df["forecast_30d"] = df["forecast_30d"].fillna(0)

# ==========================================================
# GAP CALCULATIONS
# ==========================================================

df["gap_7d"] = (
    df["forecast_7d"]
    + df["safety_stock_95"]
    - df["available_inventory"]
)

df["gap_30d"] = (
    df["forecast_30d"]
    + df["safety_stock_95"]
    - df["available_inventory"]
)

# ==========================================================
# SHORTAGE QUANTITY
# ==========================================================

df["shortage_quantity"] = (
    df["gap_30d"]
    .clip(lower=0)
    .round()
    .astype(int)
)

# ==========================================================
# FORECAST DAILY RATE
# ==========================================================

df["forecast_daily_rate"] = (
    df["forecast_30d"] / 30
)

df["forecast_daily_rate"] = np.where(
    df["forecast_daily_rate"] <= 0,
    0.01,
    df["forecast_daily_rate"]
)

# ==========================================================
# DAYS UNTIL STOCKOUT
# ==========================================================

df["days_until_stockout"] = (
    df["available_inventory"]
    /
    df["forecast_daily_rate"]
)

df["days_until_stockout"] = (
    df["days_until_stockout"]
    .round(1)
)

# ==========================================================
# PROJECTED STOCKOUT DATE
# ==========================================================

today = pd.Timestamp.today().normalize()

df["projected_stockout_date"] = (
    today
    +
    pd.to_timedelta(
        df["days_until_stockout"],
        unit="D"
    )
)

df["projected_stockout_date"] = (
    pd.to_datetime(
        df["projected_stockout_date"]
    )
    .dt.date
)

# ==========================================================
# GAP SCORE
# ==========================================================

df["gap_ratio"] = (
    df["shortage_quantity"]
    /
    (df["forecast_30d"] + 1)
)

df["gap_score"] = (
    df["gap_ratio"]
    * 100
).clip(0, 100)

# ==========================================================
# ABC SCORE
# ==========================================================

abc_map = {
    "A": 100,
    "B": 70,
    "C": 40
}

df["abc_score"] = (
    df["abc_class"]
    .map(abc_map)
    .fillna(50)
)

# ==========================================================
# XYZ SCORE
# ==========================================================

xyz_map = {
    "X": 30,
    "Y": 60,
    "Z": 100
}

df["xyz_score"] = (
    df["xyz_class"]
    .map(xyz_map)
    .fillna(50)
)

# ==========================================================
# INVENTORY RISK SCORE
# ==========================================================

df["inventory_risk_score"] = (
    0.40 * df["gap_score"]
    +
    0.25 * df["abc_score"]
    +
    0.20 * df["xyz_score"]
    +
    0.15 * df["stockout_risk_score"]
)

df["inventory_risk_score"] = (
    df["inventory_risk_score"]
    .clip(0, 100)
    .round(1)
)

# ==========================================================
# PROCUREMENT PRIORITY
# ==========================================================

conditions = [
    df["inventory_risk_score"] >= 80,
    df["inventory_risk_score"] >= 60,
    df["inventory_risk_score"] >= 40
]

choices = [
    "Critical",
    "High",
    "Medium"
]

df["procurement_priority"] = np.select(
    conditions,
    choices,
    default="Low"
)

# ==========================================================
# PROCUREMENT ALERT
#
# Inventory warning
# ==========================================================

df["procurement_alert"] = np.where(
    df["available_inventory"]
    <=
    df["reorder_point_lt_med"],
    "YES",
    "NO"
)

# ==========================================================
# PROCUREMENT ACTION
#
# Actual replenishment recommendation
# Much stricter than alert
# ==========================================================

df["procurement_trigger"] = np.where(
    (
        (
            (df["gap_30d"] > 0)
            &
            (df["days_until_stockout"] < 21)
        )
        |
        (
            df["inventory_risk_score"] >= 80
        )
    ),
    "YES",
    "NO"
)

# ==========================================================
# PROCUREMENT CATEGORY
# ==========================================================

conditions = [
    df["days_until_stockout"] <= 7,

    (
        (df["days_until_stockout"] > 7)
        &
        (df["days_until_stockout"] <= 14)
    ),

    (
        (df["days_until_stockout"] > 14)
        &
        (df["days_until_stockout"] <= 30)
    )
]

choices = [
    "Emergency",
    "Urgent",
    "Planned"
]

df["procurement_category"] = np.select(
    conditions,
    choices,
    default="Monitor"
)

# ==========================================================
# PROCUREMENT REASON
# ==========================================================

def get_procurement_reason(row):

    reasons = []

    if row["gap_30d"] > 0:
        reasons.append("Forecast Shortage")

    if row["available_inventory"] <= row["reorder_point_lt_med"]:
        reasons.append("Below Reorder Point")

    if row["days_until_stockout"] < 14:
        reasons.append("Impending Stockout")

    if row["inventory_risk_score"] >= 80:
        reasons.append("High Risk SKU")

    if not reasons:
        reasons.append("Inventory Healthy")

    return "; ".join(reasons)


df["procurement_reason"] = df.apply(
    get_procurement_reason,
    axis=1
)

# ==========================================================
# RECOMMENDED PO QUANTITY
# ==========================================================

df["recommended_po_qty"] = (
    df["shortage_quantity"]
    +
    (0.25 * df["forecast_30d"])
)

df["recommended_po_qty"] = (
    df["recommended_po_qty"]
    .round()
    .astype(int)
)

# ==========================================================
# OUTPUT
# ==========================================================

output_cols = [
    "item_id",

    "available_inventory",

    "forecast_7d",
    "forecast_30d",

    "gap_7d",
    "gap_30d",

    "shortage_quantity",

    "days_until_stockout",
    "projected_stockout_date",

    "inventory_risk_score",

    "procurement_priority",

    "procurement_alert",
    "procurement_trigger",

    "procurement_category",
    "procurement_reason",

    "recommended_po_qty"
]

output = df[output_cols]

output.to_csv(
    OUTPUT_FILE,
    index=False
)

# ==========================================================
# SUMMARY
# ==========================================================
print("\nInventory Gap Analysis Complete")
print("=" * 60)

print("\nProcurement Priority Distribution")
print(
    output["procurement_priority"]
    .value_counts()
)

print("\nProcurement Alerts")
print(
    output["procurement_alert"]
    .value_counts()
)

print("\nProcurement Triggers")
print(
    output["procurement_trigger"]
    .value_counts()
)

print("\nProcurement Categories")
print(
    output["procurement_category"]
    .value_counts()
)

print("\nTotal Shortage Quantity")
print(
    int(
        output["shortage_quantity"]
        .sum()
    )
)

print("\nTotal Recommended PO Qty")
print(
    int(
        output["recommended_po_qty"]
        .sum()
    )
)

print(f"\nSaved: {OUTPUT_FILE}")