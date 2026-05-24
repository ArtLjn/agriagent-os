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
      <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, maxHeight: 400, overflow: 'auto', fontSize: 12 }}>
        {body || '无响应'}
      </pre>
    </div>
  );
}
