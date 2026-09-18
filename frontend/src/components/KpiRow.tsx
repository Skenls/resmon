import React from 'react';
import { Snapshot } from '../types/metrics';
import { Cpu, Database, HardDrive, Network, AlertTriangle } from 'lucide-react';

interface KpiRowProps {
  latest: Snapshot | null;
}

export const KpiRow: React.FC<KpiRowProps> = ({ latest }) => {
  if (!latest) return null;

  const formatBytes = (bytes: number) => {
    const gb = bytes / (1024 * 1024 * 1024);
    return `${gb.toFixed(1)} GB`;
  };

  const cpu = latest.cpu;
  const mem = latest.memory;
  const disk = latest.disk;
  const net = latest.network;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {/* 1. CPU KPI */}
      <div className="glass-panel p-4 flex flex-col justify-between border-l-4 border-l-cyan-500">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-mono uppercase tracking-wider font-semibold">Processor</span>
          <Cpu className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="flex items-baseline gap-2 mb-2">
          <span className="text-3xl font-bold font-mono text-white tracking-tight">
            {cpu.overall.toFixed(1)}%
          </span>
          <span className="text-xs text-slate-400 font-mono">
            {cpu.cores.length} {cpu.cores.length === 1 ? 'core' : 'cores'}
          </span>
        </div>
        <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
          <span>Load: {cpu.loadavg.join(', ')}</span>
          {cpu.psi_some?.avg10 !== undefined && cpu.psi_some.avg10 > 0 && (
            <span className="flex items-center gap-1 text-rose-400" title="CPU Pressure Stall (avg10)">
              <AlertTriangle className="w-3 h-3" />
              {cpu.psi_some.avg10.toFixed(2)}%
            </span>
          )}
        </div>
      </div>

      {/* 2. Memory KPI */}
      <div className="glass-panel p-4 flex flex-col justify-between border-l-4 border-l-purple-500">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-mono uppercase tracking-wider font-semibold">Memory & Swap</span>
          <Database className="w-4 h-4 text-purple-400" />
        </div>
        <div className="flex items-baseline gap-2 mb-2">
          <span className="text-3xl font-bold font-mono text-white tracking-tight">
            {mem.percent.toFixed(1)}%
          </span>
          <span className="text-xs text-slate-400 font-mono">
            {formatBytes(mem.used)} / {formatBytes(mem.total)}
          </span>
        </div>
        <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
          <span>Swap: {mem.swap_percent.toFixed(1)}%</span>
          <span title="Page faults per second">
            PF: {mem.page_faults_minor_sec.toLocaleString()} /s
          </span>
        </div>
      </div>

      {/* 3. Disk I/O KPI */}
      <div className="glass-panel p-4 flex flex-col justify-between border-l-4 border-l-amber-500">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-mono uppercase tracking-wider font-semibold">Disk Throughput</span>
          <HardDrive className="w-4 h-4 text-amber-400" />
        </div>
        <div className="flex items-baseline gap-2 mb-2">
          <span className="text-3xl font-bold font-mono text-white tracking-tight">
            {(disk.read_mbs + disk.write_mbs).toFixed(2)}
          </span>
          <span className="text-xs text-slate-400 font-mono">MB/s total</span>
        </div>
        <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
          <span className="text-amber-300">R: {disk.read_mbs} MB/s</span>
          <span className="text-orange-400">W: {disk.write_mbs} MB/s</span>
          <span>{(disk.read_iops + disk.write_iops).toFixed(0)} IOPS</span>
        </div>
      </div>

      {/* 4. Network KPI */}
      <div className="glass-panel p-4 flex flex-col justify-between border-l-4 border-l-emerald-500">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-mono uppercase tracking-wider font-semibold">Network Activity</span>
          <Network className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="flex items-baseline gap-2 mb-2">
          <span className="text-3xl font-bold font-mono text-white tracking-tight">
            {(net.rx_kbs + net.tx_kbs).toFixed(1)}
          </span>
          <span className="text-xs text-slate-400 font-mono">KB/s</span>
        </div>
        <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
          <span className="text-emerald-400">↓ {net.rx_kbs} KB/s</span>
          <span className="text-teal-300">↑ {net.tx_kbs} KB/s</span>
          <span>Est: {net.connections_count?.ESTABLISHED || 0}</span>
        </div>
      </div>
    </div>
  );
};
