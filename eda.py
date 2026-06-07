# """
# =============================================================================
# PROCUREMENT INTELLIGENCE SYSTEM — EDA + DEMAND FORECASTING PIPELINE
# =============================================================================
# Dataset  : M5 reduced (CA_1 | FOODS_1, FOODS_2, HOUSEHOLD_1 | ~400 SKUs | 730 days)
# Author   : Procurement AI Team
# Purpose  : EDA → Inventory Parameter Extraction → Multi-SKU Demand Forecasting
# Outputs  :
#     eda_sku_features.csv          — SKU-level feature table for synthetic generation
#     forecast_7_days.csv           — 7-day forward forecasts for all SKUs
#     forecast_30_days.csv          — 30-day forward forecasts for all SKUs
#     eda_plots/                    — EDA visualisation assets
#     forecast_plots/               — Sample SKU forecast charts
# =============================================================================
# """

# # -----------------------------------------------------------------------------
# # 0. IMPORTS & CONFIGURATION
# # -----------------------------------------------------------------------------
# import warnings, os, time
# warnings.filterwarnings("ignore")

# import numpy as np
# import pandas as pd
# import matplotlib
# matplotlib.use("Agg")          # headless - no display needed
# import matplotlib.pyplot as plt
# import matplotlib.ticker as mticker
# import seaborn as sns
# from pathlib import Path
# from scipy import stats

# # LightGBM - fast, handles lags + categoricals, no stationarity requirement
# import lightgbm as lgb
# from sklearn.metrics import mean_squared_error, mean_absolute_error

# # -- Output directories -------------------------------------------------------
# OUT_DIR      = Path("outputs")
# EDA_PLOT_DIR = OUT_DIR / "eda_plots"
# FC_PLOT_DIR  = OUT_DIR / "forecast_plots"
# for d in [OUT_DIR, EDA_PLOT_DIR, FC_PLOT_DIR]:
#     d.mkdir(parents=True, exist_ok=True)

# # -- Visual style -------------------------------------------------------------
# sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
# PALETTE = sns.color_palette("Set2", 8)

# # -- Helper Functions ---------------------------------------------------------
# def get_days_since_last_sale(sales_series):
#     """
#     Computes days since the last sale prior to day t.
#     Output days[t] represents days elapsed since the most recent day before t where sales > 0.
#     """
#     n = len(sales_series)
#     days = np.zeros(n)
#     days_since = 999.0  # Large fallback value
#     for i in range(n):
#         days[i] = days_since
#         if sales_series.iloc[i] > 0:
#             days_since = 1.0
#         else:
#             days_since += 1.0
#     return pd.Series(days, index=sales_series.index)


# def get_max_consecutive_zeros(sales_series):
#     """
#     Computes the longest continuous sequence of zero sales.
#     """
#     max_zeros = 0
#     current_zeros = 0
#     for val in sales_series:
#         if val == 0:
#             current_zeros += 1
#             if current_zeros > max_zeros:
#                 max_zeros = current_zeros
#         else:
#             current_zeros = 0
#     return max_zeros


# def calculate_croston_params(series):
#     """
#     Calculates Average Demand Interval (ADI), CV^2 of non-zero demand,
#     and assigns Croston category.
#     """
#     non_zeros = series[series > 0]
#     if len(non_zeros) == 0:
#         return len(series), 0.0, "Lumpy"
    
#     # ADI = Total Periods / Non-zero Periods
#     adi = len(series) / len(non_zeros)
    
#     # CV^2 of non-zero demand
#     mean_nz = non_zeros.mean()
#     std_nz = non_zeros.std()
#     cv2 = (std_nz / mean_nz) ** 2 if mean_nz > 0 else 0.0
#     if pd.isna(cv2):
#         cv2 = 0.0
        
#     # Categories based on Syntetos & Boylan (2005)
#     if adi < 1.32 and cv2 < 0.49:
#         category = "Smooth"
#     elif adi < 1.32 and cv2 >= 0.49:
#         category = "Erratic"
#     elif adi >= 1.32 and cv2 < 0.49:
#         category = "Intermittent"
#     else:
#         category = "Lumpy"
        
#     return adi, cv2, category

# print("=" * 70)
# print("  PROCUREMENT INTELLIGENCE SYSTEM - PIPELINE START")
# print("=" * 70)

# # -----------------------------------------------------------------------------
# # 1. DATA LOADING
# # -----------------------------------------------------------------------------
# print("\n[1/9] Loading datasets ...")

# sales_raw   = pd.read_csv("./data/sales_train_400sku_730days.csv")
# prices_raw  = pd.read_csv("./data/sell_prices_400sku.csv")
# calendar_raw = pd.read_csv("./data/calendar_730days.csv")

# print(f"  sales    : {sales_raw.shape}")
# print(f"  prices   : {prices_raw.shape}")
# print(f"  calendar : {calendar_raw.shape}")

# # -----------------------------------------------------------------------------
# # 2. DATA WRANGLING - WIDE TO LONG
# # -----------------------------------------------------------------------------
# print("\n[2/9] Reshaping sales to long format ...")

# # Identify day columns (d_XXXX pattern)
# day_cols = [c for c in sales_raw.columns if c.startswith("d_")]
# id_cols  = [c for c in sales_raw.columns if not c.startswith("d_")]

# sales_long = sales_raw.melt(
#     id_vars    = id_cols,
#     value_vars = day_cols,
#     var_name   = "d",
#     value_name = "sales"
# )

# # Merge calendar to get actual dates and event info
# calendar_raw["d"] = calendar_raw["d"].astype(str)
# sales_long = sales_long.merge(
#     calendar_raw[["d", "date", "wm_yr_wk", "weekday", "wday", "month",
#                   "year", "event_name_1", "event_type_1",
#                   "event_name_2", "event_type_2",
#                   "snap_CA"]],
#     on="d", how="left"
# )
# sales_long["date"] = pd.to_datetime(sales_long["date"])

# # Merge sell prices  (wm_yr_wk aligns price to the correct week)
# sales_long = sales_long.merge(
#     prices_raw[["store_id", "item_id", "wm_yr_wk", "sell_price"]],
#     on=["store_id", "item_id", "wm_yr_wk"],
#     how="left"
# )

# # Convenience columns
# sales_long["dept_id"] = sales_long["item_id"].str.rsplit("_", n=1).str[0]
# sales_long["cat_id"]  = sales_long["item_id"].str.split("_").str[0]
# sales_long.sort_values(["item_id", "date"], inplace=True)
# sales_long.reset_index(drop=True, inplace=True)

# print(f"  Long table : {sales_long.shape}  |  date range: "
#       f"{sales_long['date'].min().date()} -> {sales_long['date'].max().date()}")

# # -----------------------------------------------------------------------------
# # 3. EDA - DATASET OVERVIEW
# # -----------------------------------------------------------------------------
# print("\n[3/9] EDA - Dataset Overview ...")

# sku_list  = sales_long["item_id"].unique()
# dept_dist = sales_long.drop_duplicates("item_id")["dept_id"].value_counts()
# missing   = sales_long.isnull().sum()

# print(f"\n  -- Dataset Overview ---------------------------------")
# print(f"  Unique SKUs        : {len(sku_list)}")
# print(f"  Date coverage      : {sales_long['date'].min().date()} -> {sales_long['date'].max().date()}")
# print(f"  Total rows         : {len(sales_long):,}")
# print(f"\n  Department distribution:")
# for dept, cnt in dept_dist.items():
#     print(f"    {dept:<20}: {cnt} SKUs")
# print(f"\n  Missing values (key cols):")
# for col in ["sales", "sell_price", "date"]:
#     print(f"    {col:<20}: {missing[col]}")

# # -- 3a. Department distribution bar chart ------------------------------------
# fig, ax = plt.subplots(figsize=(8, 4))
# dept_dist.plot(kind="bar", ax=ax, color=PALETTE[:len(dept_dist)], edgecolor="white")
# ax.set_title("SKU Count by Department", fontweight="bold")
# ax.set_xlabel("Department"); ax.set_ylabel("SKU Count")
# ax.tick_params(axis="x", rotation=0)
# plt.tight_layout()
# fig.savefig(EDA_PLOT_DIR / "01_dept_distribution.png", dpi=150)
# plt.close()

# # -----------------------------------------------------------------------------
# # 4. EDA - DEMAND ANALYSIS
# # -----------------------------------------------------------------------------
# print("\n[4/9] EDA - Demand Analysis ...")

# # -- SKU-level daily demand statistics ----------------------------------------
# sku_stats = (
#     sales_long.groupby("item_id")["sales"]
#     .agg(
#         mean_demand   = "mean",
#         median_demand = "median",
#         std_demand    = "std",
#         total_demand  = "sum",
#         p25           = lambda x: x.quantile(0.25),
#         p75           = lambda x: x.quantile(0.75),
#         p95           = lambda x: x.quantile(0.95),
#         zero_rate     = lambda x: (x == 0).mean(),
#         n_days        = "count"
#     )
#     .reset_index()
# )
# sku_stats["cv"] = sku_stats["std_demand"] / (sku_stats["mean_demand"] + 1e-9)

# print(f"\n  -- Aggregate Daily Demand (all SKUs) ----------------")
# agg = sales_long["sales"]
# print(f"  Mean       : {agg.mean():.4f}")
# print(f"  Median     : {agg.median():.4f}")
# print(f"  Std Dev    : {agg.std():.4f}")
# print(f"  P25 / P75  : {agg.quantile(0.25):.2f} / {agg.quantile(0.75):.2f}")
# print(f"  P95        : {agg.quantile(0.95):.2f}")
# print(f"  Zero-sales : {(agg == 0).mean()*100:.1f}% of all obs")

# # -- Demand distribution -------------------------------------------------------
# fig, axes = plt.subplots(1, 2, figsize=(13, 4))
# axes[0].hist(sku_stats["mean_demand"], bins=40, color=PALETTE[0], edgecolor="white")
# axes[0].set_title("Distribution of SKU Mean Daily Demand", fontweight="bold")
# axes[0].set_xlabel("Mean Daily Demand"); axes[0].set_ylabel("Frequency")
# axes[1].hist(sku_stats["cv"], bins=40, color=PALETTE[1], edgecolor="white")
# axes[1].set_title("Coefficient of Variation (CV) per SKU", fontweight="bold")
# axes[1].set_xlabel("CV"); axes[1].set_ylabel("Frequency")
# plt.tight_layout()
# fig.savefig(EDA_PLOT_DIR / "02_demand_distribution.png", dpi=150)
# plt.close()

# # -- Aggregate daily demand trend ---------------------------------------------
# daily_total = sales_long.groupby("date")["sales"].sum().reset_index()
# fig, ax = plt.subplots(figsize=(14, 4))
# ax.plot(daily_total["date"], daily_total["sales"], lw=1.2, color=PALETTE[2])
# ax.set_title("Total Daily Demand - All SKUs", fontweight="bold")
# ax.set_xlabel("Date"); ax.set_ylabel("Units Sold")
# plt.tight_layout()
# fig.savefig(EDA_PLOT_DIR / "03_aggregate_demand_trend.png", dpi=150)
# plt.close()

# # -----------------------------------------------------------------------------
# # 5. EDA - PRODUCT SEGMENTATION: ABC + XYZ
# # -----------------------------------------------------------------------------
# print("\n[5/9] EDA - Product Segmentation (ABC / XYZ) ...")

# # -- ABC Analysis - cumulative revenue contribution ---------------------------
# # Revenue proxy: total_demand x mean_price
# price_mean = (
#     sales_long.groupby("item_id")["sell_price"]
#     .mean()
#     .reset_index()
#     .rename(columns={"sell_price": "mean_price"})
# )
# sku_stats = sku_stats.merge(price_mean, on="item_id", how="left")
# sku_stats["revenue"] = sku_stats["total_demand"] * sku_stats["mean_price"].fillna(1)

