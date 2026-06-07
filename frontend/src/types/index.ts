export interface DistributionEntry {
  name: string;
  value: number;
}

export interface ShortageSKUEntry {
  item_id: string;
  product_name: string;
  shortage_quantity: number;
  dept_id: string;
}

export interface DashboardData {
  total_skus: number;
  procurement_alerts: number;
  procurement_triggers: number;
  emergency_procurements: number;
  total_shortage_quantity: number;
  total_recommended_po_qty: number;
  revenue_at_risk: number;
  priority_distribution: DistributionEntry[];
  category_distribution: DistributionEntry[];
  department_distribution: DistributionEntry[];
  top_shortage_skus: ShortageSKUEntry[];
}

export interface WorkbenchItem {
  item_id: string;
  product_name: string;
  dept_id: string;
  available_inventory: number;
  forecast_30d: number;
  shortage_quantity: number;
  procurement_priority: string;
  procurement_category: string;
  procurement_reason: string;
  recommended_po_qty: number;
}

export interface SupplierInfo {
  supplier_id: string;
  supplier_name: string;
  supplier_type: string;
  supplier_price: number;
  lead_time_days: number;
  reliability_score: number;
  quality_score: number;
  fill_rate: number;
  risk_score: number;
  capacity_units: number;
}

export interface SKUDetails {
  item_id: string;
  product_name: string;
  brand: string;
  unit_size: string;
  dept_id: string;
  available_inventory: number;
  forecast_7d: number;
  forecast_30d: number;
  days_until_stockout: number;
  procurement_priority: string;
  procurement_reason: string;
  recommended_po_qty: number;
  revenue_at_risk: number;
  inventory_risk_score: number;
  projected_stockout_date: string;
  suppliers: SupplierInfo[];
}

export interface RankedSupplier {
  supplier_id: string;
  supplier_name: string;
  supplier_type: string;
  supplier_price: number;
  lead_time_days: number;
  reliability_score: number;
  quality_score: number;
  risk_score: number;
  capacity_units: number;
  cost_score: number;
  lead_time_score: number;
  reliability_score_norm: number;
  quality_score_norm: number;
  risk_score_norm: number;
  supplier_score: number;
}

export interface AllocationEntry {
  supplier_id: string;
  supplier_name: string;
  allocated_qty: number;
  allocation_pct: number;
  supplier_price: number;
  spend: number;
  lead_time_days: number;
  reliability_score: number;
  capacity_units: number;
}

export interface OptimizationResult {
  item_id: string;
  recommended_po_qty: number;
  allocations: AllocationEntry[];
  estimated_total_cost: number;
  unallocated_qty: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface CopilotResponse {
  message: string;
  context_retrieved?: Record<string, unknown>;
}
