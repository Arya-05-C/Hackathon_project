from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import services
import copilot
from schemas import (
    DashboardResponse, WorkbenchItem, SKUDetailsResponse,
    RankSuppliersRequest, RankedSupplier,
    OptimizeProcurementRequest, OptimizationResponse,
    CopilotRequest, CopilotResponse
)

# Initialize FastAPI App
app = FastAPI(
    title="Procurement Decision Intelligence System Backend",
    version="1.0.0",
    description="FastAPI service for inventory alerts, supplier rankings, PO optimization, and Copilot interactions."
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# ENDPOINTS
# ==========================================================

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy"}

@app.get("/dashboard", response_model=DashboardResponse)
def get_dashboard():
    """Retrieves executive summary indicators and Recharts distribution datasets."""
    try:
        return services.get_dashboard_data()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/procurement-items", response_model=List[WorkbenchItem])
def get_procurement_items(
    priority: Optional[str] = Query(None, description="Filter by priority (Critical, High, Medium, Low)"),
    category: Optional[str] = Query(None, description="Filter by category (Emergency, Urgent, Planned, Monitor)"),
    department: Optional[str] = Query(None, description="Filter by department division code"),
    search: Optional[str] = Query(None, description="Search term for product name or SKU code")
):
    """Retrieves list of inventory risk rows for the workbench table."""
    try:
        return services.get_procurement_items(
            priority=priority,
            category=category,
            department=department,
            search=search
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sku/{item_id}", response_model=SKUDetailsResponse)
def get_sku(item_id: str):
    """Retrieves full detail parameters and candidate suppliers for a specific SKU."""
    try:
        details = services.get_sku_details(item_id)
        if not details:
            raise HTTPException(status_code=404, detail=f"SKU {item_id} not found.")
        return details
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rank-suppliers", response_model=List[RankedSupplier])
def rank_suppliers(req: RankSuppliersRequest):
    """Ranks item candidate suppliers deterministically based on sliders weights."""
    try:
        ranked = services.get_ranked_suppliers(
            item_id=req.item_id,
            cost_weight=req.cost_weight,
            lead_time_weight=req.lead_time_weight,
            reliability_weight=req.reliability_weight,
            quality_weight=req.quality_weight,
            risk_weight=req.risk_weight
        )
        if not ranked:
            raise HTTPException(status_code=404, detail=f"No candidates found for SKU {req.item_id}")
        return ranked
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize-procurement", response_model=OptimizationResponse)
def optimize_procurement(req: OptimizeProcurementRequest):
    """Calculates quantity splits and procurement spends across candidates."""
    try:
        return services.allocate_procurement(
            item_id=req.item_id,
            recommended_po_qty=req.recommended_po_qty,
            cost_weight=req.cost_weight,
            lead_time_weight=req.lead_time_weight,
            reliability_weight=req.reliability_weight,
            quality_weight=req.quality_weight,
            risk_weight=req.risk_weight
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/copilot", response_model=CopilotResponse)
async def post_copilot(req: CopilotRequest):
    """Conversational intelligence for explaining procurement decisions."""
    try:
        result = await copilot.ask_copilot(
            message=req.message,
            history=req.history,
            item_id=req.item_id
        )
        return CopilotResponse(
            message=result["message"],
            context_retrieved=result.get("context_retrieved")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
