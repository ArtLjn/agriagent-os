export const BG = '#0d1117';
export const CARD_BG = '#161b22';
export const BORDER = '#30363d';
export const TEXT = '#e6edf3';
export const TEXT_DIM = '#8b949e';
export const TEXT_SOFT = '#c9d1d9';
export const GREEN = '#238636';
export const BLUE = '#2f81f7';
export const AMBER = '#d29922';
export const PURPLE = '#8b6bb1';
export const HOURS_24 = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, '0'));

export type NormalizedModelStats = {
  model: string;
  call_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
};

export type TrendPoint = {
  key: string;
  label: string;
  shortLabel: string;
  hour: string;
  date?: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
};

export type HeatmapRow = {
  id: string;
  label: string;
  tokensByHour: Record<string, number>;
  total_tokens: number;
  request_count: number;
  avg_tokens: number;
};

export const toNumber = (value: unknown) => {
  const num = Number(value ?? 0);
  return Number.isFinite(num) ? num : 0;
};

export const formatNumber = (value: number) => Math.round(value).toLocaleString();

export const formatCompactNumber = (value: number) => {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value >= 10_000_000 ? 1 : 2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(value >= 10_000 ? 0 : 1)}K`;
  return formatNumber(value);
};

export const fieldLabelStyle = {
  color: TEXT_DIM,
  fontSize: 13,
  marginBottom: 8,
} as const;

export const panelStyle = {
  background: CARD_BG,
  borderColor: BORDER,
} as const;

export const compactCardStyle = {
  ...panelStyle,
  minHeight: 88,
} as const;
