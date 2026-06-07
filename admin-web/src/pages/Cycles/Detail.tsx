import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Descriptions, Timeline, Card, Button, Spin, Space, message, Tag, Progress, Empty } from 'antd';
import { ArrowLeftOutlined, StepForwardOutlined } from '@ant-design/icons';
import { getCycle, advanceStage, type CropCycle } from '../../api/cycles';
import { PageShell } from '../../components/PageShell';
import { cardStyle, palette } from '../../styles/theme';

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

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />;
  if (!cycle) return <Empty description="未找到茬口" />;

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
    <PageShell
      title={cycle.name}
      description="查看当前茬口基本信息、生长阶段和推进状态。"
      actions={(
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/cycles')}>返回列表</Button>
          <Button type="primary" icon={<StepForwardOutlined />} onClick={handleAdvance} loading={advancing}>推进到下一阶段</Button>
        </Space>
      )}
    >
      <Card style={cardStyle}>
        <Descriptions column={2}>
          <Descriptions.Item label="开始日期">{cycle.start_date}</Descriptions.Item>
          <Descriptions.Item label="地块">{cycle.field_name || '--'}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={cycle.status === 'active' ? 'green' : 'default'}>{cycle.status === 'active' ? '进行中' : cycle.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="阶段进度">
            <Progress
              percent={Math.round(((cycle.stages.findIndex((stage) => stage.is_current) + 1) / Math.max(cycle.stages.length, 1)) * 100)}
              size="small"
            />
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="生长阶段" style={{ ...cardStyle, marginTop: 16 }}>
        <Timeline items={cycle.stages.map((s) => ({
          color: s.is_current ? palette.success : 'gray',
          children: (
            <div>
              <strong>{s.name}</strong> ({s.start_date} ~ {s.end_date})
              {s.is_current && <Tag color="success" style={{ marginLeft: 8 }}>当前阶段</Tag>}
              {s.key_tasks && <div style={{ color: palette.textMuted, marginTop: 4 }}>{s.key_tasks}</div>}
            </div>
          ),
        }))} />
      </Card>
    </PageShell>
  );
}
