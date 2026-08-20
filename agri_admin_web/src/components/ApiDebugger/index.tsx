import { useState } from 'react';
import { Button, Drawer, Space, message } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import RequestEditor from './RequestEditor';
import ResponsePanel from './ResponsePanel';
import apiClient from '../../api/client';

interface Props {
  open: boolean; onClose: () => void;
  defaultMethod?: string; defaultUrl?: string; defaultBody?: string;
}

export default function ApiDebugger({ open, onClose, defaultMethod = 'GET', defaultUrl = '', defaultBody = '{}' }: Props) {
  const [method, setMethod] = useState(defaultMethod);
  const [url, setUrl] = useState(defaultUrl);
  const [body, setBody] = useState(defaultBody);
  const [status, setStatus] = useState<number | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [responseBody, setResponseBody] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    setLoading(true);
    const start = Date.now();
    try {
      const config: Record<string, unknown> = { method: method.toLowerCase(), url };
      if (['POST', 'PUT', 'PATCH'].includes(method)) {
        try { config.data = JSON.parse(body); } catch { message.error('请求体 JSON 格式错误'); setLoading(false); return; }
      }
      const res = await apiClient.request(config);
      setStatus(res.status);
      setDuration(Date.now() - start);
      setResponseBody(JSON.stringify(res.data, null, 2));
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: unknown } };
      setStatus(axiosErr.response?.status ?? 0);
      setDuration(Date.now() - start);
      setResponseBody(JSON.stringify(axiosErr.response?.data ?? { error: String(err) }, null, 2));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer title="API 调试" open={open} onClose={onClose} width={640}>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <RequestEditor method={method} url={url} body={body}
          onMethodChange={setMethod} onUrlChange={setUrl} onBodyChange={setBody} />
        <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={handleSend} block>
          发送请求
        </Button>
        <ResponsePanel status={status} duration={duration} body={responseBody} />
      </Space>
    </Drawer>
  );
}