# sku_stats.sort_values("revenue", ascending=False, inplace=True)
# sku_stats["cum_pct"] = sku_stats["revenue"].cumsum() / (sku_stats["revenue"].sum() + 1e-9)

# def assign_abc(cum_pct):
#     if cum_pct <= 0.70:
#         return "A"
#     elif cum_pct <= 0.90:
#         return "B"
#     else:
#         return "C"

# sku_stats["abc_class"] = sku_stats["cum_pct"].apply(assign_abc)

# # -- XYZ Analysis - quantile-based demand variability (CV) --------------------
# cv_q33 = sku_stats["cv"].quantile(0.33)
# cv_q66 = sku_stats["cv"].quantile(0.66)
# print(f"  CV Thresholds (quantiles): 33rd={cv_q33:.4f}, 66th={cv_q66:.4f}")

# def assign_xyz(cv):
#     if cv <= cv_q33:
#         return "X"   # stable
#     elif cv <= cv_q66:
#         return "Y"   # moderate variability
#     else:
#         return "Z"   # highly variable / intermittent

# sku_stats["xyz_class"] = sku_stats["cv"].apply(assign_xyz)
# sku_stats["abc_xyz"]   = sku_stats["abc_class"] + sku_stats["xyz_class"]

# # -- Calculate Demand Intermittency & Sale Frequency Metrics -------------------
# print("  Calculating intermittency and sale frequency metrics ...")
# intermittency_metrics = []
# for item_id, group in sales_long.groupby("item_id"):
#     sales_series = group["sales"]
#     adi, cv2_val, croston = calculate_croston_params(sales_series)
#     max_zeros = get_max_consecutive_zeros(sales_series)
#     sale_freq = (sales_series > 0).mean()
    
#     intermittency_metrics.append({
#         "item_id": item_id,
#         "adi": round(adi, 4),
#         "cv2_non_zero": round(cv2_val, 4),
#         "croston_class": croston,
#         "max_consecutive_zero_days": max_zeros,
#         "sale_frequency": round(sale_freq, 4)
#     })
# intermittency_df = pd.DataFrame(intermittency_metrics)
# sku_stats = sku_stats.merge(intermittency_df, on="item_id", how="left")

# # -- Enhanced Price Analysis ---------------------------------------------------
# print("  Calculating enhanced price metrics ...")
# price_metrics = []
# for item_id, group in sales_long.groupby("item_id"):
#     prices = group["sell_price"].dropna()
#     if len(prices) == 0:
#         price_metrics.append({
#             "item_id": item_id,
#             "price_elasticity": 0.0,
#             "price_change_count": 0,
#             "max_price": 0.0,
#             "min_price": 0.0,
#             "avg_discount_pct": 0.0,
#             "promo_days_pct": 0.0
#         })
#         continue
        
#     max_p = prices.max()
#     min_p = prices.min()
    
#     df_valid = group.dropna(subset=["sell_price"])
#     if len(df_valid) >= 10 and df_valid["sell_price"].nunique() > 1:
#         corr, _ = stats.spearmanr(df_valid["sell_price"], df_valid["sales"])
#         price_elasticity = corr if not pd.isna(corr) else 0.0
#     else:
#         price_elasticity = 0.0
        
#     price_seq = group["sell_price"].dropna()
#     if len(price_seq) > 1:
#         price_changes = (price_seq != price_seq.shift(1)).sum() - 1
#         price_changes = max(0, price_changes)
#     else:
#         price_changes = 0
        
#     discounts = (max_p - prices) / (max_p + 1e-9)
#     avg_discount = discounts.mean() * 100
    
#     promo_days = (prices <= 0.98 * max_p).mean() * 100
    
#     price_metrics.append({
#         "item_id": item_id,
#         "price_elasticity": round(price_elasticity, 4),
#         "price_change_count": price_changes,
#         "max_price": round(max_p, 4),
#         "min_price": round(min_p, 4),
#         "avg_discount_pct": round(avg_discount, 4),
#         "promo_days_pct": round(promo_days, 4)
#     })
# price_df = pd.DataFrame(price_metrics)
# sku_stats = sku_stats.merge(price_df, on="item_id", how="left")

# # -- Detailed ABC-XYZ Matrix Generation ---------------------------------------
# print("\n  -- ABC-XYZ Matrix Summary (Counts, Volume & Revenue) -------")
# matrix_summary = []
# total_skus = len(sku_stats)
# total_rev = sku_stats["revenue"].sum()
# total_dem = sku_stats["total_demand"].sum()

# for abc in ["A", "B", "C"]:
#     for xyz in ["X", "Y", "Z"]:
#         cell = sku_stats[(sku_stats["abc_class"] == abc) & (sku_stats["xyz_class"] == xyz)]
#         sku_count = len(cell)
#         rev_val = cell["revenue"].sum()
#         dem_val = cell["total_demand"].sum()
#         matrix_summary.append({
#             "abc_class": abc,
#             "xyz_class": xyz,
#             "sku_count": sku_count,
#             "sku_count_pct": (sku_count / total_skus) * 100 if total_skus > 0 else 0.0,
#             "total_revenue": rev_val,
#             "revenue_pct": (rev_val / total_rev) * 100 if total_rev > 0 else 0.0,
#             "total_demand": dem_val,
#             "demand_pct": (dem_val / total_dem) * 100 if total_dem > 0 else 0.0
#         })
# matrix_summary_df = pd.DataFrame(matrix_summary)
# matrix_summary_df.to_csv(OUT_DIR / "abc_xyz_matrix_summary.csv", index=False)

# # Print detailed summary
# print(f"{'Cell':<6} | {'SKUs':<6} | {'SKU %':<8} | {'Revenue ($)':<12} | {'Rev %':<8} | {'Demand (U)':<12} | {'Dem %':<8}")
# print("-" * 75)
# for _, r in matrix_summary_df.iterrows():
#     cell_name = f"{r['abc_class']}{r['xyz_class']}"
#     print(f"{cell_name:<6} | {int(r['sku_count']):<6} | {r['sku_count_pct']:.2f}% | "
#           f"{r['total_revenue']:,.2f} | {r['revenue_pct']:.2f}% | "
#           f"{int(r['total_demand']):<12,} | {r['demand_pct']:.2f}%")

# print(f"\n  ABC distribution:\n{sku_stats['abc_class'].value_counts().to_string()}")
# print(f"\n  XYZ distribution:\n{sku_stats['xyz_class'].value_counts().to_string()}")

# # -- ABC Pareto & Matrix heatmaps ---------------------------------------------
# fig, axes = plt.subplots(1, 2, figsize=(14, 5))
# abc_counts = sku_stats["abc_class"].value_counts().sort_index()
# abc_counts.plot(kind="bar", ax=axes[0], color=[PALETTE[3], PALETTE[4], PALETTE[5]],
#                 edgecolor="white")
# axes[0].set_title("ABC Classification (SKU Count)", fontweight="bold")
# axes[0].set_xlabel("ABC Class"); axes[0].set_ylabel("SKU Count")
# axes[0].tick_params(axis="x", rotation=0)

# # Two-panel heatmap: SKU Count and Revenue %
# heatmap_counts = pd.crosstab(sku_stats["abc_class"], sku_stats["xyz_class"])
# sns.heatmap(heatmap_counts, annot=True, fmt="d", cmap="YlOrRd", ax=axes[1], linewidths=0.5)
# axes[1].set_title("ABC-XYZ Matrix (SKU Count)", fontweight="bold")
# plt.tight_layout()
# fig.savefig(EDA_PLOT_DIR / "04_abc_xyz_matrix.png", dpi=150)
# plt.close()

# # ─────────────────────────────────────────────────────────────────────────────
# # 6. EDA — VELOCITY CLASSIFICATION
# # ─────────────────────────────────────────────────────────────────────────────
# # Fast  : top 33rd percentile of mean daily demand
# # Medium: mid 33rd percentile
# # Slow  : bottom 33rd percentile

# p33 = sku_stats["mean_demand"].quantile(0.33)
# p66 = sku_stats["mean_demand"].quantile(0.66)

# def assign_velocity(mean_d):
#     if mean_d >= p66:
#         return "Fast"
#     elif mean_d >= p33:
#         return "Medium"
#     else:
#         return "Slow"

# sku_stats["velocity_class"] = sku_stats["mean_demand"].apply(assign_velocity)
# print(f"\n  Velocity distribution:\n{sku_stats['velocity_class'].value_counts().to_string()}")

# # ─────────────────────────────────────────────────────────────────────────────
# # 7. EDA — SEASONALITY ANALYSIS
# # ─────────────────────────────────────────────────────────────────────────────
# print("\n[6/9] EDA — Seasonality & Event Analysis …")

# # ── Day-of-week ───────────────────────────────────────────────────────────────
# dow_map = {1:"Sun",2:"Mon",3:"Tue",4:"Wed",5:"Thu",6:"Fri",7:"Sat"}
# sales_long["dow_label"] = sales_long["wday"].map(dow_map)
# dow_demand = (
#     sales_long.groupby("wday")["sales"]
#     .mean()
#     .reset_index()
#     .sort_values("wday")
# )
# dow_demand["dow_label"] = dow_demand["wday"].map(dow_map)

# # ── Monthly ───────────────────────────────────────────────────────────────────
# month_demand = sales_long.groupby("month")["sales"].mean().reset_index()

# # ── Event impact ─────────────────────────────────────────────────────────────
# event_mask   = sales_long["event_name_1"].notna()
# event_demand = sales_long.groupby(event_mask)["sales"].mean()
# print(f"\n  Avg daily demand — event days    : {event_demand.get(True, 0):.4f}")
# print(f"  Avg daily demand — non-event days: {event_demand.get(False, 0):.4f}")

# snap_demand = sales_long.groupby("snap_CA")["sales"].mean()
# print(f"\n  Avg demand on SNAP days  : {snap_demand.get(1, snap_demand.get(1.0, 0)):.4f}")
# print(f"  Avg demand on non-SNAP   : {snap_demand.get(0, snap_demand.get(0.0, 0)):.4f}")

# # ── Seasonality plots ─────────────────────────────────────────────────────────
# fig, axes = plt.subplots(1, 2, figsize=(14, 4))
# axes[0].bar(dow_demand["dow_label"], dow_demand["sales"],
#             color=PALETTE[:7], edgecolor="white")
# axes[0].set_title("Average Demand by Day of Week", fontweight="bold")
# axes[0].set_xlabel("Day"); axes[0].set_ylabel("Avg Units Sold")

# axes[1].bar(month_demand["month"], month_demand["sales"],
#             color=PALETTE[: len(month_demand)], edgecolor="white")
# axes[1].set_title("Average Demand by Month", fontweight="bold")
# axes[1].set_xlabel("Month"); axes[1].set_ylabel("Avg Units Sold")
# axes[1].xaxis.set_major_locator(mticker.MultipleLocator(1))
# plt.tight_layout()
# fig.savefig(EDA_PLOT_DIR / "05_seasonality.png", dpi=150)
# plt.close()

# # ─────────────────────────────────────────────────────────────────────────────
# # 8. EDA — PRICE ANALYSIS
# # ──────────────────────────────────────────────────────────────────�# -----------------------------------------------------------------------------
# # 9. INVENTORY PARAMETER EXTRACTION
# # -----------------------------------------------------------------------------
# print("\n[8/9] Extracting Inventory Parameters ...")

# # -- Ensure dept_id exists in sku_stats
# if "dept_id" not in sku_stats.columns:
#     sku_stats["dept_id"] = sku_stats["item_id"].str.rsplit("_", n=1).str[0]

