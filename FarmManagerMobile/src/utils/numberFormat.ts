export function formatCompactNumber(value: number): string {
  const abs = Math.abs(value);

  if (abs >= 100000000) {
    return `${(value / 100000000).toFixed(2)}亿`;
  }
  if (abs >= 10000) {
    return `${(value / 10000).toFixed(1)}万`;
  }

  return String(Math.round(value));
}
