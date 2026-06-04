import { useEffect, useState } from 'react';
import {
  Typography,
  Button,
  Card,
  Descriptions,
  Tag,
  Modal,
  message,
  Spin,
  Empty,
} from 'antd';
import { SettingOutlined, ClearOutlined } from '@ant-design/icons';
import { getConfig, clearCache, type AdminConfig } from '../../api/admin';

const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';

export default function ConfigKeys() {
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [clearLoading, setClearLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await getConfig();
        setConfig(res);
      } catch {
        // 错误已在 api client 中处理
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleClearCache = () => {
    Modal.confirm({
      title: '确认清空缓存',
      content: '确定要清空所有缓存吗？此操作不可恢复。',
      okText: '确认清空',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        setClearLoading(true);
        try {
          const res = await clearCache();
          const total = Object.values(res.cleared).reduce((sum, v) => sum + v, 0);
          message.success(`已清空 ${total} 条缓存`);
        } catch {
          // 错误已在 api client 中处理
        } finally {
          setClearLoading(false);
        }
      },
    });
  };

  const cardStyle: React.CSSProperties = {
    backgroundColor: CARD_BG,
    border: `1px solid ${BORDER}`,
    marginBottom: 16,
  };

  const descriptionsLabelStyle: React.CSSProperties = {
    color: TEXT_DIM,
    width: 140,
  };

  const descriptionsContentStyle: React.CSSProperties = {
    color: TEXT,
  };

  const maskApiKey = (key: string): string => {
    if (!key || key.length <= 8) return '***';
    return `${key.slice(0, 4)}...${key.slice(-4)}`;
  };

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Typography.Title level={4} style={{ color: TEXT, margin: 0 }}>
          <SettingOutlined style={{ marginRight: 8 }} />
          配置管理
        </Typography.Title>
        <Button
          danger
          icon={<ClearOutlined />}
          loading={clearLoading}
          onClick={handleClearCache}
        >
          清空缓存
        </Button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 64 }}>
          <Spin size="large" />
        </div>
      ) : !config ? (
        <Empty description="暂无配置数据" style={{ marginTop: 64 }} />
      ) : (
        <>
          <Card
            title={<span style={{ color: TEXT }}>AI 配置</span>}
            style={cardStyle}
            headStyle={{ backgroundColor: CARD_BG, borderBottom: `1px solid ${BORDER}` }}
          >
            <Descriptions
              column={1}
              labelStyle={descriptionsLabelStyle}
              contentStyle={descriptionsContentStyle}
            >
              <Descriptions.Item label="模型">{config.ai.model}</Descriptions.Item>
              <Descriptions.Item label="Base URL">{config.ai.base_url}</Descriptions.Item>
              <Descriptions.Item label="API Key">
                {maskApiKey(config.ai.api_key)}
              </Descriptions.Item>
              <Descriptions.Item label="Enable Thinking">
                <Tag color={config.ai.enable_thinking ? 'success' : 'default'}>
                  {config.ai.enable_thinking ? '启用' : '禁用'}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card
            title={<span style={{ color: TEXT }}>Trace 配置</span>}
            style={cardStyle}
            headStyle={{ backgroundColor: CARD_BG, borderBottom: `1px solid ${BORDER}` }}
          >
            <Descriptions
              column={1}
              labelStyle={descriptionsLabelStyle}
              contentStyle={descriptionsContentStyle}
            >
              <Descriptions.Item label="Batch Size">
                {config.trace.batch_size}
              </Descriptions.Item>
              <Descriptions.Item label="Flush Interval">
                {config.trace.flush_interval} 秒
              </Descriptions.Item>
              <Descriptions.Item label="TTL Days">
                {config.trace.trace_ttl_days} 天
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card
            title={<span style={{ color: TEXT }}>Token 配额</span>}
            style={cardStyle}
            headStyle={{ backgroundColor: CARD_BG, borderBottom: `1px solid ${BORDER}` }}
          >
            <Descriptions
              column={1}
              labelStyle={descriptionsLabelStyle}
              contentStyle={descriptionsContentStyle}
            >
              <Descriptions.Item label="月限额">
                {config.token_quota.monthly_limit.toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="周限额">
                {config.token_quota.weekly_limit.toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="超额动作">
                <Tag
                  color={
                    config.token_quota.over_quota_action === 'reject'
                      ? 'error'
                      : config.token_quota.over_quota_action === 'warn'
                        ? 'warning'
                        : 'default'
                  }
                >
                  {config.token_quota.over_quota_action === 'reject' ? 'reject' : 'warn'}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card
            title={<span style={{ color: TEXT }}>LangSmith</span>}
            style={cardStyle}
            headStyle={{ backgroundColor: CARD_BG, borderBottom: `1px solid ${BORDER}` }}
          >
            <Descriptions
              column={1}
              labelStyle={descriptionsLabelStyle}
              contentStyle={descriptionsContentStyle}
            >
              <Descriptions.Item label="启用状态">
                <Tag color={config.langsmith.enabled ? 'success' : 'default'}>
                  {config.langsmith.enabled ? '启用' : '禁用'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="项目名称">
                {config.langsmith.project}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <div
            style={{
              marginTop: 24,
              padding: 12,
              backgroundColor: CARD_BG,
              border: `1px solid ${BORDER}`,
              borderRadius: 8,
              color: TEXT_DIM,
              fontSize: 13,
            }}
          >
            API Key 验证功能需要后端支持 /admin/config/validate-key 端点
          </div>
        </>
      )}
    </div>
  );
}