# # -- 9a. Lead-time-ready inventory features
# # Assign lead time parameters based on department category
# def get_lead_time_params(dept_id):
#     if "FOODS" in dept_id:
#         return 3.0, 0.5  # grocery/perishables: short, stable lead time
#     elif "HOUSEHOLD" in dept_id:
#         return 10.0, 1.5  # non-perishables: longer, more variable lead time
#     else:
#         return 7.0, 1.0  # general default

# lt_params = sku_stats["dept_id"].apply(get_lead_time_params)
# sku_stats["lead_time_mean"] = [x[0] for x in lt_params]
# sku_stats["lead_time_std"] = [x[1] for x in lt_params]

# # -- 9b. Dynamic Service-Level based safety stock (A: 98%, B: 95%, C: 90%)
# z_map = {"A": 2.054, "B": 1.645, "C": 1.282}
# sku_stats["service_level_z"] = sku_stats["abc_class"].map(z_map).fillna(1.282)

# sku_stats["average_daily_demand"] = sku_stats["mean_demand"]
# sku_stats["demand_std"] = sku_stats["std_demand"]
# sku_stats["coefficient_of_variation"] = sku_stats["cv"]

# # SS = Z * sqrt(L * sigma_D^2 + D^2 * sigma_L^2)
# sku_stats["suggested_safety_stock"] = (
#     sku_stats["service_level_z"] * np.sqrt(
#         sku_stats["lead_time_mean"] * (sku_stats["demand_std"] ** 2) +
#         (sku_stats["average_daily_demand"] ** 2) * (sku_stats["lead_time_std"] ** 2)
#     )
# ).round(2)

# sku_stats["suggested_reorder_point"] = (
#     sku_stats["average_daily_demand"] * sku_stats["lead_time_mean"] +
#     sku_stats["suggested_safety_stock"]
# ).round(2)

# # -- 9c. Economic Order Quantity (EOQ) calculation
# # DA = Annual Demand, Order Cost S = $50, Holding Cost H = 20% of mean unit price (min $0.10)
# sku_stats["eoq"] = np.sqrt(
#     (2 * (sku_stats["average_daily_demand"] * 365) * 50.0) /
#     np.maximum(0.10, 0.20 * sku_stats["mean_price"])
# ).round(0).astype(int)

# # -- 9d. Procurement Risk Indicators
# def get_risk_level(score):
#     if score >= 3:
#         return "High"
#     elif score >= 2:
#         return "Medium"
#     else:
#         return "Low"

# risk_metrics = []
# for idx, r in sku_stats.iterrows():
#     # Intermittency Risk: based on ADI
#     int_score = 3 if r["adi"] >= 1.5 else (2 if r["adi"] >= 1.1 else 1)
    
#     # Volatility Risk: based on CV
#     vol_score = 3 if r["cv"] >= 1.0 else (2 if r["cv"] >= 0.5 else 1)
    
#     # Lead Time Risk: relative lead time standard deviation
#     lt_ratio = r["lead_time_std"] / r["lead_time_mean"]
#     lt_score = 3 if lt_ratio >= 0.15 else (2 if lt_ratio >= 0.08 else 1)
    
#     # Overall Risk: max score
#     overall_score = max(int_score, vol_score, lt_score)
    
#     risk_metrics.append({
#         "item_id": r["item_id"],
#         "intermittency_risk": get_risk_level(int_score),
#         "demand_volatility_risk": get_risk_level(vol_score),
#         "lead_time_risk": get_risk_level(lt_score),
#         "overall_procurement_risk": get_risk_level(overall_score)
#     })
# risk_df = pd.DataFrame(risk_metrics)
# sku_stats = sku_stats.merge(risk_df, on="item_id", how="left")

# # -- 9e. Inventory Gap Readiness Columns
# curr_inv_list = []
# on_order_list = []
# np.random.seed(42)  # reproducible simulation
# for idx, r in sku_stats.iterrows():
#     ss = r["suggested_safety_stock"]
#     rop = r["suggested_reorder_point"]
#     eoq_val = r["eoq"]
    
#     # Simulate current inventory
#     rng_val = np.random.rand()
#     if rng_val < 0.05:
#         curr_inv = 0.0  # Stockout
#     elif rng_val < 0.15:
#         curr_inv = np.random.uniform(0.1 * ss, 0.9 * ss) if ss > 0 else 0.0  # Understocked
#     elif rng_val < 0.80:
#         curr_inv = np.random.uniform(ss, rop) if rop > ss else ss  # Healthy
#     else:
#         curr_inv = np.random.uniform(rop, rop + 1.5 * ss) if ss > 0 else rop  # Overstocked
        
#     # Simulate on-order quantity for items running low (current_inv < rop)
#     rng_order = np.random.rand()
#     if curr_inv < rop and rng_order < 0.40:
#         on_order = eoq_val
#     else:
#         on_order = 0.0
        
#     curr_inv_list.append(round(curr_inv, 2))
#     on_order_list.append(round(on_order, 2))

# sku_stats["current_inventory"] = curr_inv_list
# sku_stats["on_order_quantity"] = on_order_list

# # Inventory Gap = max(0, ROP - (Inv + OnOrder))
# sku_stats["inventory_gap"] = np.maximum(
#     0.0,
#     sku_stats["suggested_reorder_point"] - (sku_stats["current_inventory"] + sku_stats["on_order_quantity"])
# ).round(2)

# def get_inventory_status(row):
#     curr = row["current_inventory"]
#     ss = row["suggested_safety_stock"]
#     rop = row["suggested_reorder_point"]
#     if curr == 0.0:
#         return "Stockout"
#     elif curr < ss:
#         return "Understocked"
#     elif curr <= rop:
#         return "Healthy"
#     else:
#         return "Overstocked"

# sku_stats["inventory_status"] = sku_stats.apply(get_inventory_status, axis=1)

# # -- Final feature table ------------------------------------------------------
# feature_cols = [
#     "item_id", "dept_id",
#     "average_daily_demand", "median_demand", "demand_std",
#     "coefficient_of_variation", "total_demand",
#     "p25", "p75", "p95", "zero_rate",
#     "adi", "cv2_non_zero", "croston_class", "max_consecutive_zero_days", "sale_frequency",
#     "mean_price", "price_std", "price_range_pct", "max_price", "min_price",
#     "price_elasticity", "price_change_count", "avg_discount_pct", "promo_days_pct", "revenue",
#     "abc_class", "xyz_class", "abc_xyz", "velocity_class",
#     "lead_time_mean", "lead_time_std", "service_level_z",
#     "suggested_safety_stock", "suggested_reorder_point", "eoq",
#     "intermittency_risk", "demand_volatility_risk", "lead_time_risk", "overall_procurement_risk",
#     "current_inventory", "on_order_quantity", "inventory_gap", "inventory_status"
# ]

# eda_features = sku_stats[feature_cols].copy()
# eda_features.to_csv(OUT_DIR / "eda_sku_features.csv", index=False)
# print(f"  Saved: eda_sku_features.csv  ({len(eda_features)} SKUs x {len(feature_cols)} features)")R EXTRACTION
# # ─────────────────────────────────────────────────────────────────────────────
# print("\n[8/9] Extracting Inventory Parameters …")

# """
# Safety Stock  = Z × σ_demand × √(lead_time)
#   We assume a standard lead time of 7 days for this extraction phase.
#   The supplier generation module will override with actual lead times.

# Reorder Point = (mean_demand × lead_time) + safety_stock
#   Service level = 95%  →  Z = 1.65
# """

# Z_SCORE      = 1.65  # 95% service level
# ASSUMED_LT   = 7     # days — placeholder until actual suppliers are assigned

# sku_stats["average_daily_demand"]  = sku_stats["mean_demand"]
# sku_stats["demand_std"]            = sku_stats["std_demand"]
# sku_stats["coefficient_of_variation"] = sku_stats["cv"]
# sku_stats["suggested_safety_stock"]   = (
#     Z_SCORE * sku_stats["demand_std"] * np.sqrt(ASSUMED_LT)
# ).round(2)
# sku_stats["suggested_reorder_point"]  = (
#     sku_stats["average_daily_demand"] * ASSUMED_LT
#     + sku_stats["suggested_safety_stock"]
# ).round(2)

# # ── Final feature table ───────────────────────────────────────────────────────
# feature_cols = [
#     "item_id", "dept_id",
#     "average_daily_demand", "median_demand", "demand_std",
#     "coefficient_of_variation", "total_demand",
#     "p25", "p75", "p95", "zero_rate",
#     "mean_price", "price_std", "price_range_pct", "revenue",
#     "abc_class", "xyz_class", "abc_xyz", "velocity_class",
#     "suggested_safety_stock", "suggested_reorder_point",
# ]
# # Add dept_id if missing
# if "dept_id" not in sku_stats.columns:
#     sku_stats["dept_id"] = sku_stats["item_id"].str.rsplit("_", n=1).str[0]

# eda_features = sku_stats[feature_cols].copy()
# eda_features.to_csv(OUT_DIR / "eda_sku_features.csv", index=False)
# print(f"  Saved: eda_sku_features.csv  ({len(eda_features)} SKUs × {len(feature_cols)} features)")

# # ─────────────────────────────────────────────────────────────────────────────
# # 10. DEMAND FORECASTING PIPELINE
# # ─────────────────────────────────────────────────────────────────────────────
# print("\n[9/9] Demand Forecasting — LightGBM Multi-SKU Pipeline …")

# """
# MODEL CHOICE: LightGBM (Gradient Boosted Trees)
# ───────────────────────────────────────────────
# Why LightGBM for procurement forecasting?

# 1. SPEED   — Handles 400 SKUs × 730 days easily in minutes on CPU.
#              ARIMA/SARIMA would require 400 separate model fits.

# 2. FEATURES — Natively handles:
#                • Lag features (autocorrelation)
#                • Rolling statistics (trend, variance)
#                • Categorical features (dept, velocity class)
#                • Calendar effects (DoW, month, events, SNAP)
#              — No manual stationarity checks needed.

# 3. ACCURACY — Outperforms classical models on M5 competition data,
#               especially for intermittent and lumpy demand (Z-class SKUs).

# 4. EXPLAINABILITY — Feature importance gives procurement team insight
#                     into what drives demand (event vs. price vs. lag).

# 5. SINGLE GLOBAL MODEL — One model trained on all SKUs simultaneously.
#    SKU identity is encoded as a categorical feature, allowing the model
#    to learn cross-SKU patterns (shared seasonal effects, event lifts).
#    This is better than 400 local models for low-demand SKUs with sparse data.

# TRAINING STRATEGY:
#   • Last 30 days withheld as validation set
#   • Recursive multi-step forecasting for 7- and 30-day horizons
#   • Features: lags [1,2,3,7,14,28], rolling mean/std [7,14,28],
#               DoW, month, snap_CA, event flags, abc/xyz encodings
# """

# # ── 10a. Build daily SKU × date panel ────────────────────────────────────────
# print("  Building full panel …")

# # Pivot to wide then re-melt to guarantee no missing dates
# sales_wide = sales_long.pivot_table(
#     index   = "date",
#     columns = "item_id",
#     values  = "sales",
#     aggfunc = "sum"
# ).fillna(0)

# # Calendar features aligned to date index
# cal_feat = (
#     sales_long[["date","wday","month","snap_CA",
#                 "event_name_1","event_type_1"]]
#     .drop_duplicates("date")
#     .set_index("date")
# )
# cal_feat["is_event"] = cal_feat["event_name_1"].notna().astype(int)
# cal_feat["is_snap"]  = cal_feat["snap_CA"].fillna(0).astype(int)

