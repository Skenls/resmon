import React from 'react';
import { Line } from 'react-chartjs-2';
import { Snapshot } from '../types/metrics';
import { HardDrive, ArrowDown, ArrowUp, Activity } from 'lucide-react';

interface DiskSectionProps {
  history: Snapshot[];
  latest: Snapshot | null;
}

export const DiskSection: React.FC<DiskSectionProps> = ({ history, latest }) => {
  if (!latest) return null;

  const disk = latest.disk;

  const labels = history.map((s) => {
    const d = new Date(s.timestamp * 1000);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  });

  const readData = history.map((s) => s.disk.read_mbs);
  const writeData = history.map((s) => s.disk.write_mbs);

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Read (MB/s)',
        data: readData,
        borderColor: '#F59E0B',
        backgroundColor: 'rgba(245, 158, 11, 0.12)',
        fill: true,
        tension: 0.2,
        borderWidth: 2,
        pointRadius: 0,
      },
      {
        label: 'Write (MB/s)',
        data: writeData,
        borderColor: '#EA580C',
        backgroundColor: 'rgba(234, 88, 12, 0.08)',
        fill: true,
        tension: 0.2,
        borderWidth: 1.5,
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
        grid: { color: 'rgba(255, 255, 255, 0.04)' },
        ticks: {
          color: '#64748B',
          font: { family: '"JetBrains Mono"', size: 10 },
          callback: (val: any) => `${val} MB/s`,
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

  const formatGb = (bytes: number) => (bytes / (1024 * 1024 * 1024)).toFixed(1);

  return (
    <div className="glass-panel p-5 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <HardDrive className="w-5 h-5 text-amber-400" />
          <h2 className="text-base font-bold text-white tracking-wide">Disk Operations & Storage Mounts</h2>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
          <span className="flex items-center gap-1 text-amber-300">
            <ArrowDown className="w-3.5 h-3.5" /> Read: {disk.read_mbs} MB/s ({disk.read_iops} IOPS)
          </span>
          <span>•</span>
          <span className="flex items-center gap-1 text-orange-400">
            <ArrowUp className="w-3.5 h-3.5" /> Write: {disk.write_mbs} MB/s ({disk.write_iops} IOPS)
          </span>
          {disk.psi_some?.avg10 !== undefined && disk.psi_some.avg10 > 0 && (
            <>
              <span>•</span>
              <span className="text-rose-400 flex items-center gap-1">
                <Activity className="w-3 h-3" />
                I/O Stall: {disk.psi_some.avg10.toFixed(2)}%
              </span>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Throughput Chart */}
        <div className="lg:col-span-2 h-56 w-full">
          <Line data={chartData} options={chartOptions} />
        </div>

        {/* Partitions List */}
        <div className="flex flex-col justify-between">
          <div className="text-xs font-mono text-slate-400 mb-2 uppercase tracking-wider">
            Filesystem Usage
          </div>
          <div className="flex flex-col gap-2.5 overflow-y-auto max-h-52 pr-1">
            {disk.partitions && disk.partitions.length > 0 ? (
              disk.partitions.map((part, idx) => (
                <div key={idx} className="glass-panel-subtle p-2.5">
                  <div className="flex items-center justify-between text-xs font-mono mb-1">
                    <span className="font-semibold text-slate-200 truncate max-w-[140px]" title={part.mountpoint}>
                      {part.mountpoint}
                    </span>
                    <span className="text-amber-300 font-bold">{part.percent}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden mb-1.5">
                    <div
                      className={`h-full rounded-full ${
                        part.percent > 90 ? 'bg-rose-500' : part.percent > 75 ? 'bg-amber-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${part.percent}%` }}
                    ></div>
                  </div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                    <span className="truncate max-w-[120px]" title={part.device}>{part.device}</span>
                    <span>{formatGb(part.used)} / {formatGb(part.total)} GB</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-500 font-mono italic">No partitions reported</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
