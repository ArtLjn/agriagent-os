import { Input, Select, Row, Col } from 'antd';

const { TextArea } = Input;
const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

interface Props {
  method: string; url: string; body: string;
  onMethodChange: (v: string) => void;
  onUrlChange: (v: string) => void;
  onBodyChange: (v: string) => void;
}

export default function RequestEditor({ method, url, body, onMethodChange, onUrlChange, onBodyChange }: Props) {
  return (
    <div>
      <Row gutter={8} style={{ marginBottom: 12 }}>
        <Col span={6}>
          <Select value={method} onChange={onMethodChange} options={METHODS.map((m) => ({ value: m }))} style={{ width: '100%' }} />
        </Col>
        <Col span={18}>
          <Input value={url} onChange={(e) => onUrlChange(e.target.value)} placeholder="/api/endpoint" />
        </Col>
      </Row>
      {(method === 'POST' || method === 'PUT' || method === 'PATCH') && (
        <TextArea value={body} onChange={(e) => onBodyChange(e.target.value)} rows={8} placeholder='{"key": "value"}' style={{ fontFamily: 'monospace' }} />
      )}
    </div>
  );
}
