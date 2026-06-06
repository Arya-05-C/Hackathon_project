/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { 
  fetchDashboard 
} from '../lib/api';
import { DashboardData } from '../types';
import { 
  Package, 
  AlertTriangle, 
  Zap, 
  ShieldAlert, 
  FileText, 
  ShoppingBag,
  ArrowUpRight
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';
import CopilotChat from '../components/CopilotChat';

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    fetchDashboard()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError('Failed to connect to the backend server. Please verify FastAPI is running.');
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="min-h-[70vh] flex flex-col justify-center items-center gap-4">
        <div className="w-12 h-12 rounded-full border-4 border-indigo-500/20 border-t-indigo-500 animate-spin" />
        <p className="text-white/60 text-sm font-semibold">Loading dashboard intelligence...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-[70vh] flex flex-col justify-center items-center gap-4 text-center max-w-md mx-auto">
        <div className="p-4 bg-rose-500/10 rounded-2xl border border-rose-500/20 text-rose-400">
          <AlertTriangle className="w-10 h-10" />
        </div>
        <h2 className="text-lg font-bold text-white">Server Connection Error</h2>
        <p className="text-sm text-white/50">{error || "Could not retrieve dashboard statistics."}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition-all"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  // Priority Colors
  const PRIORITY_COLORS: Record<string, string> = {
    Critical: '#F43F5E', // Rose
    High: '#F59E0B',     // Amber
    Medium: '#3B82F6',   // Blue
    Low: '#10B981'       // Emerald
  };

  // Category Colors
  const CATEGORY_COLORS: Record<string, string> = {
    Emergency: '#F43F5E',
    Urgent: '#F59E0B',
    Planned: '#3B82F6',
    Monitor: '#10B981'
  };

  const DEPT_COLORS = ['#6366F1', '#3B82F6', '#10B981', '#F59E0B', '#8B5CF6'];

  const kpiCards = [
    {
      title: 'Total SKUs',
      value: data.total_skus,
      desc: 'Monitored items',
      icon: Package,
      glow: 'glow-blue',
      textColor: 'text-blue-400',
      bgColor: 'bg-blue-500/10'
    },
    {
      title: 'Total Shortage Qty',
      value: data.total_shortage_quantity.toLocaleString(),
      desc: 'Units needed',
      icon: AlertTriangle,
      glow: 'glow-rose',
      textColor: 'text-rose-400',
      bgColor: 'bg-rose-500/10'
    },
    {
      title: 'Recommended PO Qty',
      value: data.total_recommended_po_qty.toLocaleString(),
      desc: 'Replenishment bulk',
      icon: ShoppingBag,
      glow: 'glow-purple',
      textColor: 'text-purple-400',
      bgColor: 'bg-purple-500/10'
    },
    {
      title: 'Procurement Alerts',
      value: data.procurement_alerts,
      desc: 'Below reorder point',
      icon: FileText,
      glow: 'glow-amber',
      textColor: 'text-amber-400',
      bgColor: 'bg-amber-500/10'
    },
    {
      title: 'Procurement Triggers',
      value: data.procurement_triggers,
      desc: 'Replenishments required',
      icon: Zap,
      glow: 'glow-indigo',
      textColor: 'text-indigo-400',
      bgColor: 'bg-indigo-500/10'
    },
    {
      title: 'Emergency Orders',
      value: data.emergency_procurements,
      desc: 'Stockout within 7 days',
      icon: ShieldAlert,
      glow: 'glow-rose',
      textColor: 'text-rose-400',
      bgColor: 'bg-rose-500/20 border border-rose-500/30'
    }
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Title */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white via-white to-white/60 bg-clip-text text-transparent">
            Executive Procurement Dashboard
          </h1>
          <p className="text-white/50 text-sm mt-1">
            Real-time supply chain alerts, shortages analysis, and allocation intelligence.
          </p>
        </div>
        
        <button
          onClick={() => router.push('/workbench')}
          className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-semibold text-sm transition-all shadow-lg shadow-indigo-600/20 active:scale-95 cursor-pointer"
        >
          Open Procurement Workbench
          <ArrowUpRight className="w-4 h-4" />
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-5">
        {kpiCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              className={`glass-panel p-5 rounded-2xl flex flex-col justify-between min-h-[130px] ${card.glow}`}
            >
              <div className="flex justify-between items-start">
                <span className="text-xs text-white/50 font-medium">{card.title}</span>
                <div className={`p-2 rounded-lg ${card.bgColor} ${card.textColor}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </div>
              
              <div className="mt-4">
                <p className="text-2xl font-bold text-white tracking-tight">{card.value}</p>
                <p className="text-[10px] text-white/30 font-medium mt-0.5">{card.desc}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Priority Distribution */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div>
            <h3 className="font-bold text-white text-base">Procurement Priority</h3>
            <p className="text-xs text-white/40">Risk severity breakdown across active SKUs</p>
          </div>
          
          <div className="h-64 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.priority_distribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={85}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, percent }) => `${name} (${((percent || 0) * 100).toFixed(0)}%)`}
                >
                  {data.priority_distribution.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={PRIORITY_COLORS[entry.name] || '#6366F1'} 
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Category Distribution */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div>
            <h3 className="font-bold text-white text-base">Procurement Gaps Category</h3>
            <p className="text-xs text-white/40">Urgencies based on days until stockout</p>
          </div>
          
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.category_distribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <YAxis stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <Tooltip cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={50}>
                  {data.category_distribution.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={CATEGORY_COLORS[entry.name] || '#6366F1'} 
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Department Distribution */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div>
            <h3 className="font-bold text-white text-base">Department Distribution</h3>
            <p className="text-xs text-white/40">Shortage items count grouped by product divisions</p>
          </div>
          
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart 
                data={data.department_distribution}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <YAxis dataKey="name" type="category" stroke="rgba(255,255,255,0.4)" fontSize={11} width={100} />
                <Tooltip cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
                <Bar dataKey="value" fill="#6366F1" radius={[0, 6, 6, 0]} maxBarSize={24}>
                  {data.department_distribution.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={DEPT_COLORS[index % DEPT_COLORS.length]} 
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top 10 Shortage SKUs */}
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div>
            <h3 className="font-bold text-white text-base">Top 10 Shortage SKUs</h3>
            <p className="text-xs text-white/40">Click a bar to open dynamic supplier recommender workbench</p>
          </div>
          
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.top_shortage_skus}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="item_id" stroke="rgba(255,255,255,0.4)" fontSize={10} tickLine={false} />
                <YAxis stroke="rgba(255,255,255,0.4)" fontSize={11} />
                <Tooltip 
                  formatter={(value, name, props) => [value, 'Shortage Quantity', props.payload.product_name]}
                  cursor={{ fill: 'rgba(255,255,255,0.02)' }} 
                />
                <Bar 
                  dataKey="shortage_quantity" 
                  fill="#EC4899" 
                  radius={[6, 6, 0, 0]} 
                  maxBarSize={32}
                  className="cursor-pointer"
                  onClick={(payload: any) => {
                    const itemId = payload?.item_id || payload?.activePayload?.[0]?.payload?.item_id;
                    if (itemId) {
                      router.push(`/sku/${itemId}`);
                    }
                  }}
                >
                  {data.top_shortage_skus.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={index === 0 ? '#F43F5E' : '#EC4899'} 
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* AI Procurement Copilot */}
      <CopilotChat />
    </div>
  );
}
