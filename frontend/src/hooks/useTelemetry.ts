import { useState, useEffect, useRef, useCallback } from 'react';
import { Snapshot, StaticInfo } from '../types/metrics';

export function useTelemetry() {
  const [staticInfo, setStaticInfo] = useState<StaticInfo | null>(null);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [latest, setLatest] = useState<Snapshot | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const [windowSeconds, setWindowSeconds] = useState<number>(300); // default 5m

  const wsRef = useRef<WebSocket | null>(null);
  const pingTimeRef = useRef<number>(0);
  const reconnectTimeoutRef = useRef<any>(null);
  const isPausedRef = useRef<boolean>(isPaused);
  isPausedRef.current = isPaused;

  // 1. Fetch static system info
  useEffect(() => {
    fetch('/api/info', { credentials: 'same-origin' })
      .then((res) => res.json())
      .then((data) => setStaticInfo(data))
      .catch((err) => console.error('Failed to load system info:', err));

    fetch('/api/history', { credentials: 'same-origin' })
      .then((res) => res.json())
      .then((data: Snapshot[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setHistory(data);
          setLatest(data[data.length - 1]);
        }
      })
      .catch((err) => console.error('Failed to load history:', err));
  }, []);

  // 2. Setup WebSocket with auto-reconnect
  const connectWs = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/metrics`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      // Measure latency
      pingTimeRef.current = performance.now();
      try {
        ws.send('ping');
      } catch (e) {
        // ignore
      }
    };

    ws.onmessage = (event) => {
      if (event.data === 'pong') {
        const roundTrip = Math.round(performance.now() - pingTimeRef.current);
        setLatencyMs(roundTrip);
        return;
      }

      try {
        const snap: Snapshot = JSON.parse(event.data);
        if (!isPausedRef.current) {
          setLatest(snap);
          setHistory((prev) => {
            const next = [...prev, snap];
            // Keep last 900 points in frontend memory
            if (next.length > 900) {
              return next.slice(next.length - 900);
            }
            return next;
          });
        }
      } catch (err) {
        console.error('Error parsing snapshot JSON:', err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      reconnectTimeoutRef.current = setTimeout(() => {
        connectWs();
      }, 2000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connectWs();

    // Ping every 10s for latency indicator
    const pingInterval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        pingTimeRef.current = performance.now();
        try {
          wsRef.current.send('ping');
        } catch (e) {
          // ignore
        }
      }
    }, 10000);

    return () => {
      clearInterval(pingInterval);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWs]);

  // Pause live polling when tab is hidden to save client resources
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // tab backgrounded
      } else {
        // refresh history on foreground
        fetch('/api/history', { credentials: 'same-origin' })
          .then((res) => res.json())
          .then((data: Snapshot[]) => {
            if (Array.isArray(data) && data.length > 0) {
              setHistory(data);
              setLatest(data[data.length - 1]);
            }
          })
          .catch(() => {});
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  const togglePause = useCallback(() => {
    setIsPaused((prev) => !prev);
  }, []);

  // Filter history to current window
  const windowedHistory = useCallback(() => {
    if (history.length === 0) return [];
    const lastTime = history[history.length - 1].timestamp;
    const cutoff = lastTime - windowSeconds;
    return history.filter((s) => s.timestamp >= cutoff);
  }, [history, windowSeconds])();

  return {
    staticInfo,
    latest,
    history: windowedHistory,
    rawHistory: history,
    isConnected,
    isPaused,
    togglePause,
    latencyMs,
    windowSeconds,
    setWindowSeconds,
  };
}
