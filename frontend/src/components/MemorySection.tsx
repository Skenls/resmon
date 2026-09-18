import React from 'react';
import { Line } from 'react-chartjs-2';
import { Snapshot } from '../types/metrics';
import { Database, Layers, RefreshCw, AlertCircle } from 'lucide-react';

interface MemorySectionProps {
  history: Snapshot[];
  latest: Snapshot | null;
}

export const MemorySection: React.FC<MemorySectionProps> = ({ history, latest }) => {
  if (!latest) return null;

  const mem = latest.memory;

  const formatGb = (bytes: number) => (bytes / (1024 * 1024 * 1024)).toFixed(2);

  const labels = history.map((s) => {
    const d = new Date(s.timestamp * 1000);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  });

  const ramData = history.map((s) => s.memory.percent);
  const swapData = history.map((s) => s.memory.swap_percent);

  const chartData = {
    labels,
    datasets: [
      {
        label: 'RAM Used %',
        data: ramData,
        borderColor: '#8B5CF6',
        backgroundColor: 'rgba(139, 92, 246, 0.15)',
        fill: true,
        tension: 0.2,
        borderWidth: 2,
        pointRadius: 0,
      },
      {
        label: 'Swap Used %',
        data: swapData,
        borderColor: '#EC4899',
        backgroundColor: 'rgba(236, 72, 153, 0.05)',
        fill: true,
        tension: 0.2,
        borderWidth: 1.5,
        borderDash: [3, 3],
        pointRadius: 0,
      },
    ],
  };

  const chartOptions: any = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.04)' },
        ticks: { color: '#64748B', font: { family: '"JetBrains Mono"', size: 10 }, maxTicksLimit: 6 },
      },
      y: {
        min: 0,
        max: 100,
        grid: { color: 'rgba(255, 255, 255, 0.04)' },
        ticks: {
          color: '#64748B',
          font: { family: '"JetBrains Mono"', size: 10 },
          callback: (val: any) => `${val}%`,
        },
      },
    },
    plugins: {
      legend: {
        labels: { color: '#94A3B8', font: { family: '"Plus Jakarta Sans"', size: 12 }, boxWidth: 12 },
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        titleColor: '#F8FAFC',
        bodyColor: '#94A3B8',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
      },
    },
  };

  return (
    <div className="glass-panel p-5 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Database className="w-5 h-5 text-purple-400" />
          <h2 className="text-base font-bold text-white tracking-wide">RAM, Swap & Memory Access Dynamics</h2>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
          <span>Total: <strong className="text-white">{formatGb(mem.total)} GB</strong></span>
          <span>•</span>
          <span>Available: <strong className="text-emerald-400">{formatGb(mem.available)} GB</strong></span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Memory Chart */}
        <div className="lg:col-span-2 h-56 w-full">
          <Line data={chartData} options={chartOptions} />
        </div>

        {/* Detailed Memory & Access Metrics */}
        <div className="flex flex-col justify-between gap-3">
          {/* Visual RAM Usage Bar */}
          <div className="glass-panel-subtle p-3">
            <div className="flex justify-between text-xs font-mono mb-1.5">
              <span className="text-slate-400 flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-purple-400" />
                Physical RAM Breakdown
              </span>
              <span className="text-purple-300 font-bold">{mem.percent.toFixed(1)}%</span>
            </div>
            <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden flex">
              <div
                className="h-full bg-purple-500"
                style={{ width: `${(mem.used / mem.total) * 100}%` }}
                title={`Used: ${formatGb(mem.used)} GB`}
              ></div>
              <div
                className="h-full bg-indigo-500/70"
                style={{ width: `${((mem.cached + mem.buffers) / mem.total) * 100}%` }}
                title={`Cache/Buffers: ${formatGb(mem.cached + mem.buffers)} GB`}
              ></div>
            </div>
            <div className="flex justify-between text-[11px] font-mono text-slate-400 mt-2">
              <span>Used: {formatGb(mem.used)} GB</span>
              <span>Cache: {formatGb(mem.cached + mem.buffers)} GB</span>
              <span>Free: {formatGb(mem.free)} GB</span>
            </div>
          </div>

          {/* Swap Bar */}
          <div className="glass-panel-subtle p-3">
            <div className="flex justify-between text-xs font-mono mb-1">
              <span className="text-slate-400">Swap Memory</span>
              <span className="text-pink-400 font-bold">{mem.swap_percent.toFixed(1)}%</span>
            </div>
            <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-pink-500 transition-all duration-300"
                style={{ width: `${mem.swap_percent}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-[11px] font-mono text-slate-400 mt-1.5">
              <span>Used: {formatGb(mem.swap_used)} GB</span>
              <span>Total: {formatGb(mem.swap_total)} GB</span>
            </div>
          </div>

          {/* Page Faults & Memory Pressure */}
          <div className="glass-panel-subtle p-3 flex flex-col justify-between">
            <div className="text-xs font-mono text-slate-400 mb-1 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
                Memory Access / Page Faults
              </span>
              {mem.psi_some?.avg10 !== undefined && mem.psi_some.avg10 > 0 && (
                <span className="flex items-center gap-1 text-rose-400 text-[10px]">
                  <AlertCircle className="w-3 h-3" />
                  Stall: {mem.psi_some.avg10.toFixed(2)}%
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 mt-1 font-mono text-xs">
              <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                <div className="text-[10px] text-slate-500">Minor Faults</div>
                <div className="text-white font-bold">{mem.page_faults_minor_sec.toLocaleString()} <span className="text-[10px] text-slate-400 font-normal">/s</span></div>
              </div>
              <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                <div className="text-[10px] text-slate-500">Major Faults (I/O)</div>
                <div className={`font-bold ${mem.page_faults_major_sec > 0 ? 'text-amber-400' : 'text-white'}`}>
                  {mem.page_faults_major_sec.toLocaleString()} <span className="text-[10px] text-slate-400 font-normal">/s</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
