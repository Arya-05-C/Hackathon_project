import os
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from schemas import (
    DashboardResponse, DistributionEntry, ShortageSKUEntry,
    WorkbenchItem, SKUDetailsResponse, SupplierInfo,
    RankedSupplier, AllocationEntry, OptimizationResponse
)

# ==========================================================
# FILE PATH CONFIGURATION (ROBUST & LOCATION-AGNOSTIC)
# ==========================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # sprint 2 root
OUTPUTS_DIR = BASE_DIR / "outputs"

GAPS_FILE = OUTPUTS_DIR / "inventory_gaps.csv"
PRODUCT_FILE = OUTPUTS_DIR / "product_master.csv"
MAPPING_FILE = OUTPUTS_DIR / "supplier_item_mapping.csv"
SUPPLIER_FILE = BASE_DIR / "supplier_master.csv"

# ==========================================================
# DATA LOADING UTILITIES
# ==========================================================

def load_inventory_gaps_enriched() -> pd.DataFrame:
    """Loads inventory_gaps.csv joined with product_master.csv."""
    if not GAPS_FILE.exists():
        raise FileNotFoundError(f"inventory_gaps.csv not found at {GAPS_FILE}")
    if not PRODUCT_FILE.exists():
        raise FileNotFoundError(f"product_master.csv not found at {PRODUCT_FILE}")
    
    gaps_df = pd.read_csv(GAPS_FILE)
    product_df = pd.read_csv(PRODUCT_FILE)
    
    # Merge gaps with product master information
    merged = gaps_df.merge(
        product_df[["item_id", "product_name", "brand", "unit_size", "dept_id"]],
        on="item_id",
        how="left"
    )
    
    # Fill NAs
    merged["product_name"] = merged["product_name"].fillna("Unknown Product")
    merged["brand"] = merged["brand"].fillna("Generic")
    merged["unit_size"] = merged["unit_size"].fillna("N/A")
    merged["dept_id"] = merged["dept_id"].fillna("OTHER")
    
    return merged

def get_dashboard_data() -> DashboardResponse:
    """Calculates dashboard KPIs and chart distributions."""
    df = load_inventory_gaps_enriched()
    
    # Calculate stats
    total_skus = int(df["item_id"].nunique())
    procurement_alerts = int((df["procurement_alert"] == "YES").sum())
    procurement_triggers = int((df["procurement_trigger"] == "YES").sum())
    emergency_procurements = int((df["procurement_category"] == "Emergency").sum())
    total_shortage_quantity = int(df["shortage_quantity"].sum())
    total_recommended_po_qty = int(df["recommended_po_qty"].sum())
    total_revenue_at_risk = round(df["revenue_at_risk"].sum(),2)
    
    # Priority Distribution
    priority_counts = df["procurement_priority"].value_counts()
    priority_dist = [
        DistributionEntry(name=str(k), value=int(v))
        for k, v in priority_counts.items()
    ]
    
    # Category Distribution
    category_counts = df["procurement_category"].value_counts()
    category_dist = [
        DistributionEntry(name=str(k), value=int(v))
        for k, v in category_counts.items()
    ]
    
    # Department Distribution
    dept_counts = df["dept_id"].value_counts()
    dept_dist = [
        DistributionEntry(name=str(k), value=int(v))
        for k, v in dept_counts.items()
    ]
    
    # Top 10 Shortage SKUs
    top_shortage_df = df.sort_values(by="shortage_quantity", ascending=False).head(10)
    top_shortage_skus = [
        ShortageSKUEntry(
            item_id=str(row["item_id"]),
            product_name=str(row["product_name"]),
            shortage_quantity=int(row["shortage_quantity"]),
            dept_id=str(row["dept_id"])
        )
        for _, row in top_shortage_df.iterrows()
    ]
    
    return DashboardResponse(
        total_skus=total_skus,
        procurement_alerts=procurement_alerts,
        procurement_triggers=procurement_triggers,
        emergency_procurements=emergency_procurements,
        total_shortage_quantity=total_shortage_quantity,
        total_recommended_po_qty=total_recommended_po_qty,
        revenue_at_risk=total_revenue_at_risk,
        priority_distribution=priority_dist,
        category_distribution=category_dist,
        department_distribution=dept_dist,
        top_shortage_skus=top_shortage_skus
    )