# # ── 10b. Feature engineering function ────────────────────────────────────────
# def build_features(df_sku: pd.DataFrame, sku_id: str,
#                    sku_meta: dict) -> pd.DataFrame:
#     """
#     Given a time-series Series for one SKU, return a feature DataFrame.
#     df_sku : DataFrame with columns [date, sales] indexed by date
#     sku_meta: dict with abc_class, xyz_class, velocity_class
#     """
#     df = df_sku.copy()
#     df = df.join(cal_feat[["wday","month","is_event","is_snap"]])

#     # Lag features — capture autocorrelation
#     for lag in [1, 2, 3, 7, 14, 28]:
#         df[f"lag_{lag}"] = df["sales"].shift(lag)

#     # Rolling statistics — capture local trend and volatility
#     for window in [7, 14, 28]:
#         df[f"roll_mean_{window}"] = df["sales"].shift(1).rolling(window).mean()
#         df[f"roll_std_{window}"]  = df["sales"].shift(1).rolling(window).std()

#     # Calendar features
#     df["dow"]   = df["wday"]
#     df["month_feat"] = df["month"]

#     # SKU-level metadata features (encoded as integer)
#     abc_map = {"A": 0, "B": 1, "C": 2}
#     xyz_map = {"X": 0, "Y": 1, "Z": 2}
#     vel_map = {"Fast": 0, "Medium": 1, "Slow": 2}
#     df["abc_enc"] = abc_map.get(sku_meta.get("abc_class", "C"), 2)
#     df["xyz_enc"] = xyz_map.get(sku_meta.get("xyz_class", "Z"), 2)
#     df["vel_enc"] = vel_map.get(sku_meta.get("velocity_class", "Slow"), 2)

#     df.dropna(inplace=True)
#     return df

# # ── 10c. Build global training dataset ───────────────────────────────────────
# print("  Engineering features for all SKUs …")

# FEATURE_COLS = (
#     [f"lag_{l}" for l in [1, 2, 3, 7, 14, 28]]
#     + [f"roll_mean_{w}" for w in [7, 14, 28]]
#     + [f"roll_std_{w}"  for w in [7, 14, 28]]
#     + ["dow", "month_feat", "is_event", "is_snap",
#        "abc_enc", "xyz_enc", "vel_enc"]
# )
# TARGET_COL = "sales"
# VAL_DAYS   = 30

# sku_meta_map = (
#     sku_stats.set_index("item_id")[["abc_class","xyz_class","velocity_class"]]
#     .to_dict(orient="index")
# )

# all_dfs = []
# for sku in sku_list:
#     ts = sales_wide[[sku]].rename(columns={sku: "sales"})
#     meta = sku_meta_map.get(sku, {})
#     df_feat = build_features(ts, sku, meta)
#     df_feat["item_id"] = sku
#     all_dfs.append(df_feat)

# panel = pd.concat(all_dfs).reset_index()
# panel.rename(columns={"index": "date"}, inplace=True)
# panel["date"] = pd.to_datetime(panel["date"])

# print(f"  Panel shape: {panel.shape}")

# # ── 10d. Train / Validation split ────────────────────────────────────────────
# max_date   = panel["date"].max()
# val_cutoff = max_date - pd.Timedelta(days=VAL_DAYS)

# train_df = panel[panel["date"] <= val_cutoff].copy()
# val_df   = panel[panel["date"] >  val_cutoff].copy()

# X_train = train_df[FEATURE_COLS];  y_train = train_df[TARGET_COL]
# X_val   = val_df[FEATURE_COLS];    y_val   = val_df[TARGET_COL]

# print(f"  Train: {len(train_df):,} rows  |  Val: {len(val_df):,} rows")

# # ── 10e. LightGBM training ────────────────────────────────────────────────────
# print("  Training LightGBM global model …")
# t0 = time.time()

# params = {
#     "objective"        : "regression_l1",   # MAE objective — robust to outliers
#     "metric"           : ["rmse", "mae"],
#     "n_estimators"     : 800,
#     "learning_rate"    : 0.05,
#     "num_leaves"       : 63,
#     "min_child_samples": 20,
#     "feature_fraction" : 0.8,
#     "bagging_fraction" : 0.8,
#     "bagging_freq"     : 5,
#     "reg_alpha"        : 0.1,
#     "reg_lambda"       : 0.1,
#     "n_jobs"           : -1,
#     "verbose"          : -1,
#     "random_state"     : 42,
# }

# model = lgb.LGBMRegressor(**params)
# model.fit(
#     X_train, y_train,
#     eval_set           = [(X_val, y_val)],
#     callbacks          = [lgb.early_stopping(50, verbose=False),
#                           lgb.log_evaluation(period=-1)],
# )
# elapsed = time.time() - t0
# print(f"  Training complete in {elapsed:.1f}s  |  Best iteration: {model.best_iteration_}")

# # ── 10f. Validation metrics ───────────────────────────────────────────────────
# val_pred = np.maximum(0, model.predict(X_val))

# rmse = np.sqrt(mean_squared_error(y_val, val_pred))
# mae  = mean_absolute_error(y_val, val_pred)
# mape_mask  = y_val > 0
# mape = np.mean(np.abs((y_val[mape_mask] - val_pred[mape_mask]) / y_val[mape_mask])) * 100

# print(f"\n  ── Validation Metrics ────────────────────────────────")
# print(f"  RMSE : {rmse:.4f}")
# print(f"  MAE  : {mae:.4f}")
# print(f"  MAPE : {mape:.2f}%  (non-zero demand days only)")

# # ── 10g. Feature importance plot ──────────────────────────────────────────────
# imp_df = pd.DataFrame({
#     "feature"   : FEATURE_COLS,
#     "importance": model.feature_importances_
# }).sort_values("importance", ascending=True).tail(15)

# fig, ax = plt.subplots(figsize=(9, 6))
# ax.barh(imp_df["feature"], imp_df["importance"], color=PALETTE[2])
# ax.set_title("Top-15 Feature Importances (LightGBM)", fontweight="bold")
# ax.set_xlabel("Importance Score")
# plt.tight_layout()
# fig.savefig(FC_PLOT_DIR / "00_feature_importance.png", dpi=150)
# plt.close()

# # ── 10h. Recursive multi-step forecasting ────────────────────────────────────
# print("\n  Generating forecasts for all SKUs …")

# def recursive_forecast(model, sku_id: str, history: pd.Series,
#                         cal_future: pd.DataFrame, n_steps: int,
#                         sku_meta: dict) -> pd.DataFrame:
#     """
#     Recursively generates n_steps daily forecasts for one SKU.
#     Each predicted value is appended to history for the next lag computation.
#     """
#     hist = history.copy()
#     preds = []
#     future_dates = cal_future.index[:n_steps]

#     for fd in future_dates:
#         row = {}
#         # Lags from rolling history
#         for lag in [1, 2, 3, 7, 14, 28]:
#             row[f"lag_{lag}"] = hist.iloc[-lag] if lag <= len(hist) else 0
#         # Rolling stats
#         for window in [7, 14, 28]:
#             slice_ = hist.iloc[-window:] if window <= len(hist) else hist
#             row[f"roll_mean_{window}"] = slice_.mean()
#             row[f"roll_std_{window}"]  = slice_.std() if len(slice_) > 1 else 0

#         # Calendar
#         row["dow"]         = cal_future.loc[fd, "wday"]  if fd in cal_future.index else 4
#         row["month_feat"]  = cal_future.loc[fd, "month"] if fd in cal_future.index else 1
#         row["is_event"]    = int(cal_future.loc[fd, "is_event"]) if fd in cal_future.index else 0
#         row["is_snap"]     = int(cal_future.loc[fd, "is_snap"])  if fd in cal_future.index else 0

#         # SKU meta
#         abc_map = {"A": 0, "B": 1, "C": 2}
#         xyz_map = {"X": 0, "Y": 1, "Z": 2}
#         vel_map = {"Fast": 0, "Medium": 1, "Slow": 2}
#         row["abc_enc"] = abc_map.get(sku_meta.get("abc_class", "C"), 2)
#         row["xyz_enc"] = xyz_map.get(sku_meta.get("xyz_class", "Z"), 2)
#         row["vel_enc"] = vel_map.get(sku_meta.get("velocity_class", "Slow"), 2)

#         x = pd.DataFrame([row])[FEATURE_COLS]
#         pred = max(0.0, float(model.predict(x)[0]))
#         preds.append({"date": fd, "item_id": sku_id, "forecast": round(pred, 4)})
#         hist = pd.concat([hist, pd.Series([pred])], ignore_index=True)

#     return pd.DataFrame(preds)

# # Build future calendar (extend beyond training max)
# last_date    = sales_wide.index.max()
# future_dates_7  = pd.date_range(last_date + pd.Timedelta(1, "D"), periods=7,  freq="D")
# future_dates_30 = pd.date_range(last_date + pd.Timedelta(1, "D"), periods=30, freq="D")

# # Future calendar features — repeat last known week pattern as approximation
# # (In production: use actual forward calendar)
# def build_future_cal(dates):
#     fc = pd.DataFrame(index=dates)
#     fc["wday"]     = fc.index.dayofweek + 2  # approx M5 wday encoding
#     fc["month"]    = fc.index.month
#     fc["is_event"] = 0
#     fc["is_snap"]  = 0
#     return fc

# future_cal_7  = build_future_cal(future_dates_7)
# future_cal_30 = build_future_cal(future_dates_30)

# forecasts_7  = []
# forecasts_30 = []

# for i, sku in enumerate(sku_list):
#     hist_series = sales_wide[sku].reset_index(drop=True)
#     meta        = sku_meta_map.get(sku, {})
#     f7  = recursive_forecast(model, sku, hist_series, future_cal_7,  7,  meta)
#     f30 = recursive_forecast(model, sku, hist_series, future_cal_30, 30, meta)
#     forecasts_7.append(f7)
#     forecasts_30.append(f30)
#     if (i + 1) % 100 == 0:
#         print(f"    … {i+1}/{len(sku_list)} SKUs done")

# fc7_df  = pd.concat(forecasts_7,  ignore_index=True)
# fc30_df = pd.concat(forecasts_30, ignore_index=True)

# fc7_df.to_csv(OUT_DIR  / "forecast_7_days.csv",  index=False)
# fc30_df.to_csv(OUT_DIR / "forecast_30_days.csv", index=False)

# print(f"\n  Saved: forecast_7_days.csv   ({len(fc7_df):,} rows)")
# print(f"  Saved: forecast_30_days.csv  ({len(fc30_df):,} rows)")

# # ── 10i. Sample SKU forecast visualisations ───────────────────────────────────
# print("\n  Generating sample SKU forecast plots …")

# # Pick one SKU from each ABC class
# sample_skus = []
# for cls in ["A", "B", "C"]:
#     cands = sku_stats[sku_stats["abc_class"] == cls]["item_id"].values
#     if len(cands) > 0:
#         sample_skus.append(cands[0])

# for sku in sample_skus[:3]:
#     hist_ts  = sales_wide[sku].tail(90)
#     f30_sku  = fc30_df[fc30_df["item_id"] == sku].set_index("date")["forecast"]

#     fig, ax = plt.subplots(figsize=(14, 4))
#     ax.plot(hist_ts.index, hist_ts.values, color=PALETTE[0], lw=1.5,
#             label="Historical (last 90d)")
#     ax.plot(f30_sku.index, f30_sku.values, color=PALETTE[3], lw=2.0,
#             linestyle="--", marker="o", markersize=3, label="30-day Forecast")
#     ax.axvline(last_date, color="grey", linestyle=":", lw=1)
#     ax.set_title(f"SKU: {sku}  |  30-Day Demand Forecast", fontweight="bold")
#     ax.set_xlabel("Date"); ax.set_ylabel("Units")
#     ax.legend()
#     plt.tight_layout()
#     fig.savefig(FC_PLOT_DIR / f"forecast_{sku}.png", dpi=150)
#     plt.close()

