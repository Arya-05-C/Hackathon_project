'use client';

import React, { useState, useEffect, use } from 'react';
import { useRouter } from 'next/navigation';
import { 
  fetchSKUDetails, 
  rankSuppliers, 
  optimizeProcurement 
} from '../../../lib/api';
import { 
  SKUDetails, 
  RankedSupplier, 
  OptimizationResult 
} from '../../../types';
import { 
  ArrowLeft, 
  Loader2, 
  AlertTriangle, 
  Info, 
  Sliders, 
  TrendingUp, 
  DollarSign, 
  ArrowRightLeft,
  Keyboard
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import CopilotChat from '../../../components/CopilotChat';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function SKUDetailPage({ params }: PageProps) {
  const router = useRouter();
  const { id } = use(params);

  // States
  const [sku, setSku] = useState<SKUDetails | null>(null);
  const [rankedSuppliers, setRankedSuppliers] = useState<RankedSupplier[]>([]);
  const [optimization, setOptimization] = useState<OptimizationResult | null>(null);
  const [poQty, setPoQty] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Weights state (Cost, Lead Time, Reliability, Quality, Risk)
  const [weights, setWeights] = useState({
    cost_weight: 20,
    lead_time_weight: 20,
    reliability_weight: 20,
    quality_weight: 20,
    risk_weight: 20
  });
  const [inputMode, setInputMode] = useState<'slider' | 'manual'>('slider');

  // Load SKU data on mount
  useEffect(() => {
    setLoading(true);
    fetchSKUDetails(id)
      .then((res) => {
        setSku(res);
        setPoQty(res.recommended_po_qty);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError(`Failed to retrieve SKU details for ${id}.`);
        setLoading(false);
      });
  }, [id]);

  // Handle Dynamic Weight Updates and Auto-Normalization to 100%
  const handleWeightChange = (key: keyof typeof weights, value: number) => {
    const otherKeys = (Object.keys(weights) as Array<keyof typeof weights>).filter(k => k !== key);
    const otherSum = otherKeys.reduce((sum, k) => sum + weights[k], 0);
    
    const newWeights = { ...weights };
    newWeights[key] = value;
    
    const remaining = 100 - value;
    
    if (otherSum === 0) {
      // If others were zero, distribute remaining equally
      otherKeys.forEach(k => {
        newWeights[k] = remaining / 4;
      });
    } else {
      // Distribute remaining proportionally
      otherKeys.forEach(k => {
        newWeights[k] = Math.round((weights[k] / otherSum) * remaining * 100) / 100;
      });
    }

    // Ensure they sum exactly to 100 due to float rounding
    const sum = Object.values(newWeights).reduce((a, b) => a + b, 0);
    if (sum !== 100) {
      const diff = 100 - sum;
      // Adjust first other key slightly to handle float error
      newWeights[otherKeys[0]] = Math.round((newWeights[otherKeys[0]] + diff) * 100) / 100;
    }
    
    setWeights(newWeights);
  };

  // Handle Independent Weight Updates (no auto-normalization)
  const handleManualWeightChange = (key: keyof typeof weights, value: number) => {
    setWeights(prev => ({
      ...prev,
      [key]: value
    }));
  };

  // Compute Total Weight validation
  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
  const isValidWeight = totalWeight === 100;

  // Re-trigger Ranking & Optimization when weights or quantity changes
  useEffect(() => {
    if (!sku) return;

    // In manual mode, do not call backend unless total weight is exactly 100%
    if (inputMode === 'manual' && totalWeight !== 100) return;

    // Fetch ranked suppliers
    rankSuppliers(id, weights)
      .then((res) => {
        setRankedSuppliers(res);
      })
      .catch(err => console.error("Error ranking suppliers:", err));

    // Fetch optimization results
    optimizeProcurement(id, poQty, weights)
      .then((res) => {
        setOptimization(res);
      })
      .catch(err => console.error("Error optimizing procurement:", err));

  }, [sku, weights, poQty, id, inputMode, totalWeight]);

  if (loading) {
    return (
      <div className="min-h-[70vh] flex flex-col justify-center items-center gap-4">
        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin" />
        <p className="text-white/60 text-sm font-semibold">Analyzing SKU constraints and candidate metrics...</p>
      </div>
    );
  }

  if (error || !sku) {
    return (
      <div className="min-h-[70vh] flex flex-col justify-center items-center gap-4 text-center max-w-md mx-auto">
        <div className="p-4 bg-rose-500/10 rounded-2xl border border-rose-500/20 text-rose-400">
          <AlertTriangle className="w-10 h-10" />
        </div>
        <h2 className="text-lg font-bold text-white">SKU Not Found</h2>
        <p className="text-sm text-white/50">{error || "Could not retrieve SKU information."}</p>
        <button
          onClick={() => router.push('/workbench')}
          className="mt-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition-all"
        >
          Return to Workbench
        </button>
      </div>
    );
  }

  const getPriorityBadge = (p: string) => {
    switch (p.toLowerCase()) {
      case 'critical': return 'bg-rose-500/10 border-rose-500/30 text-rose-400';
      case 'high': return 'bg-amber-500/10 border-amber-500/30 text-amber-400';
      case 'medium': return 'bg-blue-500/10 border-blue-500/30 text-blue-400';
      default: return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';
    }
  };

  // Forecast Comparison Chart Data
  const forecastChartData = [
    { name: '7-Day Sum', forecast: sku.forecast_7d, fill: '#6366F1' },
    { name: '30-Day Sum', forecast: sku.forecast_30d, fill: '#3B82F6' },
    { name: 'Recommended PO', forecast: sku.recommended_po_qty, fill: '#EC4899' }
  ];

  return (
    <div className="space-y-6 pb-20">
      {/* Back Button & Header */}
      <div className="flex flex-col gap-4">
        <button
          onClick={() => router.push('/workbench')}
          className="flex items-center gap-2 text-white/40 hover:text-white transition-colors text-sm font-semibold max-w-fit cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Workbench
        </button>

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
              {sku.product_name}
            </h1>
            <p className="text-sm text-white/40 font-mono mt-1">
              SKU: {sku.item_id} &bull; Brand: {sku.brand} &bull; Size: {sku.unit_size}
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <span className={`text-xs px-3 py-1.5 rounded-lg border font-semibold ${getPriorityBadge(sku.procurement_priority)}`}>
              {sku.procurement_priority} Priority
            </span>
            <span className="text-xs px-3 py-1.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-lg font-semibold">
              Risk Score: {sku.inventory_risk_score}
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: SKU Info & Recommendation Studio */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Col: Product & Forecast info */}
        <div className="lg:col-span-1 space-y-6">
          {/* Inventory Snapshot */}
          <div className="glass-panel p-6 rounded-2xl space-y-5">
            <h3 className="font-bold text-white text-base flex items-center gap-2 border-b border-white/5 pb-3">
              <Info className="w-4 h-4 text-indigo-400" />
              Inventory Metrics
            </h3>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-black/20 p-3.5 rounded-xl border border-white/5">
                <span className="text-[10px] text-white/40 font-bold uppercase tracking-wider">Available Stock</span>
                <p className="text-xl font-bold text-white mt-1">{sku.available_inventory}</p>
              </div>
              <div className="bg-black/20 p-3.5 rounded-xl border border-white/5">
                <span className="text-[10px] text-white/40 font-bold uppercase tracking-wider">Stockout Horizon</span>
                <p className="text-xl font-bold text-rose-400 mt-1">{sku.days_until_stockout} Days</p>
              </div>
            </div>
            
            <div className="space-y-3.5 text-sm pt-2">
              <div className="flex justify-between items-center">
                <span className="text-white/40 font-medium">Projected Stockout:</span>
                <span className="text-white/80 font-semibold">{sku.projected_stockout_date}</span>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-white/40 font-medium">Department:</span>
                <span className="text-white/80 font-semibold bg-white/5 px-2 py-0.5 rounded">{sku.dept_id}</span>
              </div>
              
              <div className="flex flex-col gap-1">
                <span className="text-white/40 font-medium">Procurement Alert:</span>
                <p className="text-xs text-white/80 leading-relaxed bg-[#131B2E] p-2.5 rounded-xl border border-white/5 mt-1">
                  {sku.procurement_reason}
                </p>
              </div>
            </div>
          </div>

          {/* Forecast & Recommendations Comparison */}
          <div className="glass-panel p-6 rounded-2xl space-y-4">
            <h3 className="font-bold text-white text-base flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-blue-400" />
              Demand Forecast Sums
            </h3>
            
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={forecastChartData}>
                  <XAxis dataKey="name" stroke="rgba(255,255,255,0.4)" fontSize={10} />
                  <Tooltip cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
                  <Bar dataKey="forecast" maxBarSize={32} radius={[4, 4, 0, 0]}>
                    {forecastChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Right Col: Supplier Recommendation Studio (Sliders & Ranked Table) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="glass-panel p-6 rounded-2xl space-y-6">
            <div className="flex justify-between items-center border-b border-white/5 pb-4">
              <div className="flex items-center gap-2">
                <Sliders className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-white text-base">Supplier Recommendation Studio</h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setWeights({
                    cost_weight: 20,
                    lead_time_weight: 20,
                    reliability_weight: 20,
                    quality_weight: 20,
                    risk_weight: 20
                  })}
                  className="text-[10px] bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 px-2 py-1 rounded border border-indigo-500/20 font-bold cursor-pointer transition-colors"
                >
                  Equalize (20% each)
                </button>
                <span className={`text-[10px] font-bold px-2 py-1 rounded border uppercase tracking-wide transition-all ${
                  isValidWeight
                    ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                    : 'text-rose-400 bg-rose-500/10 border-rose-500/20 animate-pulse'
                }`}>
                  Total weight: {totalWeight}% {isValidWeight ? '✓' : '(Must equal 100%)'}
                </span>
              </div>
            </div>

            {/* Weights Sliders Layout */}
            {inputMode === 'slider' ? (
              <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
                {[
                  { key: 'cost_weight', label: 'Cost Weight' },
                  { key: 'lead_time_weight', label: 'Lead Time Weight' },
                  { key: 'reliability_weight', label: 'Reliability Weight' },
                  { key: 'quality_weight', label: 'Quality Weight' },
                  { key: 'risk_weight', label: 'Risk Weight' }
                ].map((slider) => {
                  const val = weights[slider.key as keyof typeof weights];
                  return (
                    <div key={slider.key} className="space-y-2.5">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-white/60">{slider.label}</span>
                        <span className="text-indigo-400 font-bold">{Math.round(val)}%</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={val}
                        onChange={(e) => handleWeightChange(slider.key as keyof typeof weights, Number(e.target.value))}
                        className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                      />
                    </div>
                  );
                })}
              </div>
            ) : (
              /* Manual Input Mode Layout */
              <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
                {[
                  { key: 'cost_weight', label: 'Cost Weight' },
                  { key: 'lead_time_weight', label: 'Lead Time Weight' },
                  { key: 'reliability_weight', label: 'Reliability Weight' },
                  { key: 'quality_weight', label: 'Quality Weight' },
                  { key: 'risk_weight', label: 'Risk Weight' }
                ].map((inputItem) => {
                  const val = weights[inputItem.key as keyof typeof weights];
                  return (
                    <div key={inputItem.key} className="space-y-2">
                      <label className="block text-xs font-semibold text-white/60">{inputItem.label}</label>
                      <div className="relative rounded-xl border border-white/10 bg-black/20 focus-within:border-indigo-500/50 transition-all flex items-center px-3 py-2">
                        <input
                          type="number"
                          min="0"
                          max="100"
                          value={val === 0 ? '' : val}
                          placeholder="0"
                          onChange={(e) => handleManualWeightChange(inputItem.key as keyof typeof weights, Math.min(100, Math.max(0, Number(e.target.value))))}
                          className="w-full bg-transparent text-sm font-bold text-white outline-none border-none text-left [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                        />
                        <span className="text-white/30 text-xs font-bold font-mono select-none">%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Input Mode Toggle Link/Button */}
            <div className="flex justify-end pt-2 border-t border-white/5">
              <button
                type="button"
                onClick={() => setInputMode(inputMode === 'slider' ? 'manual' : 'slider')}
                className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-semibold transition-colors cursor-pointer"
              >
                {inputMode === 'slider' ? (
                  <>
                    <Keyboard className="w-3.5 h-3.5" />
                    Switch to Manual Keypad Entry
                  </>
                ) : (
                  <>
                    <Sliders className="w-3.5 h-3.5" />
                    Switch to Slider Adjustment Mode
                  </>
                )}
              </button>
            </div>

            {inputMode === 'manual' && !isValidWeight && (
              <div className="flex items-center gap-2 p-3.5 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs font-medium">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>
                  The total sum of weights is currently <strong>{totalWeight}%</strong>. Please adjust the values so they equal exactly <strong>100%</strong> to recalculate supplier rankings.
                </span>
              </div>
            )}

            {/* Ranked Candidates Table */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-white/40 uppercase tracking-widest">
                Optimal Candidate Suppliers (Sorted by score)
              </h4>
              
              <div className="overflow-x-auto border border-white/5 rounded-xl">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-white/[0.02] text-xs font-semibold text-white/50 uppercase border-b border-white/5">
                      <th className="px-4 py-3">Rank & Name</th>
                      <th className="px-4 py-3 text-right">Score</th>
                      <th className="px-4 py-3 text-right">Price</th>
                      <th className="px-4 py-3 text-right">Lead Time</th>
                      <th className="px-4 py-3 text-right">Reliability</th>
                      <th className="px-4 py-3 text-right">Quality</th>
                      <th className="px-4 py-3 text-right">Risk (Norm)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-xs">
                    {rankedSuppliers.map((sup, idx) => (
                      <tr key={sup.supplier_id} className="hover:bg-white/[0.01]">
                        <td className="px-4 py-3 font-medium">
                          <div>
                            <span className="text-indigo-400 font-semibold mr-1.5">#{idx + 1}</span>
                            <span className="text-white font-semibold">{sup.supplier_name}</span>
                          </div>
                          <span className="text-[10px] text-white/30 tracking-wide font-medium">
                            {sup.supplier_type} supplier
                          </span>
                        </td>
                        
                        <td className="px-4 py-3 text-right">
                          <span className="bg-indigo-500/10 text-indigo-300 font-bold px-2 py-0.5 rounded border border-indigo-500/20 text-xs">
                            {sup.supplier_score}
                          </span>
                        </td>
                        
                        <td className="px-4 py-3 text-right text-white/80 font-medium">
                          ${sup.supplier_price.toFixed(2)}
                        </td>
                        
                        <td className="px-4 py-3 text-right text-white/60">
                          {sup.lead_time_days} Days
                        </td>
                        
                        <td className="px-4 py-3 text-right text-white/60">
                          {sup.reliability_score}%
                        </td>
                        
                        <td className="px-4 py-3 text-right text-white/60">
                          {sup.quality_score}%
                        </td>
                        
                        <td className="px-4 py-3 text-right text-white/40">
                          {sup.risk_score} ({100 - sup.risk_score})
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Section 2: Procurement Allocation splits */}
      <div className="glass-panel p-6 rounded-2xl space-y-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-white/5 pb-4">
          <div className="flex items-center gap-2">
            <ArrowRightLeft className="w-5 h-5 text-indigo-400" />
            <div>
              <h3 className="font-bold text-white text-base">Multi-Supplier Quantity Allocation</h3>
              <p className="text-xs text-white/40">Distributes recommended volume based on supplier capacities and rankings</p>
            </div>
          </div>
          
          {/* Allocation input */}
          <div className="flex items-center gap-3 bg-black/20 px-4 py-2 border border-white/5 rounded-xl">
            <span className="text-xs text-white/40 font-bold uppercase tracking-wider">Required Quantity</span>
            <input
              type="number"
              value={poQty}
              onChange={(e) => setPoQty(Math.max(0, Number(e.target.value)))}
              className="bg-transparent text-white text-sm font-bold w-24 outline-none border-none text-right [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            />
          </div>
        </div>

        {/* Allocation Splits Table */}
        {optimization ? (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3">
              <div className="overflow-x-auto border border-white/5 rounded-xl">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-white/[0.02] font-semibold text-white/50 uppercase border-b border-white/5">
                      <th className="px-4 py-3.5">Supplier</th>
                      <th className="px-4 py-3.5 text-right">Allocated Quantity</th>
                      <th className="px-4 py-3.5 text-right">Allocation %</th>
                      <th className="px-4 py-3.5 text-right">Supplier Price</th>
                      <th className="px-4 py-3.5 text-right">Spend</th>
                      <th className="px-4 py-3.5 text-right">Capacity Constraints</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {optimization.allocations.map((alloc) => {
                      const hasAllocation = alloc.allocated_qty > 0;
                      return (
                        <tr 
                          key={alloc.supplier_id} 
                          className={`hover:bg-white/[0.01] ${hasAllocation ? 'bg-indigo-500/[0.02]' : ''}`}
                        >
                          <td className="px-4 py-3.5 font-medium">
                            <span className="text-white font-semibold">{alloc.supplier_name}</span>
                          </td>
                          
                          <td className={`px-4 py-3.5 text-right font-bold text-sm ${hasAllocation ? 'text-indigo-400' : 'text-white/20'}`}>
                            {alloc.allocated_qty.toLocaleString()}
                          </td>
                          
                          <td className="px-4 py-3.5 text-right font-semibold text-white/80">
                            {alloc.allocation_pct}%
                          </td>
                          
                          <td className="px-4 py-3.5 text-right text-white/60">
                            ${alloc.supplier_price.toFixed(2)}
                          </td>
                          
                          <td className={`px-4 py-3.5 text-right font-bold ${hasAllocation ? 'text-emerald-400' : 'text-white/20'}`}>
                            ${alloc.spend.toLocaleString()}
                          </td>
                          
                          <td className="px-4 py-3.5 text-right text-white/40">
                            Limit: {alloc.capacity_units.toLocaleString()} units
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Sum Summary Card */}
            <div className="lg:col-span-1 glass-panel p-5 rounded-2xl flex flex-col justify-between glow-green">
              <div className="space-y-4">
                <div className="flex justify-between items-center text-xs text-white/40 uppercase font-bold tracking-wider">
                  <span>Procurement Spend</span>
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                </div>
                
                <div>
                  <span className="text-3xl font-extrabold text-emerald-400 tracking-tight">
                    ${optimization.estimated_total_cost.toLocaleString()}
                  </span>
                  <p className="text-[10px] text-white/30 font-medium mt-1">Estimated total procurement cost</p>
                </div>
              </div>
              
              <div className="border-t border-white/5 pt-4 mt-6 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-white/40">Target Demand:</span>
                  <span className="text-white font-semibold">{optimization.recommended_po_qty}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/40">Unallocated Gaps:</span>
                  <span className={`font-semibold ${optimization.unallocated_qty > 0 ? 'text-rose-400 animate-pulse' : 'text-emerald-400'}`}>
                    {optimization.unallocated_qty} units
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Contextual AI Copilot Chat panel */}
      <CopilotChat activeItemId={sku.item_id} activeItemName={sku.product_name} />
    </div>
  );
}
