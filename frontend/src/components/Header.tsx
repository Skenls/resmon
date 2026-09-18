import React from 'react';
import { StaticInfo } from '../types/metrics';
import { Play, Pause, Activity, Server, Clock, Wifi } from 'lucide-react';

interface HeaderProps {
  staticInfo: StaticInfo | null;
  isConnected: boolean;
  isPaused: boolean;
  togglePause: () => void;
  latencyMs: number;
  windowSeconds: number;
  setWindowSeconds: (sec: number) => void;
}

export const Header: React.FC<HeaderProps> = ({
  staticInfo,
  isConnected,
  isPaused,
  togglePause,
  latencyMs,
  windowSeconds,
  setWindowSeconds,
}) => {
  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hrs = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (days > 0) return `${days}d ${hrs}h ${mins}m`;
    if (hrs > 0) return `${hrs}h ${mins}m`;
    return `${mins}m ${seconds % 60}s`;
  };

  return (
    <header className="glass-panel px-5 py-4 mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      {/* Brand & System Identification */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-glow">
          <Activity className="w-6 h-6 animate-pulse-slow" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              ResMon <span className="text-xs font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">Linux Telemetry</span>
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 mt-1 font-mono">
            <span className="flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-slate-400" />
              {staticInfo ? `${staticInfo.hostname} (${staticInfo.os})` : 'Connecting...'}
            </span>
            <span>•</span>
            <span>Kernel: {staticInfo?.kernel || '...'}</span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              Up: {staticInfo ? formatUptime(staticInfo.uptime_seconds) : '...'}
            </span>
          </div>
        </div>
      </div>

      {/* Live Status & Controls */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Connection & Latency Badge */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/60 border border-slate-700/60 text-xs font-mono">
          <span className="relative flex h-2.5 w-2.5">
            {isConnected && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            )}
            <span
              className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                isConnected ? 'bg-emerald-500' : 'bg-rose-500'
              }`}
            ></span>
          </span>
          <span className={isConnected ? 'text-emerald-400' : 'text-rose-400'}>
            {isConnected ? 'LIVE' : 'DISCONNECTED'}
          </span>
          {isConnected && (
            <>
              <span className="text-slate-600">|</span>
              <span className="text-slate-400 flex items-center gap-1">
                <Wifi className="w-3 h-3" />
                {latencyMs}ms
              </span>
            </>
          )}
        </div>

        {/* Window Selector */}
        <div className="flex items-center rounded-lg bg-slate-900/60 border border-slate-700/60 p-0.5 text-xs font-mono">
          {[
            { label: '1m', sec: 60 },
            { label: '5m', sec: 300 },
            { label: '15m', sec: 900 },
          ].map((item) => (
            <button
              key={item.sec}
              onClick={() => setWindowSeconds(item.sec)}
              className={`px-2.5 py-1 rounded transition-colors ${
                windowSeconds === item.sec
                  ? 'bg-cyan-500 text-slate-950 font-semibold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Pause/Resume Button */}
        <button
          onClick={togglePause}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all border ${
            isPaused
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 hover:bg-amber-500/30'
              : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700 hover:text-white'
          }`}
          title={isPaused ? 'Resume live updates' : 'Pause chart updates'}
        >
          {isPaused ? <Play className="w-3.5 h-3.5 fill-current" /> : <Pause className="w-3.5 h-3.5 fill-current" />}
          <span>{isPaused ? 'RESUME' : 'PAUSE'}</span>
        </button>
      </div>
    </header>
  );
};