# print(f"  Plots saved to: {FC_PLOT_DIR}/")

# # ─────────────────────────────────────────────────────────────────────────────
# # 11. PIPELINE SUMMARY
# # ─────────────────────────────────────────────────────────────────────────────
# print("\n" + "=" * 70)
# print("  PIPELINE COMPLETE — OUTPUT ARTIFACTS")
# print("=" * 70)
# print(f"""
#   outputs/
#   ├── eda_sku_features.csv          ← {len(eda_features)} SKUs × {len(feature_cols)} features
#   │                                   (ready for synthetic inventory + supplier generation)
#   ├── forecast_7_days.csv           ← 7-day forward forecasts ({len(sku_list)} SKUs)
#   ├── forecast_30_days.csv          ← 30-day forward forecasts ({len(sku_list)} SKUs)
#   ├── eda_plots/
#   │   ├── 01_dept_distribution.png
#   │   ├── 02_demand_distribution.png
#   │   ├── 03_aggregate_demand_trend.png
#   │   ├── 04_abc_xyz_matrix.png
#   │   ├── 05_seasonality.png
#   │   └── 06_price_analysis.png
#   └── forecast_plots/
#       ├── 00_feature_importance.png
#       └── forecast_<SKU>.png  (3 sample SKUs, one per ABC class)

#   Validation Metrics  →  RMSE: {rmse:.4f}  |  MAE: {mae:.4f}  |  MAPE: {mape:.2f}%
#   Training Time       →  {elapsed:.1f}s  (single CPU)
# """)
# print("  Next step: pass eda_sku_features.csv into Module 3 (Inventory Gap Detection)")
# print("=" * 70)

"""
=============================================================================
PROCUREMENT INTELLIGENCE SYSTEM v2 — EDA + DEMAND FORECASTING PIPELINE
=============================================================================
Dataset  : M5 reduced (CA_1 | FOODS_1, FOODS_2, HOUSEHOLD_1 | top SKUs | 730 days)
Improvements over v1:
  EDA       — Quantile-based XYZ, intermittency metrics, WMAPE, enhanced price
  Features  — Sparsity-aware lags, 90/180-day rolling, sale frequency
  Inventory — Lead-time-ready params, service-level safety stock, risk indicators
Outputs:
    eda_sku_features.csv
    forecast_7_days.csv
    forecast_30_days.csv
    eda_plots/
    forecast_plots/
=============================================================================
"""

# ─────────────────────────────────────────────────────────────────────────────
# 0. IMPORTS & CONFIG
# ─────────────────────────────────────────────────────────────────────────────
import warnings, os, time
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path
from scipy import stats

import lightgbm as lgb
from sklearn.metrics import mean_squared_error, mean_absolute_error

OUT_DIR      = Path("outputs")
EDA_PLOT_DIR = OUT_DIR / "eda_plots"
FC_PLOT_DIR  = OUT_DIR / "forecast_plots"
for d in [OUT_DIR, EDA_PLOT_DIR, FC_PLOT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
PALETTE = sns.color_palette("Set2", 10)

# Inventory constants
Z_95   = 1.645   # 95% service level
Z_98   = 2.054   # 98% service level
Z_99   = 2.326   # 99% service level
LT_MIN = 3       # minimum lead time (days) for risk calculations
LT_MED = 7       # assumed medium lead time
LT_MAX = 14      # assumed max lead time

print("=" * 70)
print("  PROCUREMENT INTELLIGENCE SYSTEM v2 — PIPELINE START")
print("=" * 70)

# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA LOADING
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/10] Loading datasets …")

sales_raw    = pd.read_csv("./data/sales_train_400sku_730days.csv")
prices_raw   = pd.read_csv("./data/sell_prices_400sku.csv")
calendar_raw = pd.read_csv("./data/calendar_730days.csv")

print(f"  sales    : {sales_raw.shape}")
print(f"  prices   : {prices_raw.shape}")
print(f"  calendar : {calendar_raw.shape}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. DATA WRANGLING
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/10] Reshaping to long format …")

day_cols = [c for c in sales_raw.columns if c.startswith("d_")]
id_cols  = [c for c in sales_raw.columns if not c.startswith("d_")]

sales_long = sales_raw.melt(
    id_vars    = id_cols,
    value_vars = day_cols,
    var_name   = "d",
    value_name = "sales"
)

calendar_raw["d"] = calendar_raw["d"].astype(str)
sales_long = sales_long.merge(
    calendar_raw[["d","date","wm_yr_wk","weekday","wday","month","year",
                  "event_name_1","event_type_1","event_name_2","event_type_2","snap_CA"]],
    on="d", how="left"
)
sales_long["date"] = pd.to_datetime(sales_long["date"])

sales_long = sales_long.merge(
    prices_raw[["store_id","item_id","wm_yr_wk","sell_price"]],
    on=["store_id","item_id","wm_yr_wk"], how="left"
)

sales_long["dept_id"] = sales_long["item_id"].str.rsplit("_", n=1).str[0]
sales_long["cat_id"]  = sales_long["item_id"].str.split("_").str[0]
sales_long.sort_values(["item_id","date"], inplace=True)
sales_long.reset_index(drop=True, inplace=True)

sku_list = sales_long["item_id"].unique()
print(f"  Long table: {sales_long.shape} | "
      f"{sales_long['date'].min().date()} → {sales_long['date'].max().date()}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. EDA — DATASET OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/10] EDA — Dataset Overview …")

dept_dist = sales_long.drop_duplicates("item_id")["dept_id"].value_counts()
missing   = sales_long.isnull().sum()

print(f"\n  Unique SKUs   : {len(sku_list)}")
print(f"  Date range    : {sales_long['date'].min().date()} → {sales_long['date'].max().date()}")
print(f"  Total rows    : {len(sales_long):,}")
print(f"\n  Department distribution:")
for dept, cnt in dept_dist.items():
    print(f"    {dept:<20}: {cnt} SKUs")
print(f"\n  Missing values:")
for col in ["sales","sell_price","date"]:
    pct = missing[col] / len(sales_long) * 100
    print(f"    {col:<20}: {missing[col]:,}  ({pct:.2f}%)")

# Dept bar chart
fig, ax = plt.subplots(figsize=(8,4))
dept_dist.plot(kind="bar", ax=ax, color=PALETTE[:len(dept_dist)], edgecolor="white")
ax.set_title("SKU Count by Department", fontweight="bold")
ax.set_xlabel("Department"); ax.set_ylabel("SKU Count")
ax.tick_params(axis="x", rotation=0)
plt.tight_layout()
fig.savefig(EDA_PLOT_DIR / "01_dept_distribution.png", dpi=150); plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 4. EDA — DEMAND ANALYSIS + INTERMITTENCY
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/10] EDA — Demand Analysis + Intermittency Metrics …")

# ── Per-SKU demand statistics ─────────────────────────────────────────────────
def adi(series):
    """Average Demand Interval — avg gap (days) between non-zero sales."""
    nz = np.where(series > 0)[0]
    if len(nz) < 2:
        return np.nan
    return np.mean(np.diff(nz))

def cv2(series):
    """Squared coefficient of variation of non-zero demand."""
    nz = series[series > 0]
    if len(nz) < 2:
        return np.nan
    return (nz.std() / nz.mean()) ** 2

sku_rows = []
for sku, grp in sales_long.groupby("item_id"):
    s = grp.sort_values("date")["sales"].values
    nz = s[s > 0]
    total     = s.sum()
    n         = len(s)
    mean_d    = s.mean()
    med_d     = np.median(s)
    std_d     = s.std()
    cv_val    = std_d / (mean_d + 1e-9)
    zero_rate = (s == 0).mean()
    sale_freq = (s > 0).mean()           # proportion of days with a sale
    adi_val   = adi(s)
    cv2_val   = cv2(pd.Series(s))
    p25, p75, p95 = np.percentile(s, [25, 75, 95])

    # Sale frequency over trailing windows (using last N days)
    sf_28 = (s[-28:] > 0).mean() if n >= 28 else (s > 0).mean()
    sf_90 = (s[-90:] > 0).mean() if n >= 90 else (s > 0).mean()
    nz28  = int((s[-28:] > 0).sum()) if n >= 28 else int((s > 0).sum())
    nz90  = int((s[-90:] > 0).sum()) if n >= 90 else int((s > 0).sum())

    sku_rows.append({
        "item_id": sku,
        "dept_id": sku.rsplit("_", 1)[0],
        "total_demand": total,
        "n_days": n,
        "mean_demand": mean_d,
        "median_demand": med_d,
        "std_demand": std_d,
        "cv": cv_val,
        "cv2": cv2_val,
        "adi": adi_val,
        "zero_rate": zero_rate,
        "sale_frequency": sale_freq,
        "sale_frequency_28": sf_28,
        "sale_frequency_90": sf_90,
        "non_zero_sales_28": nz28,
        "non_zero_sales_90": nz90,
        "p25": p25,
        "p75": p75,
        "p95": p95,
    })

sku_stats = pd.DataFrame(sku_rows)

agg = sales_long["sales"]
print(f"\n  Mean daily demand  : {agg.mean():.4f}")
print(f"  Median             : {agg.median():.4f}")
print(f"  Std Dev            : {agg.std():.4f}")
print(f"  P25 / P75          : {agg.quantile(0.25):.2f} / {agg.quantile(0.75):.2f}")
print(f"  P95                : {agg.quantile(0.95):.2f}")
print(f"  Zero-sales rate    : {(agg==0).mean()*100:.1f}%")

# ── Intermittency classification (ADI / CV²) ──────────────────────────────────
# Syntetos-Boylan-Croston classification:
#   ADI ≥ 1.32  AND  CV² < 0.49  → Intermittent
#   ADI ≥ 1.32  AND  CV² ≥ 0.49  → Lumpy
#   ADI < 1.32  AND  CV² < 0.49  → Smooth
#   ADI < 1.32  AND  CV² ≥ 0.49  → Erratic

def classify_demand_pattern(row):
    adi_v = row["adi"]
    cv2_v = row["cv2"]
    if pd.isna(adi_v) or pd.isna(cv2_v):
        return "Lumpy"        # single-sale SKUs → most conservative
    if adi_v >= 1.32 and cv2_v < 0.49:
        return "Intermittent"
    elif adi_v >= 1.32 and cv2_v >= 0.49:
        return "Lumpy"
    elif adi_v < 1.32 and cv2_v < 0.49:
        return "Smooth"
    else:
        return "Erratic"

sku_stats["demand_pattern"] = sku_stats.apply(classify_demand_pattern, axis=1)
print(f"\n  Demand pattern distribution:")
print(sku_stats["demand_pattern"].value_counts().to_string())

# Demand distribution plots
fig, axes = plt.subplots(1, 3, figsize=(16, 4))
axes[0].hist(sku_stats["mean_demand"], bins=40, color=PALETTE[0], edgecolor="white")
axes[0].set_title("Mean Daily Demand per SKU", fontweight="bold")
axes[0].set_xlabel("Mean Demand")

axes[1].hist(sku_stats["zero_rate"], bins=30, color=PALETTE[1], edgecolor="white")
axes[1].set_title("Zero-Sale Rate per SKU", fontweight="bold")
axes[1].set_xlabel("Proportion of Zero-Sale Days")

axes[2].scatter(sku_stats["adi"].clip(upper=20), sku_stats["cv2"].clip(upper=5),
                c=PALETTE[:4] * 100, alpha=0.4, s=15)
