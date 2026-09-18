import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { Snapshot, StaticInfo } from '../types/metrics';
import { Cpu, Zap, Activity } from 'lucide-react';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend
);

interface CpuSectionProps {
  history: Snapshot[];
  latest: Snapshot | null;
  staticInfo: StaticInfo | null;
}

export const CpuSection: React.FC<CpuSectionProps> = ({ history, latest, staticInfo }) => {
  if (!latest) return null;

  const labels = history.map((s) => {
    const d = new Date(s.timestamp * 1000);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  });

  const overallCpuData = history.map((s) => s.cpu.overall);
  const psiData = history.map((s) => s.cpu.psi_some?.avg10 || 0);

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Overall CPU %',
        data: overallCpuData,
        borderColor: '#06B6D4',
        backgroundColor: 'rgba(6, 182, 212, 0.12)',
        fill: true,
        tension: 0.25,
        borderWidth: 2,
        pointRadius: 0,
      },
      {
        label: 'CPU Stall Latency (PSI avg10 %)',
        data: psiData,
        borderColor: '#F43F5E',
        backgroundColor: 'rgba(244, 63, 94, 0.08)',
        fill: true,
        tension: 0.25,
        borderWidth: 1.5,
        borderDash: [4, 4],
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
        ticks: { color: '#64748B', font: { family: '"JetBrains Mono"', size: 10 }, maxTicksLimit: 8 },
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
        labels: {
          color: '#94A3B8',
          font: { family: '"Plus Jakarta Sans"', size: 12 },
          boxWidth: 12,
        },
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

  const getCoreColor = (pct: number) => {
    if (pct < 50) return 'bg-cyan-500 text-cyan-300';
    if (pct < 80) return 'bg-amber-500 text-amber-300';
    return 'bg-rose-500 text-rose-300';
  };

  return (
    <div className="glass-panel p-5 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide">CPU Load & Pressure Stall Latency</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-slate-400">
          <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700">
            {staticInfo?.cpu_model || 'Processor'}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700">
            {latest.cpu.cores.length} logical cores
          </span>
        </div>
      </div>

      {/* Main Streaming Chart */}
      <div className="h-56 w-full mb-6">
        <Line data={chartData} options={chartOptions} />
      </div>

      {/* Per-Core Breakdown */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            Individual Core Activity
          </span>
          <span className="text-xs font-mono text-slate-500">
            Overall: <span className="text-cyan-400 font-semibold">{latest.cpu.overall.toFixed(1)}%</span>
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
          {latest.cpu.cores.map((corePct, idx) => {
            return (
              <div key={idx} className="glass-panel-subtle p-2 flex flex-col justify-between">
                <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-1">
                  <span>Core {idx}</span>
                  <span className="font-semibold text-slate-200">{corePct.toFixed(0)}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${getCoreColor(corePct).split(' ')[0]}`}
                    style={{ width: `${Math.min(100, Math.max(0, corePct))}%` }}
                  ></div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
