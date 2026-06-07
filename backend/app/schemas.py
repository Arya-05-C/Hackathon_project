from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# ==========================================================
# DASHBOARD SCHEMAS
# ==========================================================

class DistributionEntry(BaseModel):
    name: str
    value: int

class ShortageSKUEntry(BaseModel):
    item_id: str
    product_name: str
    shortage_quantity: int
    dept_id: str

class DashboardResponse(BaseModel):
    total_skus: int
    procurement_alerts: int
    procurement_triggers: int
    emergency_procurements: int
    total_shortage_quantity: int
    total_recommended_po_qty: int
    revenue_at_risk: float
    priority_distribution: List[DistributionEntry]
    category_distribution: List[DistributionEntry]
    department_distribution: List[DistributionEntry]
    top_shortage_skus: List[ShortageSKUEntry]

# ==========================================================
# WORKBENCH SCHEMAS
# ==========================================================

class WorkbenchItem(BaseModel):
    item_id: str
    product_name: str
    dept_id: str
    available_inventory: int
    forecast_30d: float
    shortage_quantity: int
    procurement_priority: str
    procurement_category: str
    procurement_reason: str
    recommended_po_qty: int

# ==========================================================
# SKU DETAILS SCHEMAS
# ==========================================================

class SupplierInfo(BaseModel):
    supplier_id: str
    supplier_name: str
    supplier_type: str
    supplier_price: float
    lead_time_days: int
    reliability_score: int
    quality_score: int
    fill_rate: int
    risk_score: int
    capacity_units: int

class SKUDetailsResponse(BaseModel):
    item_id: str
    product_name: str
    brand: str
    unit_size: str
    dept_id: str
    available_inventory: int
    forecast_7d: float
    forecast_30d: float
    days_until_stockout: float
    procurement_priority: str
    procurement_reason: str
    recommended_po_qty: int
    revenue_at_risk: float
    inventory_risk_score: float
    projected_stockout_date: str
    suppliers: List[SupplierInfo]

# ==========================================================
# RECOMMENDATION & OPTIMIZATION SCHEMAS
# ==========================================================

class SupplierWeights(BaseModel):
    cost_weight: float = Field(default=20.0, ge=0.0)
    lead_time_weight: float = Field(default=20.0, ge=0.0)
    reliability_weight: float = Field(default=20.0, ge=0.0)
    quality_weight: float = Field(default=20.0, ge=0.0)
    risk_weight: float = Field(default=20.0, ge=0.0)

class RankSuppliersRequest(SupplierWeights):
    item_id: str

class RankedSupplier(BaseModel):
    supplier_id: str
    supplier_name: str
    supplier_type: str
    supplier_price: float
    lead_time_days: int
    reliability_score: int
    quality_score: int
    risk_score: int
    capacity_units: int
    cost_score: float
    lead_time_score: float
    reliability_score_norm: float
    quality_score_norm: float
    risk_score_norm: float
    supplier_score: float

class OptimizeProcurementRequest(SupplierWeights):
    item_id: str
    recommended_po_qty: int = Field(ge=0)

class AllocationEntry(BaseModel):
    supplier_id: str
    supplier_name: str
    allocated_qty: int
    allocation_pct: float
    supplier_price: float
    spend: float
    lead_time_days: int
    reliability_score: int
    capacity_units: int

class OptimizationResponse(BaseModel):
    item_id: str
    recommended_po_qty: int
    allocations: List[AllocationEntry]
    estimated_total_cost: float
    unallocated_qty: int

# ==========================================================
# COPILOT SCHEMAS
# ==========================================================

class ChatMessage(BaseModel):
    role: str # 'user' or 'assistant' or 'system'
    content: str

class CopilotRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    item_id: Optional[str] = None

class CopilotResponse(BaseModel):
    message: str
    context_retrieved: Optional[Dict[str, Any]] = None