axes[2].axhline(0.49, color="red",  lw=1, ls="--", label="CV²=0.49")
axes[2].axvline(1.32, color="blue", lw=1, ls="--", label="ADI=1.32")
axes[2].set_title("ADI vs CV² — Demand Classification", fontweight="bold")
axes[2].set_xlabel("ADI (clipped @20)"); axes[2].set_ylabel("CV² (clipped @5)")
axes[2].legend(fontsize=8)
plt.tight_layout()
fig.savefig(EDA_PLOT_DIR / "02_demand_analysis.png", dpi=150); plt.close()

# Aggregate demand trend
daily_total = sales_long.groupby("date")["sales"].sum().reset_index()
fig, ax = plt.subplots(figsize=(14, 4))
ax.plot(daily_total["date"], daily_total["sales"], lw=1.2, color=PALETTE[2])
ax.set_title("Total Daily Demand — All SKUs", fontweight="bold")
ax.set_xlabel("Date"); ax.set_ylabel("Units Sold")
plt.tight_layout()
fig.savefig(EDA_PLOT_DIR / "03_aggregate_demand_trend.png", dpi=150); plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 5. EDA — ABC / XYZ SEGMENTATION (QUANTILE-BASED XYZ)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[5/10] EDA — ABC / XYZ Segmentation (quantile-based XYZ) …")

# ── ABC — cumulative revenue contribution ─────────────────────────────────────
price_mean = (
    sales_long.groupby("item_id")["sell_price"]
    .mean().reset_index().rename(columns={"sell_price":"mean_price"})
)
sku_stats = sku_stats.merge(price_mean, on="item_id", how="left")
sku_stats["revenue"] = sku_stats["total_demand"] * sku_stats["mean_price"].fillna(1)

sku_stats.sort_values("revenue", ascending=False, inplace=True)
sku_stats["cum_pct"] = sku_stats["revenue"].cumsum() / sku_stats["revenue"].sum()

def assign_abc(cum_pct):
    if cum_pct <= 0.70: return "A"
    elif cum_pct <= 0.90: return "B"
    else: return "C"

sku_stats["abc_class"] = sku_stats["cum_pct"].apply(assign_abc)

# ── XYZ — QUANTILE-BASED on CV (avoids 325/400 being Z) ─────────────────────
# Divide SKUs into thirds by their CV value.
# X = bottom 33rd percentile CV (most stable)
# Y = 33rd–66th percentile CV
# Z = top 33rd percentile CV (most variable)
# This guarantees roughly equal class sizes regardless of the CV distribution.
cv_p33 = sku_stats["cv"].quantile(0.33)
cv_p66 = sku_stats["cv"].quantile(0.66)

def assign_xyz_quantile(cv):
    if cv <= cv_p33: return "X"
    elif cv <= cv_p66: return "Y"
    else: return "Z"

sku_stats["xyz_class"]   = sku_stats["cv"].apply(assign_xyz_quantile)
sku_stats["abc_xyz"]     = sku_stats["abc_class"] + sku_stats["xyz_class"]

print(f"\n  CV thresholds — X ≤ {cv_p33:.3f}  |  Y ≤ {cv_p66:.3f}  |  Z > {cv_p66:.3f}")
print(f"\n  ABC distribution:\n{sku_stats['abc_class'].value_counts().sort_index().to_string()}")
print(f"\n  XYZ distribution:\n{sku_stats['xyz_class'].value_counts().sort_index().to_string()}")
print(f"\n  ABC-XYZ Matrix:")
matrix = pd.crosstab(sku_stats["abc_class"], sku_stats["xyz_class"])
print(matrix.to_string())

# ── Velocity classification ───────────────────────────────────────────────────
p33_d = sku_stats["mean_demand"].quantile(0.33)
p66_d = sku_stats["mean_demand"].quantile(0.66)
def assign_velocity(v):
    if v >= p66_d: return "Fast"
    elif v >= p33_d: return "Medium"
    else: return "Slow"
sku_stats["velocity_class"] = sku_stats["mean_demand"].apply(assign_velocity)

# ABC/XYZ plots
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
abc_counts = sku_stats["abc_class"].value_counts().sort_index()
abc_counts.plot(kind="bar", ax=axes[0], color=[PALETTE[3],PALETTE[4],PALETTE[5]],
                edgecolor="white")
axes[0].set_title("ABC Classification (Revenue-based)", fontweight="bold")
axes[0].set_xlabel("Class"); axes[0].set_ylabel("SKU Count")
axes[0].tick_params(axis="x", rotation=0)

heatmap_data = pd.crosstab(sku_stats["abc_class"], sku_stats["xyz_class"])
sns.heatmap(heatmap_data, annot=True, fmt="d", cmap="YlOrRd",
            ax=axes[1], linewidths=0.5)
axes[1].set_title("ABC–XYZ Matrix (Quantile-based XYZ)", fontweight="bold")
plt.tight_layout()
fig.savefig(EDA_PLOT_DIR / "04_abc_xyz_matrix.png", dpi=150); plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 6. EDA — SEASONALITY + EVENT ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[6/10] EDA — Seasonality & Event Analysis …")

dow_map = {1:"Sun",2:"Mon",3:"Tue",4:"Wed",5:"Thu",6:"Fri",7:"Sat"}
dow_demand = (
    sales_long.groupby("wday")["sales"].mean().reset_index().sort_values("wday")
)
dow_demand["dow_label"] = dow_demand["wday"].map(dow_map)
month_demand = sales_long.groupby("month")["sales"].mean().reset_index()

# Event impact — broken out by event type
event_impact = (
    sales_long.groupby(sales_long["event_name_1"].fillna("No Event"))["sales"]
    .agg(mean_sales="mean", n_days="count")
    .reset_index()
    .rename(columns={"event_name_1": "event"})
    .sort_values("mean_sales", ascending=False)
)
baseline = sales_long[sales_long["event_name_1"].isna()]["sales"].mean()
event_impact["lift_pct"] = (event_impact["mean_sales"] / baseline - 1) * 100

event_mask  = sales_long["event_name_1"].notna()
snap_demand = sales_long.groupby("snap_CA")["sales"].mean()
print(f"\n  Demand baseline (no event) : {baseline:.4f}")
print(f"  Demand on event days       : {sales_long[event_mask]['sales'].mean():.4f}")
print(f"  SNAP days avg demand       : {snap_demand.get(1, snap_demand.get(1.0, 0)):.4f}")
print(f"  Non-SNAP avg demand        : {snap_demand.get(0, snap_demand.get(0.0, 0)):.4f}")
print(f"\n  Top 5 events by demand lift:")
print(event_impact[event_impact["event"] != "No Event"].head(5)[
    ["event","mean_sales","lift_pct"]].to_string(index=False))

fig, axes = plt.subplots(1, 2, figsize=(14, 4))
axes[0].bar(dow_demand["dow_label"], dow_demand["sales"],
            color=PALETTE[:7], edgecolor="white")
axes[0].set_title("Average Demand by Day of Week", fontweight="bold")
axes[0].set_xlabel("Day"); axes[0].set_ylabel("Avg Units")

axes[1].bar(month_demand["month"], month_demand["sales"],
            color=PALETTE[:len(month_demand)], edgecolor="white")
axes[1].set_title("Average Demand by Month", fontweight="bold")
axes[1].set_xlabel("Month")
axes[1].xaxis.set_major_locator(mticker.MultipleLocator(1))
plt.tight_layout()
fig.savefig(EDA_PLOT_DIR / "05_seasonality.png", dpi=150); plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 7. EDA — PRICE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[7/10] EDA — Price Analysis …")

# Impute missing prices with SKU median
sales_long["sell_price"] = (
    sales_long.groupby("item_id")["sell_price"]
    .transform(lambda x: x.fillna(x.median()))
)
remaining_missing = sales_long["sell_price"].isna().sum()
print(f"  Missing prices after SKU-median imputation: {remaining_missing}")

price_stats = (
    sales_long.groupby("item_id")["sell_price"]
    .agg(price_mean="mean", price_std="std", price_min="min",
         price_max="max", price_median="median")
    .reset_index()
)
price_stats["price_range_pct"] = (
    (price_stats["price_max"] - price_stats["price_min"])
    / price_stats["price_mean"].replace(0, np.nan)
)
price_stats["price_cv"] = (
    price_stats["price_std"] / price_stats["price_mean"].replace(0, np.nan)
)

sku_stats = sku_stats.merge(
    price_stats[["item_id","price_mean","price_std",
                 "price_range_pct","price_cv","price_median"]],
    on="item_id", how="left"
)

print(f"  SKUs with price variation > 10%  : {(price_stats['price_range_pct']>0.10).sum()}")
print(f"  Median SKU price                 : ${price_stats['price_mean'].median():.2f}")
print(f"  Price range                      : ${price_stats['price_mean'].min():.2f} – ${price_stats['price_mean'].max():.2f}")

# Price correlation with demand
corr = sku_stats[["mean_demand","mean_price"]].corr().iloc[0,1]
print(f"  Price–Demand Pearson correlation : {corr:.4f}")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].scatter(sku_stats["mean_price"], sku_stats["mean_demand"],
                alpha=0.5, s=25, color=PALETTE[0])
axes[0].set_title(f"Price vs Mean Daily Demand  (r={corr:.3f})", fontweight="bold")
axes[0].set_xlabel("Mean Price ($)"); axes[0].set_ylabel("Mean Daily Demand")

axes[1].hist(price_stats["price_range_pct"].dropna(), bins=40,
             color=PALETTE[1], edgecolor="white")
axes[1].set_title("Price Range % per SKU", fontweight="bold")
axes[1].set_xlabel("(max−min)/mean"); axes[1].set_ylabel("Frequency")
plt.tight_layout()
fig.savefig(EDA_PLOT_DIR / "06_price_analysis.png", dpi=150); plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# 8. INVENTORY PARAMETER EXTRACTION (v2)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[8/10] Inventory Parameter Extraction (v2) …")

"""
Safety Stock formulas
─────────────────────
Standard (known demand, known LT):
  SS = Z × σ_d × √LT

With lead-time variability (used for procurement risk tier):
  SS_risk = Z × √(LT × σ_d² + d² × σ_LT²)
  We approximate σ_LT = (LT_MAX - LT_MIN) / 4  (range / 4 heuristic)

Reorder Point:
  ROP = d̄ × LT + SS

Days of Supply:
  DOS = current_inventory / d̄
  (here we output the denominator d̄ for downstream use)

Procurement Risk Tier:
  Based on demand pattern + CV + ABC class
"""

sigma_lt = (LT_MAX - LT_MIN) / 4   # ≈ 2.75 days std dev on lead time


PATTERN_MULTIPLIER = {
    "Smooth": 1.00,
    "Erratic": 1.05,
    "Intermittent": 1.15,
    "Lumpy": 1.30
}



def safety_stock(mean_d, std_d, lt, z):
    return z * std_d * np.sqrt(lt)

def safety_stock_lt_risk(mean_d, std_d, lt, z, s_lt):
    """Safety stock accounting for both demand AND lead-time variability."""
    return z * np.sqrt(lt * std_d**2 + mean_d**2 * s_lt**2)

def procurement_risk_tier(row):
    """
    3-tier procurement risk indicator:
      HIGH   — lumpy/intermittent C-class or high CV Z-class A-items
      MEDIUM — moderate variability, mid-tier ABC
      LOW    — smooth/stable, A-class reliable SKUs
    """
    if row["demand_pattern"] in ["Lumpy"] and row["abc_class"] == "C":
        return "HIGH"
    if row["xyz_class"] == "Z" and row["abc_class"] == "A":
        return "HIGH"
    if row["demand_pattern"] in ["Intermittent","Lumpy"]:
        return "MEDIUM"
    if row["xyz_class"] == "Z":
        return "MEDIUM"
    return "LOW"

