export interface PsiMetrics {
  avg10?: number;
  avg60?: number;
  avg300?: number;
  total?: number;
}

export interface CpuMetrics {
  overall: number;
  cores: number[];
  loadavg: [number, number, number];
  psi_some: PsiMetrics;
}

export interface MemoryMetrics {
  total: number;
  used: number;
  free: number;
  available: number;
  buffers: number;
  cached: number;
  percent: number;
  swap_total: number;
  swap_used: number;
  swap_free: number;
  swap_percent: number;
  psi_some: PsiMetrics;
  psi_full?: PsiMetrics;
  page_faults_minor_sec: number;
  page_faults_major_sec: number;
}

export interface DiskPartition {
  device: string;
  mountpoint: string;
  fstype: string;
  total: number;
  used: number;
  free: number;
  percent: number;
}

export interface DiskMetrics {
  read_mbs: number;
  write_mbs: number;
  read_iops: number;
  write_iops: number;
  psi_some: PsiMetrics;
  psi_full?: PsiMetrics;
  partitions: DiskPartition[];
}

export interface ListeningPort {
  port: number;
  address: string;
  proto: string;
  pid: number | null;
  process: string;
}

export interface NetworkMetrics {
  rx_kbs: number;
  tx_kbs: number;
  packets_rx_sec: number;
  packets_tx_sec: number;
  connections_count: {
    ESTABLISHED?: number;
    LISTEN?: number;
    TIME_WAIT?: number;
    CLOSE_WAIT?: number;
    SYN_SENT?: number;
    OTHER?: number;
    [key: string]: number | undefined;
  };
  listening_ports: ListeningPort[];
}

export interface Snapshot {
  timestamp: number;
  cpu: CpuMetrics;
  memory: MemoryMetrics;
  disk: DiskMetrics;
  network: NetworkMetrics;
}

export interface StaticInfo {
  hostname: string;
  os: string;
  kernel: string;
  cpu_model: string;
  cpu_cores_physical: number;
  cpu_cores_logical: number;
  total_memory: number;
  boot_time: number;
  uptime_seconds: number;
}