def get_procurement_items(
    priority: Optional[str] = None,
    category: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None
) -> List[WorkbenchItem]:
    """Returns a filtered list of items for the procurement workbench table."""
    df = load_inventory_gaps_enriched()
    
    # Apply filters
    if priority:
        df = df[df["procurement_priority"].str.lower() == priority.lower()]
    if category:
        df = df[df["procurement_category"].str.lower() == category.lower()]
    if department:
        df = df[df["dept_id"].str.lower() == department.lower()]
    if search:
        search_lower = search.lower()
        df = df[
            df["product_name"].str.lower().str.contains(search_lower) | 
            df["item_id"].str.lower().str.contains(search_lower)
        ]
        
    items = []
    for _, row in df.iterrows():
        items.append(
            WorkbenchItem(
                item_id=str(row["item_id"]),
                product_name=str(row["product_name"]),
                dept_id=str(row["dept_id"]),
                available_inventory=int(row["available_inventory"]),
                forecast_30d=float(row["forecast_30d"]),
                shortage_quantity=int(row["shortage_quantity"]),
                procurement_priority=str(row["procurement_priority"]),
                procurement_category=str(row["procurement_category"]),
                procurement_reason=str(row["procurement_reason"]),
                recommended_po_qty=int(row["recommended_po_qty"])
            )
        )
    return items

def get_sku_details(item_id: str) -> Optional[SKUDetailsResponse]:
    """Retrieves detailed SKU info and its candidate suppliers list."""
    df = load_inventory_gaps_enriched()
    sku_row = df[df["item_id"] == item_id]
    
    if sku_row.empty:
        return None
    
    row = sku_row.iloc[0]
    
    # Load candidate suppliers for this item
    suppliers_list = []
    if MAPPING_FILE.exists():
        mappings = pd.read_csv(MAPPING_FILE)
        item_mappings = mappings[mappings["item_id"] == item_id]
        
        # Load supplier master to get names
        supplier_master = pd.read_csv(SUPPLIER_FILE) if SUPPLIER_FILE.exists() else pd.DataFrame()
        
        for _, map_row in item_mappings.iterrows():
            supplier_id = str(map_row["supplier_id"])
            
            # Lookup supplier name from master or fallback to mapping
            s_name = f"Supplier {supplier_id}"
            if not supplier_master.empty:
                match = supplier_master[supplier_master["supplier_id"] == supplier_id]
                if not match.empty:
                    s_name = str(match.iloc[0]["supplier_name"])
            
            suppliers_list.append(
                SupplierInfo(
                    supplier_id=supplier_id,
                    supplier_name=s_name,
                    supplier_type=str(map_row["supplier_type"]),
                    supplier_price=float(map_row["supplier_price"]),
                    lead_time_days=int(map_row["lead_time_days"]),
                    reliability_score=int(map_row["reliability_score"]),
                    quality_score=int(map_row["quality_score"]),
                    fill_rate=int(map_row["fill_rate"]),
                    risk_score=int(map_row["risk_score"]),
                    capacity_units=int(map_row["capacity_units"])
                )
            )
            print("Revenue:", row["revenue_at_risk"])
    return SKUDetailsResponse(
        item_id=str(row["item_id"]),
        product_name=str(row["product_name"]),
        brand=str(row["brand"]),
        unit_size=str(row["unit_size"]),
        dept_id=str(row["dept_id"]),
        available_inventory=int(row["available_inventory"]),
        forecast_7d=float(row["forecast_7d"]),
        forecast_30d=float(row["forecast_30d"]),
        days_until_stockout=float(row["days_until_stockout"]),
        procurement_priority=str(row["procurement_priority"]),
        procurement_reason=str(row["procurement_reason"]),
        recommended_po_qty=int(row["recommended_po_qty"]),
        revenue_at_risk=float(row["revenue_at_risk"]),
        inventory_risk_score=float(row["inventory_risk_score"]),
        projected_stockout_date=str(row["projected_stockout_date"]),
        suppliers=suppliers_list
    )

# ==========================================================
# DETERMINISTIC SUPPLIER RANKING LOGIC
# ==========================================================