sku_stats["avg_daily_demand"]         = sku_stats["mean_demand"]
sku_stats["demand_std"]               = sku_stats["std_demand"]
sku_stats["coefficient_of_variation"] = sku_stats["cv"]
sku_stats["pattern_multiplier"] = (
    sku_stats["demand_pattern"]
    .map(PATTERN_MULTIPLIER)
    .fillna(1.0)
)

# Safety stock at 3 service levels
sku_stats["safety_stock_95"] = (
    sku_stats.apply(
        lambda r: safety_stock(
            r["avg_daily_demand"],
            r["demand_std"],
            LT_MED,
            Z_95
        ),
        axis=1
    )
    * sku_stats["pattern_multiplier"]
).round(3)
sku_stats["safety_stock_98"] = (
    sku_stats.apply(
        lambda r: safety_stock(
            r["avg_daily_demand"],
            r["demand_std"],
            LT_MED,
            Z_98
        ),
        axis=1
    )
    * sku_stats["pattern_multiplier"]
).round(3)
sku_stats["safety_stock_99"] = (
    sku_stats.apply(
        lambda r: safety_stock(
            r["avg_daily_demand"],
            r["demand_std"],
            LT_MED,
            Z_99
        ),
        axis=1
    )
    * sku_stats["pattern_multiplier"]
).round(3)

# With LT variability (for risk-aware procurement)
sku_stats["safety_stock_lt_risk"] = sku_stats.apply(
    lambda r: safety_stock_lt_risk(r["avg_daily_demand"], r["demand_std"],
                                    LT_MED, Z_95, sigma_lt), axis=1
).round(3)

# Reorder points
sku_stats["reorder_point_lt_min"] = (
    sku_stats["avg_daily_demand"] * LT_MIN + sku_stats["safety_stock_95"]
).round(3)
sku_stats["reorder_point_lt_med"] = (
    sku_stats["avg_daily_demand"] * LT_MED + sku_stats["safety_stock_95"]
).round(3)
sku_stats["reorder_point_lt_max"] = (
    sku_stats["avg_daily_demand"] * LT_MAX + sku_stats["safety_stock_95"]
).round(3)

# Procurement risk
sku_stats["procurement_risk_tier"] = sku_stats.apply(procurement_risk_tier, axis=1)

# Additional lead-time-ready features
sku_stats["avg_order_qty_suggested"]  = (
    sku_stats["avg_daily_demand"] * 30
).round(2)                              # EOQ proxy: 30-day coverage

sku_stats["stockout_risk_score"] = (
    sku_stats["cv"] * (1 - sku_stats["sale_frequency"])
).round(4)                              # higher = more stockout-prone

sku_stats["replenishment_urgency"] = pd.cut(
    sku_stats["stockout_risk_score"],
    bins   = [-np.inf, 0.3, 0.7, np.inf],
    labels = ["Normal","Watch","Critical"]
)

print(f"\n  Procurement risk distribution:")
print(sku_stats["procurement_risk_tier"].value_counts().to_string())
print(f"\n  Replenishment urgency:")
print(sku_stats["replenishment_urgency"].value_counts().to_string())

# ─────────────────────────────────────────────────────────────────────────────
# 9. SAVE EDA FEATURE TABLE
# ─────────────────────────────────────────────────────────────────────────────
feature_cols = [
    # Identity
    "item_id", "dept_id",
    # Demand stats
    "avg_daily_demand", "median_demand", "demand_std",
    "coefficient_of_variation", "cv2", "adi",
    "total_demand", "p25", "p75", "p95",
    # Intermittency / sparsity
    "zero_rate", "sale_frequency",
    "sale_frequency_28", "sale_frequency_90",
    "non_zero_sales_28", "non_zero_sales_90",
    "demand_pattern",
    # Segmentation
    "abc_class", "xyz_class", "abc_xyz", "velocity_class",
    # Price
    "mean_price", "price_std", "price_cv", "price_range_pct", "revenue",
    # Inventory params
    "safety_stock_95", "safety_stock_98", "safety_stock_99",
    "safety_stock_lt_risk",
    "reorder_point_lt_min", "reorder_point_lt_med", "reorder_point_lt_max",
    "avg_order_qty_suggested",
    # Risk
    "procurement_risk_tier", "stockout_risk_score", "replenishment_urgency",
]

eda_features = sku_stats[feature_cols].copy()
eda_features.to_csv(OUT_DIR / "eda_sku_features.csv", index=False)
print(f"\n  Saved: eda_sku_features.csv  "
      f"({len(eda_features)} SKUs × {len(feature_cols)} features)")
print(eda_features.columns.to_list())
# ─────────────────────────────────────────────────────────────────────────────
# 10. DEMAND FORECASTING — LightGBM v2
# ─────────────────────────────────────────────────────────────────────────────
print("\n[10/10] Demand Forecasting — LightGBM v2 …")

"""
v2 FEATURE ADDITIONS over v1:
  days_since_last_sale   — measures recency of demand; critical for lumpy SKUs
  non_zero_sales_28/90   — non-zero count in trailing windows
  sale_frequency_28/90   — proportion of non-zero days (trailing)
  rolling_mean_90/180    — long-term trend anchors
  rolling_std_90/180     — long-horizon volatility
These features explicitly give the model sparsity information,
allowing it to distinguish a 0-demand day from a permanently dead SKU.
"""

# Build wide panel
sales_wide = sales_long.pivot_table(
    index="date", columns="item_id", values="sales", aggfunc="sum"
).fillna(0)

cal_feat = (
    sales_long[["date","wday","month","snap_CA","event_name_1"]]
    .drop_duplicates("date").set_index("date")
)
cal_feat["is_event"] = cal_feat["event_name_1"].notna().astype(int)
cal_feat["is_snap"]  = cal_feat["snap_CA"].fillna(0).astype(int)

LAGS       = [1, 2, 3, 7, 14, 28]
ROLL_MEAN  = [7, 14, 28, 90, 180]
ROLL_STD   = [7, 14, 28, 90, 180]
VAL_DAYS   = 30

FEATURE_COLS = (
    [f"lag_{l}"        for l in LAGS]
    + [f"roll_mean_{w}" for w in ROLL_MEAN]
    + [f"roll_std_{w}"  for w in ROLL_STD]
    + ["roll_mean_90_nz","roll_mean_180_nz"]   # rolling mean of non-zero only
    + ["days_since_last_sale"]
    + ["sale_freq_28","sale_freq_90"]
    + ["non_zero_28","non_zero_90"]
    + ["dow","month_feat","is_event","is_snap"]
    + ["abc_enc","xyz_enc","vel_enc","pattern_enc"]
    + ["adi_feat","cv2_feat","zero_rate_feat","sale_frequency_feat"]
    + ["price_std_feat","price_cv_feat","price_range_pct_feat"]
)

sku_meta_map = (
    sku_stats.set_index("item_id")[
        [
            "abc_class",
            "xyz_class",
            "velocity_class",
            "demand_pattern",
            "adi",
            "cv2",
            "zero_rate",
            "sale_frequency",
            "price_std",
            "price_cv",
            "price_range_pct",
            
        ]
    ].to_dict(orient="index")
)

ABC_ENC     = {"A":0,"B":1,"C":2}
XYZ_ENC     = {"X":0,"Y":1,"Z":2}
VEL_ENC     = {"Fast":0,"Medium":1,"Slow":2}
PATTERN_ENC = {"Smooth":0,"Erratic":1,"Intermittent":2,"Lumpy":3}

def build_features(ts: pd.DataFrame, sku_id: str, meta: dict) -> pd.DataFrame:
    df = ts.copy()
    df = df.join(cal_feat[["wday","month","is_event","is_snap"]])

    # Standard lags
    for lag in LAGS:
        df[f"lag_{lag}"] = df["sales"].shift(lag)

    # Rolling means/stds (all windows)
    for w in ROLL_MEAN:
        df[f"roll_mean_{w}"] = df["sales"].shift(1).rolling(w, min_periods=1).mean()
    for w in ROLL_STD:
        df[f"roll_std_{w}"]  = df["sales"].shift(1).rolling(w, min_periods=2).std().fillna(0)

    # Non-zero rolling means (captures true demand when it occurs)
    nz_series = df["sales"].where(df["sales"] > 0)
    df["roll_mean_90_nz"]  = nz_series.shift(1).rolling(90,  min_periods=1).mean().fillna(0)
    df["roll_mean_180_nz"] = nz_series.shift(1).rolling(180, min_periods=1).mean().fillna(0)

    # Days since last sale — key for intermittent demand
    def days_since_sale(s):
        out = np.full(len(s), np.nan)
        last = np.nan
        for i, v in enumerate(s):
            if i > 0:
                out[i] = (i - last) if not np.isnan(last) else np.nan
            if v > 0:
                last = i
        return out
    df["days_since_last_sale"] = days_since_sale(df["sales"].values)
    df["days_since_last_sale"] = df["days_since_last_sale"].fillna(
        df["days_since_last_sale"].median()
    ).shift(1)

    # Trailing sale frequency and non-zero counts
    is_nz = (df["sales"] > 0).astype(float).shift(1)
    df["sale_freq_28"] = is_nz.rolling(28,  min_periods=1).mean()
    df["sale_freq_90"] = is_nz.rolling(90,  min_periods=1).mean()
    df["non_zero_28"]  = is_nz.rolling(28,  min_periods=1).sum()
    df["non_zero_90"]  = is_nz.rolling(90,  min_periods=1).sum()

    # Calendar
    df["dow"]        = df["wday"]
    df["month_feat"] = df["month"]

    # SKU metadata encodings
    df["abc_enc"]     = ABC_ENC.get(meta.get("abc_class","C"), 2)
    df["xyz_enc"]     = XYZ_ENC.get(meta.get("xyz_class","Z"), 2)
    df["vel_enc"]     = VEL_ENC.get(meta.get("velocity_class","Slow"), 2)
    df["pattern_enc"] = PATTERN_ENC.get(meta.get("demand_pattern","Lumpy"), 3)
    df["adi_feat"] = meta.get("adi", 0)
    df["cv2_feat"] = meta.get("cv2", 0)
    df["zero_rate_feat"] = meta.get("zero_rate", 0)
    df["sale_frequency_feat"] = meta.get("sale_frequency", 0)
    df["price_std_feat"] = meta.get("price_std", 0)
    df["price_cv_feat"] = meta.get("price_cv", 0)
    df["price_range_pct_feat"] = meta.get("price_range_pct", 0)

    df.dropna(subset=FEATURE_COLS, inplace=True)
    return df

print("  Engineering features for all SKUs …")
all_dfs = []
for sku in sku_list:
    ts   = sales_wide[[sku]].rename(columns={sku:"sales"})
    meta = sku_meta_map.get(sku, {})
    df_f = build_features(ts, sku, meta)
    df_f["item_id"] = sku
    all_dfs.append(df_f)

panel = pd.concat(all_dfs).reset_index().rename(columns={"index":"date"})
panel["date"] = pd.to_datetime(panel["date"])
print(f"  Panel shape: {panel.shape}")

# Train / val split
max_date   = panel["date"].max()
val_cutoff = max_date - pd.Timedelta(days=VAL_DAYS)
train_df   = panel[panel["date"] <= val_cutoff]
val_df     = panel[panel["date"] >  val_cutoff]
X_tr, y_tr = train_df[FEATURE_COLS], train_df["sales"]
X_va, y_va = val_df[FEATURE_COLS],   val_df["sales"]
print(f"  Train: {len(train_df):,}  |  Val: {len(val_df):,}")

