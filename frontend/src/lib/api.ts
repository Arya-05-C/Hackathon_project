import {
  DashboardData, WorkbenchItem, SKUDetails,
  RankedSupplier, OptimizationResult, ChatMessage, CopilotResponse
} from '../types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchDashboard(): Promise<DashboardData> {
  const res = await fetch(`${API_BASE_URL}/dashboard`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error('Failed to fetch dashboard metrics');
  }
  return res.json();
}

export async function fetchProcurementItems(filters: {
  priority?: string;
  category?: string;
  department?: string;
  search?: string;
} = {}): Promise<WorkbenchItem[]> {
  const query = new URLSearchParams();
  if (filters.priority) query.append('priority', filters.priority);
  if (filters.category) query.append('category', filters.category);
  if (filters.department) query.append('department', filters.department);
  if (filters.search) query.append('search', filters.search);

  const res = await fetch(`${API_BASE_URL}/procurement-items?${query.toString()}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error('Failed to fetch workbench items');
  }
  return res.json();
}

export async function fetchSKUDetails(itemId: string): Promise<SKUDetails> {
  const res = await fetch(`${API_BASE_URL}/sku/${itemId}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`Failed to fetch SKU details for ${itemId}`);
  }
  return res.json();
}

export async function rankSuppliers(
  itemId: string,
  weights: {
    cost_weight: number;
    lead_time_weight: number;
    reliability_weight: number;
    quality_weight: number;
    risk_weight: number;
  }
): Promise<RankedSupplier[]> {
  const res = await fetch(`${API_BASE_URL}/rank-suppliers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_id: itemId, ...weights })
  });
  if (!res.ok) {
    throw new Error(`Failed to rank suppliers for ${itemId}`);
  }
  return res.json();
}

export async function optimizeProcurement(
  itemId: string,
  recommendedPoQty: number,
  weights: {
    cost_weight: number;
    lead_time_weight: number;
    reliability_weight: number;
    quality_weight: number;
    risk_weight: number;
  }
): Promise<OptimizationResult> {
  const res = await fetch(`${API_BASE_URL}/optimize-procurement`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      item_id: itemId,
      recommended_po_qty: recommendedPoQty,
      ...weights
    })
  });
  if (!res.ok) {
    throw new Error(`Failed to optimize allocations for ${itemId}`);
  }
  return res.json();
}

export async function askCopilot(
  message: string,
  history: ChatMessage[],
  itemId?: string
): Promise<CopilotResponse> {
  const res = await fetch(`${API_BASE_URL}/copilot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history,
      item_id: itemId || null
    })
  });
  if (!res.ok) {
    throw new Error('Failed to query AI Procurement Copilot');
  }
  return res.json();
}
