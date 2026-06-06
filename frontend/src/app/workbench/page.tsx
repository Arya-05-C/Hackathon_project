'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { fetchProcurementItems } from '../../lib/api';
import { WorkbenchItem } from '../../types';
import { 
  Search, 
  Filter, 
  ChevronRight,
  Loader2,
  AlertCircle
} from 'lucide-react';
import CopilotChat from '../../components/CopilotChat';

export default function WorkbenchPage() {
  const [items, setItems] = useState<WorkbenchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter States
  const [priority, setPriority] = useState('');
  const [category, setCategory] = useState('');
  const [department, setDepartment] = useState('');
  const [search, setSearch] = useState('');
  
  const router = useRouter();

  useEffect(() => {
    setLoading(true);
    fetchProcurementItems({ priority, category, department, search })
      .then((res) => {
        setItems(res);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError('Failed to load workbench data. Verify FastAPI is online.');
        setLoading(false);
      });
  }, [priority, category, department, search]);

  // Priority badge styling
  const getPriorityBadge = (p: string) => {
    switch (p.toLowerCase()) {
      case 'critical':
        return 'bg-rose-500/10 border-rose-500/30 text-rose-400';
      case 'high':
        return 'bg-amber-500/10 border-amber-500/30 text-amber-400';
      case 'medium':
        return 'bg-blue-500/10 border-blue-500/30 text-blue-400';
      default:
        return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';
    }
  };

  // Category badge styling
  const getCategoryBadge = (c: string) => {
    switch (c.toLowerCase()) {
      case 'emergency':
        return 'bg-rose-600/20 border-rose-500/40 text-rose-300 font-bold animate-pulse';
      case 'urgent':
        return 'bg-amber-600/10 border-amber-500/30 text-amber-300 font-semibold';
      case 'planned':
        return 'bg-blue-600/10 border-blue-500/30 text-blue-300';
      default:
        return 'bg-white/5 border-white/10 text-white/50';
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
          Procurement Workbench
        </h1>
        <p className="text-sm text-white/50 mt-1">
          Review stock shortages, filter priority tiers, and launch supplier recomendations.
        </p>
      </div>

      {/* Filters Control Bar */}
      <div className="glass-panel p-5 rounded-2xl flex flex-col lg:flex-row gap-4 justify-between items-stretch lg:items-center">
        {/* Search */}
        <div className="flex-1 min-w-[280px] bg-black/30 border border-white/5 rounded-xl px-4 py-2.5 flex items-center gap-2.5 focus-within:border-indigo-500/40 transition-all">
          <Search className="w-4 h-4 text-white/40" />
          <input
            type="text"
            placeholder="Search by Product Name or SKU code..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-transparent flex-1 text-sm outline-none text-white placeholder-white/30"
          />
        </div>

        {/* Dropdowns */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Priority */}
          <div className="flex items-center gap-1.5 bg-black/20 px-3 py-1.5 rounded-xl border border-white/5">
            <span className="text-[11px] text-white/30 uppercase font-bold tracking-wider">Priority</span>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="bg-transparent text-sm text-white font-semibold outline-none border-none py-1 pr-4 cursor-pointer"
            >
              <option value="" className="bg-[#131B2E]">All</option>
              <option value="Critical" className="bg-[#131B2E] text-rose-400">Critical</option>
              <option value="High" className="bg-[#131B2E] text-amber-400">High</option>
              <option value="Medium" className="bg-[#131B2E] text-blue-400">Medium</option>
              <option value="Low" className="bg-[#131B2E] text-emerald-400">Low</option>
            </select>
          </div>

          {/* Category */}
          <div className="flex items-center gap-1.5 bg-black/20 px-3 py-1.5 rounded-xl border border-white/5">
            <span className="text-[11px] text-white/30 uppercase font-bold tracking-wider">Category</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="bg-transparent text-sm text-white font-semibold outline-none border-none py-1 pr-4 cursor-pointer"
            >
              <option value="" className="bg-[#131B2E]">All</option>
              <option value="Emergency" className="bg-[#131B2E] text-rose-400">Emergency</option>
              <option value="Urgent" className="bg-[#131B2E] text-amber-400">Urgent</option>
              <option value="Planned" className="bg-[#131B2E] text-blue-400">Planned</option>
              <option value="Monitor" className="bg-[#131B2E] text-white/50">Monitor</option>
            </select>
          </div>

          {/* Department */}
          <div className="flex items-center gap-1.5 bg-black/20 px-3 py-1.5 rounded-xl border border-white/5">
            <span className="text-[11px] text-white/30 uppercase font-bold tracking-wider">Dept</span>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="bg-transparent text-sm text-white font-semibold outline-none border-none py-1 pr-4 cursor-pointer"
            >
              <option value="" className="bg-[#131B2E]">All Departments</option>
              <option value="FOODS_1" className="bg-[#131B2E]">FOODS_1</option>
              <option value="FOODS_2" className="bg-[#131B2E]">FOODS_2</option>
              <option value="HOUSEHOLD_1" className="bg-[#131B2E]">HOUSEHOLD_1</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table Section */}
      <div className="glass-panel rounded-2xl overflow-hidden shadow-2xl relative min-h-[400px]">
        {loading ? (
          <div className="absolute inset-0 flex flex-col justify-center items-center gap-2 bg-black/10 backdrop-blur-sm z-20">
            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
            <span className="text-white/60 text-xs font-semibold">Filtering SKU inventory logs...</span>
          </div>
        ) : null}

        {error && !loading ? (
          <div className="p-12 text-center flex flex-col items-center gap-3">
            <AlertCircle className="w-10 h-10 text-rose-500" />
            <p className="text-white font-semibold">Connection Timeout</p>
            <p className="text-white/50 text-xs max-w-sm">{error}</p>
          </div>
        ) : null}

        {!loading && !error && items.length === 0 ? (
          <div className="p-12 text-center flex flex-col items-center gap-2 text-white/40">
            <Filter className="w-10 h-10 stroke-1" />
            <p className="text-sm font-semibold">No Risk Items Found</p>
            <p className="text-xs">Adjust your search inputs or active dropdown filters.</p>
          </div>
        ) : null}

        {items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#131B2E] border-b border-white/5 text-white/50 text-xs font-semibold uppercase tracking-wider">
                  <th className="px-6 py-4">Product Name</th>
                  <th className="px-6 py-4">Dept</th>
                  <th className="px-6 py-4 text-right">Stock</th>
                  <th className="px-6 py-4 text-right">30d Forecast</th>
                  <th className="px-6 py-4 text-right text-rose-400">Shortage</th>
                  <th className="px-6 py-4">Priority</th>
                  <th className="px-6 py-4">Category</th>
                  <th className="px-6 py-4 text-right text-indigo-400">Rec. PO</th>
                  <th className="px-6 py-4">Reason</th>
                  <th className="px-4 py-4 w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {items.map((item) => (
                  <tr
                    key={item.item_id}
                    onClick={() => router.push(`/sku/${item.item_id}`)}
                    className="hover:bg-white/[0.02] cursor-pointer transition-colors duration-200 text-sm group"
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-semibold text-white group-hover:text-indigo-400 transition-colors">
                          {item.product_name}
                        </p>
                        <p className="text-[10px] text-white/30 font-mono mt-0.5">{item.item_id}</p>
                      </div>
                    </td>
                    
                    <td className="px-6 py-4">
                      <span className="text-xs font-medium text-white/60 bg-white/5 px-2.5 py-1 rounded-lg">
                        {item.dept_id}
                      </span>
                    </td>
                    
                    <td className="px-6 py-4 text-right font-medium text-white/80">
                      {item.available_inventory}
                    </td>
                    
                    <td className="px-6 py-4 text-right text-white/60">
                      {Math.round(item.forecast_30d).toLocaleString()}
                    </td>
                    
                    <td className="px-6 py-4 text-right font-bold text-rose-400">
                      {item.shortage_quantity > 0 ? item.shortage_quantity : '-'}
                    </td>
                    
                    <td className="px-6 py-4">
                      <span className={`text-xs px-2.5 py-1 rounded-lg border font-semibold ${getPriorityBadge(item.procurement_priority)}`}>
                        {item.procurement_priority}
                      </span>
                    </td>
                    
                    <td className="px-6 py-4">
                      <span className={`text-xs px-2.5 py-1 rounded-lg border font-medium ${getCategoryBadge(item.procurement_category)}`}>
                        {item.procurement_category}
                      </span>
                    </td>
                    
                    <td className="px-6 py-4 text-right font-bold text-indigo-400">
                      {item.recommended_po_qty.toLocaleString()}
                    </td>
                    
                    <td className="px-6 py-4 text-xs text-white/40 max-w-[200px] truncate" title={item.procurement_reason}>
                      {item.procurement_reason}
                    </td>
                    
                    <td className="px-4 py-4 text-center">
                      <ChevronRight className="w-4 h-4 text-white/20 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      {/* AI Copilot */}
      <CopilotChat />
    </div>
  );
}