# ── LightGBM with Tweedie objective (handles zero-inflation) ─────────────────
print("  Training LightGBM (Tweedie objective) …")
t0 = time.time()

params = {
    "objective"             : "tweedie",    # ← zero-inflated distribution
    "tweedie_variance_power": 1.5,          # 1=Poisson, 2=Gamma; 1.5=balanced
    "metric"                : "rmse",
    "n_estimators"          : 1000,
    "learning_rate"         : 0.04,
    "num_leaves"            : 127,
    "min_child_samples"     : 20,
    "feature_fraction"      : 0.75,
    "bagging_fraction"      : 0.75,
    "bagging_freq"          : 5,
    "reg_alpha"             : 0.1,
    "reg_lambda"            : 0.2,
    "n_jobs"                : -1,
    "verbose"               : -1,
    "random_state"          : 42,
}

model = lgb.LGBMRegressor(**params)
model.fit(
    X_tr, y_tr,
    eval_set  = [(X_va, y_va)],
    callbacks = [lgb.early_stopping(60, verbose=False),
                 lgb.log_evaluation(period=-1)],
)
elapsed = time.time() - t0
print(f"  Done in {elapsed:.1f}s  |  Best iteration: {model.best_iteration_}")

# ── Validation metrics ────────────────────────────────────────────────────────
val_pred = np.maximum(0, model.predict(X_va))

rmse     = np.sqrt(mean_squared_error(y_va, val_pred))
mae      = mean_absolute_error(y_va, val_pred)
nz_mask  = y_va > 0
mape     = np.mean(np.abs((y_va[nz_mask] - val_pred[nz_mask]) / y_va[nz_mask])) * 100

# WMAPE — weighted by actual demand (penalises errors on high-demand days more)
wmape    = (np.abs(y_va - val_pred).sum() / y_va.sum()) * 100

# Per-SKU RMSE distribution
val_df_copy         = val_df.copy()
val_df_copy["pred"] = val_pred
sku_rmse = (
    val_df_copy.groupby("item_id")
    .apply(lambda g: np.sqrt(mean_squared_error(g["sales"], g["pred"])))
    .reset_index(name="sku_rmse")
)

print(f"\n  ── Validation Metrics ────────────────────────────────")
print(f"  RMSE            : {rmse:.4f}")
print(f"  MAE             : {mae:.4f}")
print(f"  MAPE            : {mape:.2f}%  (non-zero days only)")
print(f"  WMAPE           : {wmape:.2f}%  (demand-weighted — headline metric)")
print(f"\n  Per-SKU RMSE — p25/p50/p75/p90:")
q = sku_rmse["sku_rmse"].quantile([0.25,0.5,0.75,0.90])
print(f"    {q[0.25]:.3f} / {q[0.5]:.3f} / {q[0.75]:.3f} / {q[0.90]:.3f}")

# Feature importance
imp_df = pd.DataFrame({
    "feature"    : FEATURE_COLS,
    "importance" : model.feature_importances_
}).sort_values("importance", ascending=True).tail(20)

fig, ax = plt.subplots(figsize=(9, 7))
ax.barh(imp_df["feature"], imp_df["importance"], color=PALETTE[2])
ax.set_title("Top-20 Feature Importances (LightGBM Tweedie)", fontweight="bold")
ax.set_xlabel("Importance Score")
plt.tight_layout()
fig.savefig(FC_PLOT_DIR / "00_feature_importance.png", dpi=150); plt.close()

# Per-SKU RMSE distribution plot
fig, ax = plt.subplots(figsize=(9, 4))
ax.hist(sku_rmse["sku_rmse"], bins=40, color=PALETTE[0], edgecolor="white")
ax.set_title("Per-SKU Validation RMSE Distribution", fontweight="bold")
ax.set_xlabel("RMSE"); ax.set_ylabel("SKU Count")
ax.axvline(q[0.5], color="red", ls="--", label=f"Median={q[0.5]:.3f}")
ax.legend()
plt.tight_layout()
fig.savefig(FC_PLOT_DIR / "01_sku_rmse_distribution.png", dpi=150); plt.close()

# ── Recursive multi-step forecasting ─────────────────────────────────────────
print("\n  Generating forecasts …")

last_date = sales_wide.index.max()

def build_future_cal(dates):
    fc = pd.DataFrame(index=dates)
    fc["wday"]     = fc.index.dayofweek + 2
    fc["month"]    = fc.index.month
    fc["is_event"] = 0
    fc["is_snap"]  = 0
    return fc

future_cal_7  = build_future_cal(pd.date_range(last_date + pd.Timedelta(1,"D"), periods=7))
future_cal_30 = build_future_cal(pd.date_range(last_date + pd.Timedelta(1,"D"), periods=30))

def recursive_forecast(model, sku_id, history, future_cal, n_steps, meta):
    hist = list(history.values)
    preds = []
    n = len(hist)
    future_dates = future_cal.index[:n_steps]

    for step, fd in enumerate(future_dates):
        row = {}
        h = np.array(hist)

        # Lags
        for lag in LAGS:
            row[f"lag_{lag}"] = h[-lag] if lag <= len(h) else 0

        # Rolling means/stds
        for w in ROLL_MEAN:
            sl = h[-w:] if w <= len(h) else h
            row[f"roll_mean_{w}"] = sl.mean()
        for w in ROLL_STD:
            sl = h[-w:] if w <= len(h) else h
            row[f"roll_std_{w}"]  = sl.std() if len(sl) > 1 else 0

        # Non-zero rolling means
        nz_90  = h[-90:][ h[-90:] > 0] if len(h) >= 90 else h[h > 0]
        nz_180 = h[-180:][h[-180:] > 0] if len(h) >= 180 else h[h > 0]
        row["roll_mean_90_nz"]  = nz_90.mean()  if len(nz_90)  > 0 else 0
        row["roll_mean_180_nz"] = nz_180.mean() if len(nz_180) > 0 else 0

        # Days since last sale
        nz_idx = np.where(h > 0)[0]
        row["days_since_last_sale"] = (len(h) - 1 - nz_idx[-1]) if len(nz_idx) > 0 else len(h)

        # Trailing sale frequencies
        for key, w in [("sale_freq_28", 28), ("sale_freq_90", 90),
                        ("non_zero_28", 28), ("non_zero_90", 90)]:
            sl = h[-w:] if w <= len(h) else h
            nz_count = (sl > 0).sum()
            if "freq" in key:
                row[key] = nz_count / len(sl)
            else:
                row[key] = float(nz_count)

        # Calendar
        row["dow"]        = future_cal.loc[fd, "wday"]
        row["month_feat"] = future_cal.loc[fd, "month"]
        row["is_event"]   = int(future_cal.loc[fd, "is_event"])
        row["is_snap"]    = int(future_cal.loc[fd, "is_snap"])

        # Encodings
        row["abc_enc"]     = ABC_ENC.get(meta.get("abc_class","C"), 2)
        row["xyz_enc"]     = XYZ_ENC.get(meta.get("xyz_class","Z"), 2)
        row["vel_enc"]     = VEL_ENC.get(meta.get("velocity_class","Slow"), 2)
        row["pattern_enc"] = PATTERN_ENC.get(meta.get("demand_pattern","Lumpy"), 3)
            # Intermittency features
        row["adi_feat"] = meta.get("adi", 0)
        row["cv2_feat"] = meta.get("cv2", 0)
        row["zero_rate_feat"] = meta.get("zero_rate", 0)
        row["sale_frequency_feat"] = meta.get("sale_frequency", 0)

        # Price profile features
        row["price_std_feat"] = meta.get("price_std", 0)
        row["price_cv_feat"] = meta.get("price_cv", 0)
        row["price_range_pct_feat"] = meta.get("price_range_pct", 0)

        x    = pd.DataFrame([row])[FEATURE_COLS]
        pred = max(0.0, float(model.predict(x)[0]))
        preds.append({"date": fd, "item_id": sku_id, "forecast": round(pred, 4)})
        hist.append(pred)

    return pd.DataFrame(preds)

forecasts_7, forecasts_30 = [], []
for i, sku in enumerate(sku_list):
    hist_series = sales_wide[sku]
    meta        = sku_meta_map.get(sku, {})
    forecasts_7.append(recursive_forecast(model, sku, hist_series, future_cal_7,  7,  meta))
    forecasts_30.append(recursive_forecast(model, sku, hist_series, future_cal_30, 30, meta))
    if (i + 1) % 100 == 0:
        print(f"    … {i+1}/{len(sku_list)} SKUs done")

fc7_df  = pd.concat(forecasts_7,  ignore_index=True)
fc30_df = pd.concat(forecasts_30, ignore_index=True)
fc7_df.to_csv(OUT_DIR  / "forecast_7_days.csv",  index=False)
fc30_df.to_csv(OUT_DIR / "forecast_30_days.csv", index=False)
print(f"\n  Saved: forecast_7_days.csv   ({len(fc7_df):,} rows)")
print(f"  Saved: forecast_30_days.csv  ({len(fc30_df):,} rows)")

# ── Sample SKU forecast plots ─────────────────────────────────────────────────
print("  Generating sample forecast plots …")
sample_skus = []
for cls in ["A","B","C"]:
    cands = sku_stats[sku_stats["abc_class"] == cls]["item_id"].values
    if len(cands):
        sample_skus.append(cands[0])

for sku in sample_skus[:3]:
    hist_ts = sales_wide[sku].tail(90)
    f30     = fc30_df[fc30_df["item_id"] == sku].set_index("date")["forecast"]
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.bar(hist_ts.index, hist_ts.values, color=PALETTE[0], alpha=0.6,
           width=0.8, label="Historical (last 90d)")
    ax.plot(f30.index, f30.values, color=PALETTE[3], lw=2, marker="o",
            markersize=3, label="30-day Forecast")
    ax.axvline(last_date, color="grey", ls=":", lw=1)
    meta_row  = sku_stats[sku_stats["item_id"] == sku].iloc[0]
    ax.set_title(
        f"{sku}  |  ABC:{meta_row['abc_class']}  XYZ:{meta_row['xyz_class']}"
        f"  Pattern:{meta_row['demand_pattern']}  Velocity:{meta_row['velocity_class']}",
        fontweight="bold"
    )
    ax.set_xlabel("Date"); ax.set_ylabel("Units")
    ax.legend()
    plt.tight_layout()
    fig.savefig(FC_PLOT_DIR / f"forecast_{sku}.png", dpi=150); plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print(imp_df.sort_values(
    "importance",
    ascending=False
).head(20).to_string(index=False))
print("\n" + "=" * 70)
print("  PIPELINE v2 COMPLETE")
print("=" * 70)
print(f"""
  Validation  →  RMSE: {rmse:.4f}  MAE: {mae:.4f}
                 MAPE: {mape:.2f}% (non-zero)  WMAPE: {wmape:.2f}% (headline)
  Training    →  {elapsed:.1f}s  |  {model.best_iteration_} trees  |  Tweedie objective

  outputs/
  ├── eda_sku_features.csv          ← {len(eda_features)} SKUs × {len(feature_cols)} features
  ├── forecast_7_days.csv           ← {len(fc7_df):,} rows
  ├── forecast_30_days.csv          ← {len(fc30_df):,} rows
  ├── eda_plots/  (6 charts)
  └── forecast_plots/
      ├── 00_feature_importance.png
      ├── 01_sku_rmse_distribution.png
      └── forecast_<SKU>.png  ×3

  Next → Module 3: Inventory Gap Detection
         inputs: eda_sku_features.csv + forecast_30_days.csv
""")
print("=" * 70)