import { useState } from 'react';
import { Menu, Card, Row, Col, Button, message, Space, Spin } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import RequestEditor from '../../components/ApiDebugger/RequestEditor';
import ResponsePanel from '../../components/ApiDebugger/ResponsePanel';
import apiClient from '../../api/client';

interface Endpoint {
  method: string;
  path: string;
  description: string;
  body?: string;
}

const ENDPOINTS: Record<string, Endpoint[]> = {
  '作物管理': [
    { method: 'POST', path: '/crops/templates', description: '创建作物模板', body: '{"name":"西瓜","variety":"8424","stages":[{"name":"育苗期","duration_days":30,"order_index":1}]}' },
    { method: 'GET', path: '/crops/templates', description: '获取模板列表' },
    { method: 'GET', path: '/crops/templates/1', description: '获取模板详情' },
  ],
  '茬口管理': [
    { method: 'POST', path: '/cycles', description: '创建茬口', body: '{"name":"春季西瓜","crop_template_id":1,"start_date":"2026-04-01"}' },
    { method: 'GET', path: '/cycles', description: '获取茬口列表' },
    { method: 'GET', path: '/cycles/1', description: '获取茬口详情' },
  ],
  '农事日志': [
    { method: 'POST', path: '/logs', description: '创建日志', body: '{"cycle_id":1,"operation_type":"浇水","operation_date":"2026-05-20"}' },
    { method: 'GET', path: '/logs', description: '获取日志列表' },
    { method: 'GET', path: '/logs?cycle_id=1', description: '按茬口筛选日志' },
  ],
  '成本记账': [
    { method: 'POST', path: '/costs', description: '创建记录', body: '{"record_type":"cost","category":"肥料","amount":500,"record_date":"2026-05-20"}' },
    { method: 'GET', path: '/costs', description: '获取记录列表' },
    { method: 'GET', path: '/costs/cycles/1/profit', description: '周期利润' },
    { method: 'GET', path: '/costs/summary/2026', description: '年度汇总' },
  ],
  'AI 助手': [
    { method: 'POST', path: '/agent/chat', description: 'AI 对话', body: '{"message":"今天该做什么？"}' },
    { method: 'GET', path: '/agent/daily', description: '每日建议' },
    { method: 'POST', path: '/agent/report', description: '生成报告', body: '{"report_type":"weekly"}' },
    { method: 'GET', path: '/agent/advice-history', description: '建议历史' },
    { method: 'GET', path: '/agent/report-history', description: '报告历史' },
  ],
  '天气预报': [
    { method: 'GET', path: '/weather/forecast', description: '天气预报(7天)' },
    { method: 'GET', path: '/weather/forecast?days=3', description: '天气预报(3天)' },
  ],
  '系统': [
    { method: 'GET', path: '/health', description: '健康检查' },
  ],
};

const methodColor: Record<string, string> = {
  GET: '#52c41a', POST: '#1890ff', PUT: '#faad14', DELETE: '#ff4d4f',
};

export default function ApiTester() {
  const [selected, setSelected] = useState<Endpoint>(ENDPOINTS['系统'][0]);
  const [method, setMethod] = useState(selected.method);
  const [url, setUrl] = useState(selected.path);
  const [body, setBody] = useState(selected.body || '{}');
  const [status, setStatus] = useState<number | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [responseBody, setResponseBody] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSelect = (ep: Endpoint) => {
    setSelected(ep);
    setMethod(ep.method);
    setUrl(ep.path);
    setBody(ep.body || '{}');
    setStatus(null);
    setDuration(null);
    setResponseBody('');
  };

  const handleSend = async () => {
    setLoading(true);
    const start = Date.now();
    try {
      const config: Record<string, unknown> = { method: method.toLowerCase(), url };
      if (['POST', 'PUT', 'PATCH'].includes(method)) {
        try { config.data = JSON.parse(body); } catch { message.error('JSON 格式错误'); setLoading(false); return; }
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

  const menuItems = Object.entries(ENDPOINTS).map(([group, eps]) => ({
    key: group,
    label: group,
    children: eps.map((ep, idx) => ({
      key: `${group}-${idx}`,
      label: (
        <span>
          <span style={{ color: methodColor[ep.method], fontWeight: 'bold', marginRight: 8 }}>{ep.method}</span>
          <span>{ep.description}</span>
        </span>
      ),
    })),
  }));

  return (
    <Row gutter={16}>
      <Col span={8}>
        <Card title="API 端点" style={{ maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}>
          <Menu mode="inline" items={menuItems} onClick={({ key }) => {
            const [group, idxStr] = String(key).split('-');
            handleSelect(ENDPOINTS[group][Number(idxStr)]);
          }} />
        </Card>
      </Col>
      <Col span={16}>
        <Card title={selected.description}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <RequestEditor method={method} url={url} body={body}
              onMethodChange={setMethod} onUrlChange={setUrl} onBodyChange={setBody} />
            <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={handleSend} block>
              发送请求
            </Button>
            {loading && <Spin />}
            <ResponsePanel status={status} duration={duration} body={responseBody} />
          </Space>
        </Card>
      </Col>
    </Row>
  );
}
