import { Card, Col, Empty, Row, Space } from 'antd';
import {
  AMBER,
  BLUE,
  BORDER,
  CARD_BG,
  GREEN,
  HOURS_24,
  PURPLE,
  TEXT,
  TEXT_DIM,
  TEXT_SOFT,
  formatCompactNumber,
  formatNumber,
  panelStyle,
  type HeatmapRow,
  type NormalizedModelStats,
  type TrendPoint,
} from './dashboard-shared';

const monoStyle = {
  color: TEXT_SOFT,
  fontVariantNumeric: 'tabular-nums',
} as const;

const truncateStyle = {
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
} as const;

const modelUsageColumns = 'minmax(190px, 1.4fr) minmax(280px, 2.8fr) 112px 72px';
const heatmapColumns = `minmax(150px, 180px) repeat(${HOURS_24.length}, 28px) 94px 72px 82px`;

export function EmptyBlock({ description }: { description: string }) {
  return (
    <Empty
      description={<span style={{ color: TEXT_DIM }}>{description}</span>}
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      style={{ margin: '48px 0' }}
    />
  );
}

export function ModelUsageRows({
  modelStats,
  maxModelTokens,
}: {
  modelStats: NormalizedModelStats[];
  maxModelTokens: number;
}) {
  if (modelStats.length === 0) return <EmptyBlock description="当前筛选下暂无模型用量" />;

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ minWidth: 920 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: modelUsageColumns,
            gap: 16,
            alignItems: 'center',
            color: TEXT_DIM,
            fontSize: 12,
            padding: '0 0 10px',
          }}
        >
          <span>模型</span>
          <span>Prompt / Completion</span>
          <span style={{ textAlign: 'right' }}>Token</span>
          <span style={{ textAlign: 'right' }}>请求</span>
        </div>
        <div
          style={{
            maxHeight: 330,
            overflowY: modelStats.length > 5 ? 'auto' : 'visible',
            paddingRight: modelStats.length > 5 ? 6 : 0,
          }}
        >
          {modelStats.map((item) => {
            const totalWidth = `${Math.max(8, Math.round((item.total_tokens / maxModelTokens) * 100))}%`;
            const promptPercent = item.total_tokens > 0
              ? Math.round((item.prompt_tokens / item.total_tokens) * 100)
              : 0;
            const completionPercent = Math.max(0, 100 - promptPercent);
            return (
              <div
                key={`${item.model}-${item.call_type}`}
                style={{
                  display: 'grid',
                  gridTemplateColumns: modelUsageColumns,
                  gap: 16,
                  alignItems: 'center',
                  minHeight: 62,
                  borderTop: `1px solid ${BORDER}`,
                }}
              >
                <div style={truncateStyle} title={`${item.model} / ${item.call_type}`}>
                  <div style={{ ...truncateStyle, color: TEXT, fontWeight: 700 }}>{item.model}</div>
                  <div style={{ ...truncateStyle, color: TEXT_DIM, fontSize: 12, marginTop: 3 }}>
                    {item.call_type}
                  </div>
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: 'flex', height: 24, background: '#21262d', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ width: totalWidth, display: 'flex' }}>
                      <div style={{ width: `${promptPercent}%`, background: BLUE }} />
                      <div style={{ width: `${completionPercent}%`, background: GREEN }} />
                    </div>
                    <div style={{ flex: 1 }} />
                  </div>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
                      gap: 10,
                      color: TEXT_DIM,
                      fontSize: 12,
                      marginTop: 5,
                    }}
                  >
                    <span style={truncateStyle}>Prompt {formatCompactNumber(item.prompt_tokens)}</span>
                    <span style={{ ...truncateStyle, textAlign: 'right' }}>
                      Completion {formatCompactNumber(item.completion_tokens)}
                    </span>
                  </div>
                </div>
                <div style={{ ...monoStyle, textAlign: 'right', fontWeight: 700, overflow: 'hidden' }}>
                  {formatCompactNumber(item.total_tokens)}
                </div>
                <div style={{ ...monoStyle, textAlign: 'right', overflow: 'hidden' }}>
                  {formatNumber(item.request_count)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function svgPath(points: Array<{ x: number; y: number }>) {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ');
}

export function TokenTrendChart({
  hourlyTrend,
  maxTrendTokens,
  maxTrendRequests,
}: {
  hourlyTrend: TrendPoint[];
  maxTrendTokens: number;
  maxTrendRequests: number;
}) {
  if (!hourlyTrend.some((item) => item.total_tokens > 0 || item.request_count > 0)) {
    return <EmptyBlock description="今日暂无可用于趋势图的真实 Token trace" />;
  }

  const chartWidth = 1080;
  const chartHeight = 270;
  const padding = { top: 20, right: 54, bottom: 44, left: 58 };
  const plotWidth = chartWidth - padding.left - padding.right;
  const plotHeight = chartHeight - padding.top - padding.bottom;
  const barSlot = plotWidth / hourlyTrend.length;
  const barWidth = Math.min(24, Math.max(10, barSlot * 0.58));
  const linePoints = hourlyTrend.map((item, index) => {
    const x = padding.left + barSlot * index + barSlot / 2;
    const y = padding.top + plotHeight - (item.request_count / maxTrendRequests) * plotHeight;
    return { x, y, item };
  });

  return (
    <div style={{ overflowX: 'auto', paddingBottom: 2 }}>
      <svg role="img" aria-label="Token 用量和请求数时间趋势" viewBox={`0 0 ${chartWidth} ${chartHeight}`} style={{ minWidth: 980, width: '100%', height: 280, display: 'block' }}>
        <rect x={0} y={0} width={chartWidth} height={chartHeight} fill={CARD_BG} />
        {[0, 0.5, 1].map((tick) => {
          const y = padding.top + plotHeight - tick * plotHeight;
          return (
            <g key={tick}>
              <line x1={padding.left} x2={chartWidth - padding.right} y1={y} y2={y} stroke={BORDER} strokeOpacity={tick === 0 ? 0.9 : 0.58} />
              <text x={padding.left - 10} y={y + 4} textAnchor="end" fill={TEXT_DIM} fontSize={12}>{formatCompactNumber(maxTrendTokens * tick)}</text>
              <text x={chartWidth - padding.right + 10} y={y + 4} fill={TEXT_DIM} fontSize={12}>{formatCompactNumber(maxTrendRequests * tick)}</text>
            </g>
          );
        })}
        <text x={padding.left - 8} y={padding.top - 8} textAnchor="end" fill={TEXT_SOFT} fontSize={12} fontWeight={700}>Token</text>
        <text x={chartWidth - padding.right + 10} y={padding.top - 8} fill={AMBER} fontSize={12} fontWeight={700}>请求</text>
        {hourlyTrend.map((item, index) => {
          const x = padding.left + barSlot * index + (barSlot - barWidth) / 2;
          const totalHeight = (item.total_tokens / maxTrendTokens) * plotHeight;
          const completionHeight = item.total_tokens > 0 ? (item.completion_tokens / item.total_tokens) * totalHeight : 0;
          const promptHeight = Math.max(0, totalHeight - completionHeight);
          const promptY = padding.top + plotHeight - totalHeight;
          const completionY = promptY + promptHeight;
          const labelX = padding.left + barSlot * index + barSlot / 2;
          return (
            <g key={item.key}>
              <rect x={x} y={padding.top} width={barWidth} height={plotHeight} fill="#21262d" opacity={0.5} rx={3}>
                <title>{`${item.label} Token ${formatNumber(item.total_tokens)}，请求 ${formatNumber(item.request_count)}`}</title>
              </rect>
              {item.total_tokens > 0 && (
                <>
                  <rect x={x} y={promptY} width={barWidth} height={promptHeight} fill={BLUE} rx={3} />
                  <rect x={x} y={completionY} width={barWidth} height={completionHeight} fill={GREEN} rx={3} />
                </>
              )}
              {index % 3 === 0 && (
                <text x={labelX} y={chartHeight - 18} textAnchor="middle" fill={TEXT_DIM} fontSize={12} transform={`rotate(-55 ${labelX} ${chartHeight - 18})`}>{item.shortLabel}</text>
              )}
            </g>
          );
        })}
        <path d={svgPath(linePoints)} fill="none" stroke={AMBER} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />
        {linePoints.map((point) => (
          <circle key={point.item.key} cx={point.x} cy={point.y} r={3.5} fill={AMBER} stroke={CARD_BG} strokeWidth={1.5}>
            <title>{`${point.item.label} 请求 ${formatNumber(point.item.request_count)}，Token ${formatNumber(point.item.total_tokens)}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

export function PerformanceTrendChart({ hourlyTrend }: { hourlyTrend: TrendPoint[] }) {
  if (!hourlyTrend.some((item) => item.total_tokens > 0 || item.request_count > 0)) {
    return <EmptyBlock description="今日暂无可用于性能走势的真实 Token trace" />;
  }

  const chartWidth = 1080;
  const chartHeight = 220;
  const padding = { top: 20, right: 54, bottom: 40, left: 58 };
  const plotWidth = chartWidth - padding.left - padding.right;
  const plotHeight = chartHeight - padding.top - padding.bottom;
  const slot = plotWidth / hourlyTrend.length;
  const maxAvgTokens = Math.max(1, ...hourlyTrend.map((item) => (item.request_count > 0 ? item.total_tokens / item.request_count : 0)));
  const maxRequests = Math.max(1, ...hourlyTrend.map((item) => item.request_count));
  const buildPoints = (getValue: (item: TrendPoint) => number, maxValue: number) => hourlyTrend.map((item, index) => {
    const x = padding.left + slot * index + slot / 2;
    const y = padding.top + plotHeight - (getValue(item) / maxValue) * plotHeight;
    return { x, y, item };
  });
  const avgPoints = buildPoints((item) => (item.request_count > 0 ? item.total_tokens / item.request_count : 0), maxAvgTokens);
  const requestPoints = buildPoints((item) => item.request_count, maxRequests);

  return (
    <div style={{ overflowX: 'auto', paddingBottom: 2 }}>
      <svg role="img" aria-label="平均 Token 和请求数时间走势" viewBox={`0 0 ${chartWidth} ${chartHeight}`} style={{ minWidth: 980, width: '100%', height: 230, display: 'block' }}>
        <rect x={0} y={0} width={chartWidth} height={chartHeight} fill={CARD_BG} />
        {[0, 0.5, 1].map((tick) => {
          const y = padding.top + plotHeight - tick * plotHeight;
          return (
            <g key={tick}>
              <line x1={padding.left} x2={chartWidth - padding.right} y1={y} y2={y} stroke={BORDER} strokeOpacity={0.58} />
              <text x={padding.left - 10} y={y + 4} textAnchor="end" fill={TEXT_DIM} fontSize={12}>{formatCompactNumber(maxAvgTokens * tick)}</text>
              <text x={chartWidth - padding.right + 10} y={y + 4} fill={TEXT_DIM} fontSize={12}>{formatCompactNumber(maxRequests * tick)}</text>
            </g>
          );
        })}
        <text x={padding.left - 8} y={padding.top - 8} textAnchor="end" fill={GREEN} fontSize={12} fontWeight={700}>平均</text>
        <text x={chartWidth - padding.right + 10} y={padding.top - 8} fill={PURPLE} fontSize={12} fontWeight={700}>请求</text>
        <path d={svgPath(avgPoints)} fill="none" stroke="#56d695" strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
        <path d={svgPath(requestPoints)} fill="none" stroke={PURPLE} strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
        {avgPoints.map((point) => (
          <circle key={`avg-${point.item.key}`} cx={point.x} cy={point.y} r={3} fill="#56d695" stroke={CARD_BG} strokeWidth={1.4}>
            <title>{`${point.item.label} 平均 ${formatCompactNumber(point.item.request_count > 0 ? point.item.total_tokens / point.item.request_count : 0)} tokens/请求`}</title>
          </circle>
        ))}
        {requestPoints.map((point) => (
          <circle key={`req-${point.item.key}`} cx={point.x} cy={point.y} r={3} fill={PURPLE} stroke={CARD_BG} strokeWidth={1.4}>
            <title>{`${point.item.label} 请求 ${formatNumber(point.item.request_count)}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

export function HeatmapSection({
  title,
  rows,
  hint,
  maxHeatmapTokens,
}: {
  title: string;
  rows: HeatmapRow[];
  hint: string;
  maxHeatmapTokens: number;
}) {
  return (
    <Card title={<span style={{ color: TEXT }}>{title}</span>} extra={<span style={{ color: TEXT_DIM, fontSize: 12 }}>{hint}</span>} style={{ ...panelStyle, marginBottom: 10 }} bodyStyle={{ padding: 12 }}>
      {rows.length === 0 ? <EmptyBlock description="今日暂无小时分布数据" /> : (
        <div style={{ overflowX: 'auto' }}>
          <div style={{ minWidth: 980 }}>
            <div style={{ display: 'grid', gridTemplateColumns: heatmapColumns, gap: 5, alignItems: 'center', color: TEXT_DIM, fontSize: 11, paddingBottom: 6 }}>
              <span />
              {HOURS_24.map((hour) => <span key={hour} style={{ textAlign: 'center' }}>{hour}</span>)}
              <span style={{ textAlign: 'right' }}>Token</span>
              <span style={{ textAlign: 'right' }}>请求</span>
              <span style={{ textAlign: 'right' }}>均值</span>
            </div>
            {rows.slice(0, 8).map((row) => (
              <div key={row.id} style={{ display: 'grid', gridTemplateColumns: heatmapColumns, gap: 5, alignItems: 'center', minHeight: 28 }}>
                <div style={{ ...truncateStyle, color: TEXT_SOFT, fontWeight: 600 }} title={row.label}>{row.label}</div>
                {HOURS_24.map((hour) => {
                  const value = row.tokensByHour[hour] ?? 0;
                  const intensity = value > 0 ? Math.max(0.22, Math.min(0.92, value / maxHeatmapTokens)) : 0;
                  return (
                    <div
                      key={`${row.id}-${hour}`}
                      title={`${hour}:00 ${formatNumber(value)} tokens`}
                      style={{
                        height: 22,
                        borderRadius: 4,
                        background: value > 0 ? `rgba(46, 160, 103, ${intensity})` : '#21262d',
                        border: '1px solid rgba(48, 54, 61, 0.72)',
                      }}
                    />
                  );
                })}
                <div style={{ ...monoStyle, textAlign: 'right', fontWeight: 700 }}>{formatCompactNumber(row.total_tokens)}</div>
                <div style={{ ...monoStyle, textAlign: 'right' }}>{formatNumber(row.request_count)}</div>
                <div style={{ ...monoStyle, textAlign: 'right' }}>{formatCompactNumber(row.avg_tokens)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

export function ChartCard({
  title,
  legend,
  children,
}: {
  title: string;
  legend: Array<[string, string, 'dot' | 'square']>;
  children: React.ReactNode;
}) {
  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 12 }}>
      <Col xs={24}>
        <Card
          title={<span style={{ color: TEXT }}>{title}</span>}
          extra={(
            <Space size={16} wrap>
              {legend.map(([label, color, shape]) => (
                <LegendItem key={label} label={label} color={color} shape={shape} />
              ))}
            </Space>
          )}
          style={panelStyle}
          bodyStyle={{ padding: 14 }}
        >
          {children}
        </Card>
      </Col>
    </Row>
  );
}

export function LegendItem({ label, color, shape }: { label: string; color: string; shape: 'dot' | 'square' }) {
  return (
    <Space size={6}>
      <span
        style={{
          width: 10,
          height: 10,
          background: color,
          borderRadius: shape === 'dot' ? 999 : 2,
          display: 'inline-block',
        }}
      />
      <span style={{ color: TEXT_DIM, fontSize: 12 }}>{label}</span>
    </Space>
  );
}