def get_ranked_suppliers(
    item_id: str,
    cost_weight: float,
    lead_time_weight: float,
    reliability_weight: float,
    quality_weight: float,
    risk_weight: float
) -> List[RankedSupplier]:
    """Ranks candidates based on weights, normalized to 100%."""
    if not MAPPING_FILE.exists():
        return []
        
    mappings = pd.read_csv(MAPPING_FILE)
    item_mappings = mappings[mappings["item_id"] == item_id].copy()
    
    if item_mappings.empty:
        return []
        
    # Merge supplier master for names
    if SUPPLIER_FILE.exists():
        supplier_master = pd.read_csv(SUPPLIER_FILE)
        item_mappings = item_mappings.merge(
            supplier_master[["supplier_id", "supplier_name"]],
            on="supplier_id",
            how="left"
        )
    else:
        item_mappings["supplier_name"] = "Supplier " + item_mappings["supplier_id"]
        
    item_mappings["supplier_name"] = item_mappings["supplier_name"].fillna("Unknown Supplier")
    
    # ------------------------------------------------------
    # Normalization of Weights
    # ------------------------------------------------------
    total_weight = cost_weight + lead_time_weight + reliability_weight + quality_weight + risk_weight
    if total_weight == 0:
        w_cost = w_lt = w_rel = w_qual = w_risk = 0.2
    else:
        w_cost = cost_weight / total_weight
        w_lt = lead_time_weight / total_weight
        w_rel = reliability_weight / total_weight
        w_qual = quality_weight / total_weight
        w_risk = risk_weight / total_weight
        
    # ------------------------------------------------------
    # Normalization of Raw Metrics relative to local pool
    # ------------------------------------------------------
    # Price (Lower is better)
    max_price = item_mappings["supplier_price"].max()
    min_price = item_mappings["supplier_price"].min()
    if max_price == min_price:
        item_mappings["cost_score"] = 100.0
    else:
        item_mappings["cost_score"] = ((max_price - item_mappings["supplier_price"]) / (max_price - min_price)) * 100.0
        
    # Lead Time (Lower is better)
    max_lt = item_mappings["lead_time_days"].max()
    min_lt = item_mappings["lead_time_days"].min()
    if max_lt == min_lt:
        item_mappings["lead_time_score"] = 100.0
    else:
        item_mappings["lead_time_score"] = ((max_lt - item_mappings["lead_time_days"]) / (max_lt - min_lt)) * 100.0
        
    # Reliability (Higher is better, absolute score 0-100)
    item_mappings["reliability_score_norm"] = item_mappings["reliability_score"].astype(float)
    
    # Quality (Higher is better, absolute score 0-100)
    item_mappings["quality_score_norm"] = item_mappings["quality_score"].astype(float)
    
    # Risk (Lower is better, raw risk is 0-100, so score = 100 - risk)
    item_mappings["risk_score_norm"] = 100.0 - item_mappings["risk_score"].astype(float)
    
    # ------------------------------------------------------
    # Compute Final Score
    # ------------------------------------------------------
    item_mappings["supplier_score"] = (
        item_mappings["cost_score"] * w_cost +
        item_mappings["lead_time_score"] * w_lt +
        item_mappings["reliability_score_norm"] * w_rel +
        item_mappings["quality_score_norm"] * w_qual +
        item_mappings["risk_score_norm"] * w_risk
    )
    
    # Sort descending by final score
    ranked_df = item_mappings.sort_values(by="supplier_score", ascending=False)
    
    results = []
    for _, row in ranked_df.iterrows():
        results.append(
            RankedSupplier(
                supplier_id=str(row["supplier_id"]),
                supplier_name=str(row["supplier_name"]),
                supplier_type=str(row["supplier_type"]),
                supplier_price=float(row["supplier_price"]),
                lead_time_days=int(row["lead_time_days"]),
                reliability_score=int(row["reliability_score"]),
                quality_score=int(row["quality_score"]),
                risk_score=int(row["risk_score"]),
                capacity_units=int(row["capacity_units"]),
                cost_score=float(row["cost_score"]),
                lead_time_score=float(row["lead_time_score"]),
                reliability_score_norm=float(row["reliability_score_norm"]),
                quality_score_norm=float(row["quality_score_norm"]),
                risk_score_norm=float(row["risk_score_norm"]),
                supplier_score=round(float(row["supplier_score"]), 2)
            )
        )
    return results

# ==========================================================
# QUANTITY ALLOCATION OPTIMIZATION
# ==========================================================

def allocate_procurement(
    item_id: str,
    recommended_po_qty: int,
    cost_weight: float,
    lead_time_weight: float,
    reliability_weight: float,
    quality_weight: float,
    risk_weight: float
) -> OptimizationResponse:
    """Allocates required quantity greedily to highest-scoring suppliers."""
    # First, get ranked list of suppliers
    ranked = get_ranked_suppliers(
        item_id=item_id,
        cost_weight=cost_weight,
        lead_time_weight=lead_time_weight,
        reliability_weight=reliability_weight,
        quality_weight=quality_weight,
        risk_weight=risk_weight
    )
    
    allocations = []
    remaining_qty = recommended_po_qty
    total_spend = 0.0
    
    for supplier in ranked:
        if remaining_qty <= 0:
            allocated = 0
        else:
            allocated = min(remaining_qty, supplier.capacity_units)
            
        remaining_qty -= allocated
        spend = allocated * supplier.supplier_price
        total_spend += spend
        
        allocation_pct = (allocated / recommended_po_qty * 100.0) if recommended_po_qty > 0 else 0.0
        
        allocations.append(
            AllocationEntry(
                supplier_id=supplier.supplier_id,
                supplier_name=supplier.supplier_name,
                allocated_qty=allocated,
                allocation_pct=round(allocation_pct, 2),
                supplier_price=supplier.supplier_price,
                spend=round(spend, 2),
                lead_time_days=supplier.lead_time_days,
                reliability_score=supplier.reliability_score,
                capacity_units=supplier.capacity_units
            )
        )
        
    return OptimizationResponse(
        item_id=item_id,
        recommended_po_qty=recommended_po_qty,
        allocations=allocations,
        estimated_total_cost=round(total_spend, 2),
        unallocated_qty=max(0, remaining_qty)
    )
