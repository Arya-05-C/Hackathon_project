import pandas as pd
import numpy as np

# ============================================================
# CONFIGURATION
# ============================================================

SALES_FILE = "../data/sales_train_evaluation.csv"
PRICES_FILE = "../data/sell_prices.csv"
CALENDAR_FILE = "../data/calendar.csv"

TARGET_STORE = "CA_1"

TARGET_DEPTS = [
    "FOODS_1",
    "FOODS_2",
    "HOUSEHOLD_1"
]

TARGET_SKUS = 400
HISTORY_DAYS = 730

RANDOM_STATE = 42

# ============================================================
# LOAD DATA
# ============================================================

print("=" * 60)
print("LOADING DATA")
print("=" * 60)

sales = pd.read_csv(SALES_FILE)
prices = pd.read_csv(PRICES_FILE)
calendar = pd.read_csv(CALENDAR_FILE)

print(f"Sales Shape    : {sales.shape}")
print(f"Prices Shape   : {prices.shape}")
print(f"Calendar Shape : {calendar.shape}")

# ============================================================
# FILTER STORE
# ============================================================

sales = sales[
    sales["store_id"] == TARGET_STORE
].copy()

print(f"\nAfter Store Filter ({TARGET_STORE})")
print(f"Rows : {len(sales)}")

# ============================================================
# FILTER DEPARTMENTS
# ============================================================

sales = sales[
    sales["dept_id"].isin(TARGET_DEPTS)
].copy()

print("\nSelected Departments:")
for d in TARGET_DEPTS:
    print(f"  - {d}")

print(f"Rows After Department Filter : {len(sales)}")

# ============================================================
# SELECT TOP 300 + RANDOM 100 SKUS
# ============================================================

day_cols = [c for c in sales.columns if c.startswith("d_")]

# Total demand per SKU
sales["total_units_sold"] = sales[day_cols].sum(axis=1)

# Average daily demand
sales["avg_daily_demand"] = (
    sales["total_units_sold"] / len(day_cols)
)

# Remove extremely sparse products
sales = sales[
    sales["avg_daily_demand"] >= 0.4
].copy()

print(f"\nSKUs after sparse-product filter : {len(sales)}")

# Rank by demand
sales_ranked = sales.sort_values(
    "total_units_sold",
    ascending=False
)

TOP_SKUS = 300
RANDOM_SKUS = 100

top_skus = (
    sales_ranked["item_id"]
    .head(TOP_SKUS)
    .tolist()
)

remaining_skus = (
    sales_ranked[
        ~sales_ranked["item_id"].isin(top_skus)
    ]["item_id"]
    .tolist()
)

rng = np.random.default_rng(RANDOM_STATE)

random_skus = rng.choice(
    remaining_skus,
    size=min(RANDOM_SKUS, len(remaining_skus)),
    replace=False
)

selected_skus = list(top_skus) + list(random_skus)

sales = sales[
    sales["item_id"].isin(selected_skus)
].copy()

print(f"Top SKUs     : {len(top_skus)}")
print(f"Random SKUs  : {len(random_skus)}")
print(f"Selected SKUs: {len(selected_skus)}")

# ============================================================
# KEEP ONLY LAST 730 DAYS
# ============================================================

day_cols = [c for c in sales.columns if c.startswith("d_")]

day_numbers = sorted(
    [int(c.split("_")[1]) for c in day_cols]
)

latest_day = max(day_numbers)

start_day = latest_day - HISTORY_DAYS + 1

required_day_cols = [
    f"d_{i}"
    for i in range(start_day, latest_day + 1)
]

metadata_cols = [
    "id",
    "item_id",
    "dept_id",
    "cat_id",
    "store_id",
    "state_id"
]

sales_subset = sales[
    metadata_cols + required_day_cols
].copy()

print("\nHistory Window")
print(f"Latest Day : d_{latest_day}")
print(f"Start Day  : d_{start_day}")
print(f"Days Kept  : {len(required_day_cols)}")

# ============================================================
# FILTER CALENDAR
# ============================================================

calendar_subset = calendar[
    calendar["d"].isin(required_day_cols)
].copy()

print(f"\nCalendar Rows Retained : {len(calendar_subset)}")

# ============================================================
# FILTER SELL PRICES
# ============================================================

prices_subset = prices[
    (prices["store_id"] == TARGET_STORE)
    &
    (prices["item_id"].isin(selected_skus))
].copy()

print(f"Price Records Retained : {len(prices_subset)}")

# ============================================================
# BASIC VALIDATION
# ============================================================

print("\n" + "=" * 60)
print("VALIDATION")
print("=" * 60)

print(f"Unique SKUs      : {sales_subset['item_id'].nunique()}")
print(f"Store Count      : {sales_subset['store_id'].nunique()}")
print(f"Department Count : {sales_subset['dept_id'].nunique()}")

print("\nDepartments Distribution:")
print(
    sales_subset["dept_id"]
    .value_counts()
    .sort_index()
)

# ============================================================
# SAVE FILES
# ============================================================

sales_subset.to_csv(
    "./data/sales_train_400sku_730days.csv",
    index=False
)

prices_subset.to_csv(
    "./data/sell_prices_400sku.csv",
    index=False
)

calendar_subset.to_csv(
    "./data/calendar_730days.csv",
    index=False
)

print("\n" + "=" * 60)
print("FILES SAVED")
print("=" * 60)

print("sales_train_400sku_730days.csv")
print("sell_prices_400sku.csv")
print("calendar_730days.csv")

print("\nDataset Ready For:")
print("✓ Demand Forecasting")
print("✓ Inventory Gap Detection")
print("✓ Supplier Recommendation")
print("✓ Purchase Order Generation")
print("✓ 7-Day Forecasting")
print("✓ 30-Day Forecasting")