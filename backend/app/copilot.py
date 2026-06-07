import os
import httpx
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import services
from schemas import ChatMessage

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "meta/llama-3.2-3b-instruct"

# ==========================================================
# SYSTEM PROMPT DEFINITIONS
# ==========================================================

SYSTEM_PROMPT = (
    "You are a professional AI Procurement Copilot for the Procurement Intelligence Platform. "
    "Your objective is to help procurement managers understand inventory alerts, explain supply risks, "
    "and provide business justifications for supplier choices.\n\n"
    "CRITICAL RULES:\n"
    "1. Do NOT calculate or recalculate supplier scores or rankings yourself. Deterministic rankings "
    "   are pre-computed by the backend. Use the ranked list provided in the context.\n"
    "2. Explain decision reasoning using the pre-computed metrics (e.g. price, lead times, reliability, "
    "   quality, and risk).\n"
    "3. Keep your answers concise, bulleted, and tailored for business executives.\n"
    "4. If context data is unavailable, state the general procurement principles and ask for the specific SKU ID."
)

# ==========================================================
# CONTEXT RETRIEVAL
# ==========================================================

def retrieve_context(item_id: Optional[str] = None, query: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves structured context based on item_id or query keywords."""
    context = {}
    
    # Check if we should find a SKU from the query keywords
    if not item_id and query:
        # Search for SKU codes like FOODS_2_197 or HOUSEHOLD_1_032 in the query
        import re
        sku_match = re.search(r'(FOODS_\d+_\d+|HOUSEHOLD_\d+_\d+)', query, re.IGNORECASE)
        if sku_match:
            item_id = sku_match.group(1).upper()
            
    if item_id:
        sku_details = services.get_sku_details(item_id)
        if sku_details:
            context["sku"] = {
                "item_id": sku_details.item_id,
                "product_name": sku_details.product_name,
                "brand": sku_details.brand,
                "unit_size": sku_details.unit_size,
                "dept_id": sku_details.dept_id,
                "available_inventory": sku_details.available_inventory,
                "forecast_7d": sku_details.forecast_7d,
                "forecast_30d": sku_details.forecast_30d,
                "days_until_stockout": sku_details.days_until_stockout,
                "procurement_priority": sku_details.procurement_priority,
                "procurement_reason": sku_details.procurement_reason,
                "recommended_po_qty": sku_details.recommended_po_qty,
                "inventory_risk_score": sku_details.inventory_risk_score,
                "projected_stockout_date": sku_details.projected_stockout_date
            }
            
            # Retrieve ranked suppliers
            ranked_sups = services.get_ranked_suppliers(
                item_id=item_id,
                cost_weight=20,
                lead_time_weight=20,
                reliability_weight=20,
                quality_weight=20,
                risk_weight=20
            )
            context["suppliers"] = [
                {
                    "supplier_id": s.supplier_id,
                    "supplier_name": s.supplier_name,
                    "supplier_type": s.supplier_type,
                    "supplier_price": s.supplier_price,
                    "lead_time_days": s.lead_time_days,
                    "reliability_score": s.reliability_score,
                    "quality_score": s.quality_score,
                    "risk_score": s.risk_score,
                    "capacity_units": s.capacity_units,
                    "score": s.supplier_score
                }
                for s in ranked_sups
            ]
            
    # Check general department shortages (like FOODS_2)
    if query and ("foods_2" in query.lower() or "household" in query.lower()):
        items = services.get_procurement_items()
        dept_code = "FOODS_2" if "foods_2" in query.lower() else "HOUSEHOLD_1"
        dept_items = [i for i in items if i.dept_id == dept_code and i.shortage_quantity > 0]
        context["dept_shortages"] = {
            "department": dept_code,
            "total_items_with_shortages": len(dept_items),
            "total_shortage_qty": sum(i.shortage_quantity for i in dept_items),
            "critical_items": [
                {"item_id": i.item_id, "product_name": i.product_name, "shortage_qty": i.shortage_quantity}
                for i in sorted(dept_items, key=lambda x: x.shortage_quantity, reverse=True)[:3]
            ]
        }
        
    # If no item_id and no specific department matched, load general platform critical list
    if not context:
        items = services.get_procurement_items()
        # Find the most critical items (highest shortage quantity, priority is Critical)
        critical_items = [i for i in items if i.procurement_priority.lower() == 'critical']
        if not critical_items:
            critical_items = [i for i in items if i.shortage_quantity > 0]
        
        # Sort by shortage quantity descending
        critical_items = sorted(critical_items, key=lambda x: x.shortage_quantity, reverse=True)
        
        if critical_items:
            context["critical_items"] = [
                {
                    "item_id": i.item_id,
                    "product_name": i.product_name,
                    "dept_id": i.dept_id,
                    "available_inventory": i.available_inventory,
                    "forecast_30d": i.forecast_30d,
                    "shortage_quantity": i.shortage_quantity,
                    "priority": i.procurement_priority,
                    "reason": i.procurement_reason
                }
                for i in critical_items[:5]  # Top 5 most critical items
            ]
        
    return context

# ==========================================================
# RULE-BASED EXPLANATION FALLBACK (MOCK MODE)
# ==========================================================

def generate_fallback_response(query: str, context: Dict[str, Any]) -> str:
    """Generates high-quality template-based response in case NIM key is missing."""
    q_lower = query.lower()
    sku = context.get("sku")
    sups = context.get("suppliers", [])
    
    if sku:
        item_name = f"{sku['product_name']} ({sku['item_id']})"
        
        # Why high priority
        if "priority" in q_lower or "reason" in q_lower or "why is" in q_lower or "shortage" in q_lower:
            return (
                f"### Inventory Risk Assessment for {item_name}:\n\n"
                f"This SKU is flagged with **{sku['procurement_priority']}** priority due to the following triggers:\n"
                f"- **Stockout Risk**: Current stock is **{sku['available_inventory']}** units, with a projected stockout in **{sku['days_until_stockout']}** days (on {sku['projected_stockout_date']}).\n"
                f"- **Demand Forecast**: Forecast for the next 30 days is **{sku['forecast_30d']}** units.\n"
                f"- **System Alerts**: Identified issue is listed as `{sku['procurement_reason']}`.\n\n"
                f"**Recommendation**: Place a replenishment PO of **{sku['recommended_po_qty']}** units immediately to buffer against demand volatility."
            )
            
        # Supplier comparisons
        if "compare" in q_lower or "supplier" in q_lower or "selected" in q_lower:
            if not sups:
                return f"No candidate suppliers mapped for {sku['item_id']}."
                
            top_sup = sups[0]
            comparison_lines = []
            for s in sups[:3]:
                comparison_lines.append(
                    f"- **{s['supplier_name']}** ({s['supplier_type']}): Price: ${s['supplier_price']:.2f}, "
                    f"Lead Time: {s['lead_time_days']} days, Reliability: {s['reliability_score']}%, Risk: {s['risk_score']}."
                )
                
            comparisons = "\n".join(comparison_lines)
            return (
                f"### Supplier Recommendation for {item_name}:\n\n"
                f"Pre-calculated ranking indicates **{top_sup['supplier_name']}** is the optimal partner (Score: {top_sup['score']}/100).\n\n"
                f"**Candidate Comparison (Weighted equally across Cost, Speed, Reliability, Quality, and Risk):**\n"
                f"{comparisons}\n\n"
                f"**Strategic Selection Reasoning**:\n"
                f"- **{top_sup['supplier_name']}** scores highest because it offers a balanced profile of {top_sup['reliability_score']}% reliability and {top_sup['lead_time_days']}-day delivery at a competitive price of ${top_sup['supplier_price']:.2f}."
            )
            
    # Department level query
    dept_shortages = context.get("dept_shortages")
    if dept_shortages:
        dept = dept_shortages["department"]
        crit_lines = []
        for c in dept_shortages["critical_items"]:
            crit_lines.append(f"- **{c['product_name']}** ({c['item_id']}): Shortage of **{c['shortage_qty']}** units.")
        crit_text = "\n".join(crit_lines)
        return (
            f"### Category Shortages Report for {dept}:\n\n"
            f"There are currently **{dept_shortages['total_items_with_shortages']}** items experiencing shortages in the **{dept}** category, "
            f"totaling **{dept_shortages['total_shortage_qty']}** units of supply gaps.\n\n"
            f"**Top Gaps Needing Immediate Procurement Action:**\n"
            f"{crit_text}\n\n"
            f"**Root Causes**: These shortages are driven by recent demand surges exceeding safety stock thresholds and long supplier lead times in the {dept} division."
        )
        
    # Platform critical list query
    critical_items = context.get("critical_items")
    if critical_items:
        # If the user asks for critical/alert/shortage/worst items
        if any(x in q_lower for x in ["critical", "alert", "shortage", "worst", "stockout", "most important", "which item"]):
            top_item = critical_items[0]
            crit_lines = []
            for item in critical_items[:3]:
                crit_lines.append(
                    f"- **{item['product_name']}** (`{item['item_id']}`): Shortage of **{item['shortage_quantity']}** units in {item['dept_id']} "
                    f"(Current Stock: {item['available_inventory']}, Reason: `{item['reason']}`)."
                )
            crit_text = "\n".join(crit_lines)
            return (
                f"### Platform Critical Inventory Alerts:\n\n"
                f"Based on current inventory levels, the most critical item is **{top_item['product_name']}** (`{top_item['item_id']}`) "
                f"which is flagged with **{top_item['priority']}** priority due to: `{top_item['reason']}`.\n\n"
                f"**Top 3 items with active supply gaps needing immediate replenishment:**\n"
                f"{crit_text}\n\n"
                f"**Recommendation**: Please navigate to the SKU detail pages for these items to configure supplier weights and generate optimized purchase orders."
            )

    return (
        "### Procurement Copilot Advisor:\n\n"
        "Please query about a specific item code (e.g. `FOODS_2_197` or `HOUSEHOLD_1_032`) or a department category to get structured insights.\n\n"
        "I can answer:\n"
        "- *'Why is FOODS_2_197 high priority?'*\n"
        "- *'Compare candidate suppliers for HOUSEHOLD_1_032'*\n"
        "- *'What is causing shortages in FOODS_2?'*"
    )

# ==========================================================
# COPILOT ORCHESTRATOR
# ==========================================================

async def ask_copilot(
    message: str,
    history: List[ChatMessage] = [],
    item_id: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves context and queries NVIDIA NIM endpoint or runs fallback generator."""
    # Retrieve structured context
    context = retrieve_context(item_id=item_id, query=message)
    
    # If API key is missing or blank, use smart fallback mode
    if not NVIDIA_API_KEY or NVIDIA_API_KEY.startswith("your-") or len(NVIDIA_API_KEY) < 10:
        response_text = generate_fallback_response(message, context)
        return {
            "message": response_text,
            "context_retrieved": context if context else None
        }
        
    # Build System messages with context
    enriched_sys_prompt = SYSTEM_PROMPT
    if context:
        enriched_sys_prompt += (
            f"\n\nRETRIEVED DATA CONTEXT:\n"
            f"{str(context)}\n"
            f"Focus explanations strictly around this context information."
        )
        
    # Format messages payload
    messages_payload = [{"role": "system", "content": enriched_sys_prompt}]
    
    # Append conversation history
    for chat in history[-6:]:  # limit history to last 6 entries
        # Handle role matching
        role = chat.role if chat.role in ["user", "assistant", "system"] else "user"
        messages_payload.append({"role": role, "content": chat.content})
        
    # Append current message
    messages_payload.append({"role": "user", "content": message})
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": DEFAULT_MODEL,
                "messages": messages_payload,
                "temperature": 0.2,
                "max_tokens": 1024
            }
            
            response = await client.post(NVIDIA_API_URL, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                bot_message = data["choices"][0]["message"]["content"]
                return {
                    "message": bot_message,
                    "context_retrieved": context if context else None
                }
            else:
                # Log API error and use fallback response
                print(f"NVIDIA NIM API Error: {response.status_code} - {response.text}")
                fallback_msg = generate_fallback_response(message, context)
                return {
                    "message": fallback_msg + "\n\n*(Note: System running in offline fallback mode)*",
                    "context_retrieved": context if context else None
                }
    except Exception as e:
        print(f"Exception during Copilot NIM API call: {e}")
        fallback_msg = generate_fallback_response(message, context)
        return {
            "message": fallback_msg + "\n\n*(Note: System running in offline fallback mode)*",
            "context_retrieved": context if context else None
        }
