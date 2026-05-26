import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Descriptions, Timeline, Card, Button, Spin, Space, message } from 'antd';
import { ArrowLeftOutlined, StepForwardOutlined } from '@ant-design/icons';
import { getCycle, advanceStage, type CropCycle } from '../../api/cycles';

export default function CycleDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [cycle, setCycle] = useState<CropCycle | null>(null);
  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);

  const fetchCycle = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await getCycle(Number(id));
      setCycle(res);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCycle();
  }, [id]);

  if (loading) return <Spin />;
  if (!cycle) return <div>未找到茬口</div>;

  const handleAdvance = async () => {
    if (!id) return;
    setAdvancing(true);
    try {
      await advanceStage(Number(id));
      message.success('已推进到下一阶段');
      fetchCycle();
    } catch {
      message.error('推进失败');
    } finally {
      setAdvancing(false);
    }
  };

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/cycles')}>返回列表</Button>
        <Button icon={<StepForwardOutlined />} onClick={handleAdvance} loading={advancing}>推进到下一阶段</Button>
      </Space>
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
