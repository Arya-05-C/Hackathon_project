import pandas as pd
import numpy as np

# ==========================================================
# CONFIG
# ==========================================================

EDA_FILE = "./outputs/eda_sku_features.csv"
OUTPUT_FILE = "./outputs/inventory_snapshot.csv"

RANDOM_SEED = 42

np.random.seed(RANDOM_SEED)

# ==========================================================
# LOAD DATA
# ==========================================================

print("Loading EDA data...")

eda = pd.read_csv(EDA_FILE)

print(f"Loaded {len(eda)} SKUs")

# ==========================================================
# COVERAGE DAYS MAPPING
# ==========================================================

coverage_lookup = {
    "AX": 30,
    "AY": 25,
    "AZ": 20,
    "BX": 25,
    "BY": 20,
    "BZ": 15,
    "CX": 15,
    "CY": 10,
    "CZ": 7
}

eda["target_coverage_days"] = (
    eda["abc_xyz"]
    .map(coverage_lookup)
    .fillna(15)
)

# ==========================================================
# BASE INVENTORY
# ==========================================================

eda["base_inventory"] = (
    eda["avg_daily_demand"]
    * eda["target_coverage_days"]
)

# ==========================================================
# ADD SAFETY STOCK
# ==========================================================

eda["current_inventory"] = (
    eda["base_inventory"]
    + (0.5 * eda["safety_stock_95"])
)

# ==========================================================
# NATURAL VARIATION
# ==========================================================

eda["current_inventory"] *= np.random.uniform(
    0.85,
    1.15,
    size=len(eda)
)

# ==========================================================
# CREATE REALISTIC SHORTAGES
#
# 70% Healthy
# 20% Low Stock
# 10% Critical
# ==========================================================

n = len(eda)

critical_count = int(n * 0.10)
low_count = int(n * 0.20)

all_idx = np.arange(n)

critical_idx = np.random.choice(
    all_idx,
    critical_count,
    replace=False
)

remaining = np.setdiff1d(
    all_idx,
    critical_idx
)

low_idx = np.random.choice(
    remaining,
    low_count,
    replace=False
)

# Severe stress
eda.loc[critical_idx, "current_inventory"] *= np.random.uniform(
    0.15,
    0.40,
    size=len(critical_idx)
)

# Moderate stress
eda.loc[low_idx, "current_inventory"] *= np.random.uniform(
    0.40,
    0.70,
    size=len(low_idx)
)

# ==========================================================
# ROUND INVENTORY
# ==========================================================

eda["current_inventory"] = (
    eda["current_inventory"]
    .clip(lower=0)
    .round()
    .astype(int)
)

# ==========================================================
# RESERVED INVENTORY
# ==========================================================

eda["reserved_inventory"] = (
    eda["current_inventory"]
    *
    np.random.uniform(
        0.05,
        0.15,
        size=len(eda)
    )
)

eda["reserved_inventory"] = (
    eda["reserved_inventory"]
    .round()
    .astype(int)
)

# ==========================================================
# AVAILABLE INVENTORY
# ==========================================================

eda["available_inventory"] = (
    eda["current_inventory"]
    - eda["reserved_inventory"]
)

eda["available_inventory"] = (
    eda["available_inventory"]
    .clip(lower=0)
)

# ==========================================================
# DAYS OF COVER
# ==========================================================

eda["days_of_cover"] = np.where(
    eda["avg_daily_demand"] > 0,
    eda["available_inventory"]
    / eda["avg_daily_demand"],
    999
)

eda["days_of_cover"] = (
    eda["days_of_cover"]
    .round(1)
)

# ==========================================================
# INVENTORY VALUE
# ==========================================================

eda["inventory_value"] = (
    eda["available_inventory"]
    * eda["mean_price"]
)

eda["inventory_value"] = (
    eda["inventory_value"]
    .round(2)
)

# ==========================================================
# INVENTORY HEALTH SCORE
# ==========================================================

coverage_score = np.minimum(
    eda["days_of_cover"] / 30,
    1
)

stock_score = np.minimum(
    eda["available_inventory"]
    /
    np.maximum(
        eda["reorder_point_lt_med"],
        1
    ),
    1.5
)

eda["inventory_health"] = (
    (
        0.6 * coverage_score
        +
        0.4 * (stock_score / 1.5)
    )
    * 100
)

eda["inventory_health"] = (
    eda["inventory_health"]
    .clip(0, 100)
    .round(1)
)

# ==========================================================
# INVENTORY STATUS
# ==========================================================

conditions = [
    eda["available_inventory"]
    <= eda["safety_stock_95"],

    (
        (eda["available_inventory"] > eda["safety_stock_95"])
        &
        (
            eda["available_inventory"]
            <= eda["reorder_point_lt_med"]
        )
    ),

    eda["inventory_health"] >= 80
]

choices = [
    "Critical",
    "Low Stock",
    "Healthy"
]

eda["inventory_status"] = np.select(
    conditions,
    choices,
    default="Monitor"
)

# ==========================================================
# FINAL OUTPUT
# ==========================================================

output_cols = [
    "item_id",
    "abc_class",
    "xyz_class",
    "abc_xyz",
    "avg_daily_demand",
    "safety_stock_95",
    "reorder_point_lt_med",
    "procurement_risk_tier",
    "stockout_risk_score",
    "target_coverage_days",
    "current_inventory",
    "reserved_inventory",
    "available_inventory",
    "days_of_cover",
    "inventory_value",
    "inventory_health",
    "inventory_status"
]

inventory_snapshot = eda[output_cols]

inventory_snapshot.to_csv(
    OUTPUT_FILE,
    index=False
)

# ==========================================================
# SUMMARY
# ==========================================================

print("\nInventory Snapshot Generated")
print("=" * 60)

print(
    inventory_snapshot[
        "inventory_status"
    ]
    .value_counts()
)

print("\nAverage Cover Days:")
print(
    round(
        inventory_snapshot[
            "days_of_cover"
        ].mean(),
        2
    )
)

print("\nTotal Inventory Value:")
print(
    f"${inventory_snapshot['inventory_value'].sum():,.2f}"
)

print(f"\nSaved: {OUTPUT_FILE}")