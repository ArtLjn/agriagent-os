import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Descriptions, Timeline, Card, Button, Spin } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { getCycle, type CropCycle } from '../../api/cycles';

export default function CycleDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [cycle, setCycle] = useState<CropCycle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    getCycle(Number(id))
      .then((res) => setCycle(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <Spin />;
  if (!cycle) return <div>未找到茬口</div>;

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/cycles')} style={{ marginBottom: 16 }}>返回列表</Button>
      <Card title={cycle.name}>
        <Descriptions column={2}>
          <Descriptions.Item label="开始日期">{cycle.start_date}</Descriptions.Item>
          <Descriptions.Item label="地块">{cycle.field_name || '--'}</Descriptions.Item>
          <Descriptions.Item label="状态">{cycle.status}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="生长阶段" style={{ marginTop: 16 }}>
        <Timeline items={cycle.stages.map((s) => ({
          color: s.is_current ? 'green' : 'gray',
          children: (
            <div>
              <strong>{s.name}</strong> ({s.start_date} ~ {s.end_date})
              {s.is_current && <span style={{ color: '#52c41a', marginLeft: 8 }}>当前阶段</span>}
              {s.key_tasks && <div style={{ color: '#666' }}>{s.key_tasks}</div>}
            </div>
          ),
        }))} />
      </Card>
    </div>
  );
}
