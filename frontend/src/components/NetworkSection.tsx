import React, { useState } from 'react';
import { Line } from 'react-chartjs-2';
import { Snapshot } from '../types/metrics';
import { Network, ArrowDown, ArrowUp, Search, Shield, Radio } from 'lucide-react';

interface NetworkSectionProps {
  history: Snapshot[];
  latest: Snapshot | null;
}

export const NetworkSection: React.FC<NetworkSectionProps> = ({ history, latest }) => {
  const [filterText, setFilterText] = useState('');
  const [protoFilter, setProtoFilter] = useState<'ALL' | 'tcp' | 'udp'>('ALL');

  if (!latest) return null;

  const net = latest.network;

  const labels = history.map((s) => {
    const d = new Date(s.timestamp * 1000);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  });

  const rxData = history.map((s) => s.network.rx_kbs);
  const txData = history.map((s) => s.network.tx_kbs);

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Rx (Receive KB/s)',
        data: rxData,
        borderColor: '#10B981',
        backgroundColor: 'rgba(16, 185, 129, 0.12)',
        fill: true,
        tension: 0.2,
        borderWidth: 2,
        pointRadius: 0,
      },
      {
        label: 'Tx (Transmit KB/s)',
        data: txData,
        borderColor: '#14B8A6',
        backgroundColor: 'rgba(20, 184, 166, 0.08)',
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
          callback: (val: any) => `${val} KB/s`,
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

  const filteredPorts = (net.listening_ports || []).filter((p) => {
    if (protoFilter !== 'ALL' && p.proto.toLowerCase() !== protoFilter.toLowerCase()) {
      return false;
    }
    if (!filterText) return true;
    const query = filterText.toLowerCase();
    return (
      p.port.toString().includes(query) ||
      p.process.toLowerCase().includes(query) ||
      p.address.toLowerCase().includes(query) ||
      (p.pid && p.pid.toString().includes(query))
    );
  });

  return (
    <div className="glass-panel p-5 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Network className="w-5 h-5 text-emerald-400" />
          <h2 className="text-base font-bold text-white tracking-wide">Network Bandwidth, Sockets & Open Ports</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-slate-400">
          <span className="flex items-center gap-1 text-emerald-400">
            <ArrowDown className="w-3.5 h-3.5" /> Rx: {net.rx_kbs} KB/s
          </span>
          <span>•</span>
          <span className="flex items-center gap-1 text-teal-300">
            <ArrowUp className="w-3.5 h-3.5" /> Tx: {net.tx_kbs} KB/s
          </span>
          <span>•</span>
          <span>Packets: {net.packets_rx_sec + net.packets_tx_sec} /s</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
        {/* Network Throughput Chart */}
        <div className="lg:col-span-8 h-56 w-full">
          <Line data={chartData} options={chartOptions} />
        </div>

        {/* Connection States Summary */}
        <div className="lg:col-span-4 flex flex-col justify-between glass-panel-subtle p-3">
          <div className="text-xs font-mono text-slate-400 mb-2 uppercase tracking-wider flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-emerald-400" />
            Socket States
          </div>
          <div className="grid grid-cols-2 gap-2 font-mono text-xs">
            {Object.entries(net.connections_count || {}).map(([state, count]) => (
              <div key={state} className="bg-slate-900/60 p-2 rounded border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">{state}</div>
                <div className={`text-base font-bold ${state === 'ESTABLISHED' ? 'text-emerald-400' : state === 'LISTEN' ? 'text-cyan-400' : 'text-slate-200'}`}>
                  {count || 0}
                </div>
              </div>
            ))}
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-2">
            Total Listening Ports: <strong className="text-cyan-300">{net.listening_ports?.length || 0}</strong>
          </div>
        </div>
      </div>

      {/* Open & Active Listening Ports Table */}
      <div className="pt-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-200 font-mono uppercase tracking-wider">
              Open & Active Listening Ports ({filteredPorts.length})
            </h3>
          </div>

          <div className="flex items-center gap-2">
            {/* Protocol Filter */}
            <div className="flex rounded bg-slate-900 border border-slate-800 p-0.5 text-xs font-mono">
              {(['ALL', 'tcp', 'udp'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setProtoFilter(p)}
                  className={`px-2 py-0.5 rounded text-[11px] uppercase ${
                    protoFilter === p ? 'bg-cyan-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>

            {/* Search Box */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                placeholder="Search port, process, PID..."
                className="bg-slate-900 border border-slate-700/80 rounded-lg pl-8 pr-3 py-1 text-xs text-slate-200 placeholder-slate-500 font-mono focus:outline-none focus:border-cyan-500 w-44 sm:w-56"
              />
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-lg border border-slate-800 max-h-60 overflow-y-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] sticky top-0 border-b border-slate-800">
              <tr>
                <th className="py-2 px-3">Port</th>
                <th className="py-2 px-3">Proto</th>
                <th className="py-2 px-3">Bind Address</th>
                <th className="py-2 px-3">Process Name</th>
                <th className="py-2 px-3">PID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
              {filteredPorts.length > 0 ? (
                filteredPorts.map((p, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-2 px-3 font-bold text-cyan-400">{p.port}</td>
                    <td className="py-2 px-3 uppercase text-slate-300">
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 border border-slate-700">
                        {p.proto}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-400">{p.address}</td>
                    <td className="py-2 px-3 font-semibold text-slate-200">
                      {p.process !== 'unknown' ? p.process : <span className="text-slate-500 italic">unknown</span>}
                    </td>
                    <td className="py-2 px-3 text-slate-400">{p.pid || '-'}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-slate-500 italic">
                    No ports matching current filter
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
