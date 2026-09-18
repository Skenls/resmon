import React from 'react';
import { useTelemetry } from './hooks/useTelemetry';
import { Header } from './components/Header';
import { KpiRow } from './components/KpiRow';
import { CpuSection } from './components/CpuSection';
import { MemorySection } from './components/MemorySection';
import { DiskSection } from './components/DiskSection';
import { NetworkSection } from './components/NetworkSection';
import { Activity } from 'lucide-react';

export default function App() {
  const {
    staticInfo,
    latest,
    history,
    isConnected,
    isPaused,
    togglePause,
    latencyMs,
    windowSeconds,
    setWindowSeconds,
  } = useTelemetry();

  if (!latest && !staticInfo) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
        <div className="flex flex-col items-center gap-4 glass-panel p-8 max-w-sm text-center">
          <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 animate-pulse">
            <Activity className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white mb-1">ResMon Web</h2>
            <p className="text-xs font-mono text-slate-400">Connecting to telemetry stream...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-slate-100 p-4 md:p-6 max-w-7xl mx-auto">
      {/* 1. Header Bar */}
      <Header
        staticInfo={staticInfo}
        isConnected={isConnected}
        isPaused={isPaused}
        togglePause={togglePause}
        latencyMs={latencyMs}
        windowSeconds={windowSeconds}
        setWindowSeconds={setWindowSeconds}
      />

      {/* 2. Top Summary KPI Row */}
      <KpiRow latest={latest} />

      {/* 3. CPU & Cores */}
      <CpuSection history={history} latest={latest} staticInfo={staticInfo} />

      {/* 4. Memory, Swap & Page Faults */}
      <MemorySection history={history} latest={latest} />

      {/* 5. Disk Operations & Partitions */}
      <DiskSection history={history} latest={latest} />

      {/* 6. Network Activity & Open Ports */}
      <NetworkSection history={history} latest={latest} />

      {/* Footer */}
      <footer className="mt-8 pt-4 border-t border-slate-800/80 text-center text-xs font-mono text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-2">
        <div>ResMon Web • High-Performance Linux Telemetry</div>
        <div>In-Memory Ring Buffer • Zero Disk Wear • Sampling &lt;2ms</div>
      </footer>
    </div>
  );
}
