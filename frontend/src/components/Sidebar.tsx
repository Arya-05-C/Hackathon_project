'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  LayoutDashboard, 
  TableProperties, 
  BrainCircuit, 
  Cpu
} from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();

  const navItems = [
    {
      name: 'Dashboard',
      href: '/',
      icon: LayoutDashboard,
      description: 'Executive overview'
    },
    {
      name: 'Workbench',
      href: '/workbench',
      icon: TableProperties,
      description: 'Review risk items'
    }
  ];

  return (
    <aside className="w-64 border-r border-white/5 bg-[#0D1322]/80 backdrop-blur-xl flex flex-col h-screen sticky top-0">
      {/* Brand Header */}
      <div className="p-6 border-b border-white/5 flex items-center gap-3">
        <div className="p-2 bg-indigo-500/10 rounded-lg border border-indigo-500/20 text-indigo-400">
          <BrainCircuit className="w-6 h-6 animate-pulse" />
        </div>
        <div>
          <h1 className="text-lg font-bold bg-gradient-to-r from-indigo-200 to-blue-400 bg-clip-text text-transparent">
            ProcureIntel
          </h1>
          <span className="text-[10px] text-white/40 uppercase tracking-widest font-semibold">
            Decision Hub
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-4 px-4 py-3 rounded-xl transition-all duration-300 ${
                isActive
                  ? 'bg-gradient-to-r from-indigo-600/20 to-blue-600/10 border border-indigo-500/30 text-white shadow-lg shadow-indigo-500/5'
                  : 'text-white/60 hover:text-white hover:bg-white/5 border border-transparent'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-indigo-400' : 'text-white/50'}`} />
              <div>
                <p className="text-sm font-semibold">{item.name}</p>
                <p className="text-[10px] text-white/30 font-medium">{item.description}</p>
              </div>
            </Link>
          );
        })}
      </nav>

      {/* System Health Indicator */}
      <div className="p-4 border-t border-white/5 bg-black/20 m-4 rounded-xl space-y-3">
        <div className="flex items-center gap-2 text-[11px] text-white/40 font-semibold uppercase tracking-wider">
          <Cpu className="w-3.5 h-3.5 text-indigo-400" />
          <span>System Status</span>
        </div>
        
        <div className="space-y-2 text-xs">
          <div className="flex justify-between items-center">
            <span className="text-white/50">NIM Engine:</span>
            <span className="flex items-center gap-1.5 font-semibold text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              Active
            </span>
          </div>
          
          <div className="flex justify-between items-center">
            <span className="text-white/50">Model:</span>
            <span className="text-white/70 font-mono text-[10px] truncate max-w-[100px]">
              llama-3.2-3b
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
