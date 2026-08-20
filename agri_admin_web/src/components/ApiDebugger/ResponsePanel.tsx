import { Tag } from 'antd';

interface Props {
  status: number | null; duration: number | null; body: string;
}

function statusColor(code: number): string {
  if (code < 300) return 'green';
  if (code < 400) return 'orange';
  return 'red';
}

export default function ResponsePanel({ status, duration, body }: Props) {
  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        {status !== null && <Tag color={statusColor(status)}>{status}</Tag>}
        {duration !== null && <Tag>{duration}ms</Tag>}
      </div>
      <pre style={{ background: '#0d1117', color: '#c9d1d9', padding: 12, borderRadius: 6, maxHeight: 400, overflow: 'auto', fontSize: 12, border: '1px solid #30363d', fontFamily: 'monospace' }}>
        {body || '无响应'}
      </pre>
    </div>
  );
}
